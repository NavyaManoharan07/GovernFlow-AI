"""Loads and chunks the knowledge_base/ markdown files.

Chunking strategy: every knowledge base file follows one convention for
its authoritative content --

    - REQ-<PREFIX>-<N>: <requirement text> (Service: <tag[, tag...]>) (Source: <citation>)

Each such line becomes one precise, citable chunk. Everything else
(Overview/Processing/Notes paragraphs under a `## heading`) becomes a
lower-priority supplementary chunk tagged service="general", so retrieval
still has something to return for broader queries that don't match a
specific numbered requirement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

KNOWLEDGE_BASE_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge_base"

_REQ_LINE_RE = re.compile(
    r"^- (REQ-[A-Za-z0-9-]+):\s*(.+?)\s*\(Service:\s*([^)]+?)\)\s*\(Source:\s*(.+)\)\s*$"
)
_HEADING_RE = re.compile(r"^##\s+(.+)$")


@dataclass
class Chunk:
    chunk_id: str
    text: str
    source: str
    service_tags: List[str] = field(default_factory=lambda: ["general"])


def _parse_file(path: Path) -> List[Chunk]:
    chunks: List[Chunk] = []
    current_heading = "Overview"
    paragraph_lines: List[str] = []
    paragraph_idx = 0

    def flush_paragraph() -> None:
        nonlocal paragraph_idx
        text = " ".join(line.strip() for line in paragraph_lines if line.strip())
        paragraph_lines.clear()
        if not text or text.startswith(">"):
            return
        if current_heading.strip().lower() in {"numbered requirements"}:
            # REQ- lines are handled separately with precise citations;
            # skip any stray non-REQ text in that section.
            return
        paragraph_idx += 1
        chunks.append(
            Chunk(
                chunk_id=f"{path.stem}:{current_heading}:{paragraph_idx}",
                text=text,
                source=f"{path.stem} — {current_heading} (MOCK)",
                service_tags=["general"],
            )
        )

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()

        if line.startswith("# ") and not line.startswith("##"):
            # Document title (H1) -- not a section, carries no citable content.
            flush_paragraph()
            continue

        heading_match = _HEADING_RE.match(line)
        if heading_match:
            flush_paragraph()
            current_heading = heading_match.group(1).strip()
            continue

        req_match = _REQ_LINE_RE.match(line)
        if req_match:
            flush_paragraph()
            req_id, requirement_text, service_field, source = req_match.groups()
            service_tags = [tag.strip() for tag in service_field.split(",") if tag.strip()]
            chunks.append(
                Chunk(
                    chunk_id=f"{path.stem}:{req_id}",
                    text=requirement_text.strip(),
                    source=source.strip(),
                    service_tags=service_tags or ["general"],
                )
            )
            continue

        if not line.strip():
            flush_paragraph()
            continue

        paragraph_lines.append(line)

    flush_paragraph()
    return chunks


def load_chunks() -> List[Chunk]:
    """Loads and chunks every .md file in knowledge_base/. Deterministic
    ordering (sorted by filename) so retrieval results are reproducible
    across runs."""
    if not KNOWLEDGE_BASE_DIR.is_dir():
        return []
    chunks: List[Chunk] = []
    for path in sorted(KNOWLEDGE_BASE_DIR.glob("*.md")):
        if path.name.upper() == "README.MD":
            continue
        chunks.extend(_parse_file(path))
    return chunks
