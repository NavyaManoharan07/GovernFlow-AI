"""Pure-Python TF-IDF retriever over the knowledge base.

Deliberately avoids sentence-transformers/numpy/sklearn: this is a
hackathon demo, "reliability > complexity" per the project's engineering
rules, and a dependency-free retriever means the demo runs identically
offline with no model download and no install-time risk. TF-IDF + cosine
similarity over ~50 short, well-structured chunks is more than sufficient
for this corpus size.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, List, Optional

from backend.rag.documents import Chunk, load_chunks
from backend.rag.schemas import RetrievedRule

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Below this cosine-similarity score, a chunk is not considered relevant
# enough to report -- this is what keeps RegulationAgent from ever
# fabricating a rule: if everything scores below the floor, retrieve()
# returns an empty list and the agent must say so.
DEFAULT_MIN_CONFIDENCE = 0.12

# Filtered out before scoring -- without this, a query built mostly of
# function words ("what is the ... for ...") picks up nonzero similarity
# against nearly every chunk just from stopword overlap, since even a
# smoothed idf never reaches exactly zero for a term that appears in most
# documents. This corpus is small and domain-specific enough that a fixed
# stopword list is simpler and more predictable than a smarter scheme.
_STOPWORDS = frozenset(
    """
    a an the this that these those is are was were be been being
    of in on at for to from by with without within into onto
    and or but if then than so as it its it's i you he she we they
    do does did doing done not no yes
    what which who whom whose when where why how
    my your his her our their
    will would shall should can could may might must
    """.split()
)


def _tokenize(text: str) -> List[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


class TfidfRetriever:
    def __init__(self, chunks: List[Chunk]) -> None:
        self._chunks = chunks
        self._doc_tokens: List[List[str]] = [_tokenize(c.text) for c in chunks]
        self._df: Counter = Counter()
        for tokens in self._doc_tokens:
            for token in set(tokens):
                self._df[token] += 1
        self._n_docs = len(chunks)
        # Classic (unsmoothed) idf: log(N / df). A term appearing in every
        # chunk gets idf=0 and contributes nothing -- deliberately, so
        # near-universal words can't manufacture false-positive similarity
        # for an off-topic query (see _STOPWORDS above for the common case,
        # this is the mathematical backstop for anything the fixed list
        # misses).
        self._idf: Dict[str, float] = {
            token: math.log(self._n_docs / df) for token, df in self._df.items() if df < self._n_docs
        }
        self._doc_vectors: List[Dict[str, float]] = [
            self._vectorize(tokens, is_query=False) for tokens in self._doc_tokens
        ]
        self._doc_norms: List[float] = [math.sqrt(sum(w * w for w in vec.values())) for vec in self._doc_vectors]

    def _vectorize(self, tokens: List[str], *, is_query: bool) -> Dict[str, float]:
        if not tokens:
            return {}
        tf = Counter(tokens)
        max_tf = max(tf.values())
        vec: Dict[str, float] = {}
        for token, count in tf.items():
            idf = self._idf.get(token)
            if idf is None:
                if not is_query:
                    continue
                # Unknown-to-corpus query token: no signal, skip it rather
                # than inventing an idf weight.
                continue
            vec[token] = (count / max_tf) * idf
        return vec

    @staticmethod
    def _cosine(vec_a: Dict[str, float], norm_a: float, vec_b: Dict[str, float], norm_b: float) -> float:
        if norm_a == 0 or norm_b == 0:
            return 0.0
        shorter, longer = (vec_a, vec_b) if len(vec_a) < len(vec_b) else (vec_b, vec_a)
        dot = sum(weight * longer.get(token, 0.0) for token, weight in shorter.items())
        return dot / (norm_a * norm_b)

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        service: Optional[str] = None,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    ) -> List[RetrievedRule]:
        query_tokens = _tokenize(query)
        query_vec = self._vectorize(query_tokens, is_query=True)
        query_norm = math.sqrt(sum(w * w for w in query_vec.values()))

        scored: List[tuple[float, Chunk]] = []
        for chunk, doc_vec, doc_norm in zip(self._chunks, self._doc_vectors, self._doc_norms):
            if service is not None and service not in chunk.service_tags and "general" not in chunk.service_tags:
                continue
            score = self._cosine(query_vec, query_norm, doc_vec, doc_norm)
            if score >= min_confidence:
                scored.append((score, chunk))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            RetrievedRule(requirement=chunk.text, source=chunk.source, confidence=round(score, 4))
            for score, chunk in scored[:top_k]
        ]


_singleton_retriever: Optional[TfidfRetriever] = None


def get_retriever() -> TfidfRetriever:
    global _singleton_retriever
    if _singleton_retriever is None:
        _singleton_retriever = TfidfRetriever(load_chunks())
    return _singleton_retriever


def reset_retriever() -> None:
    """Test helper: forces get_retriever() to reload+reindex from disk."""
    global _singleton_retriever
    _singleton_retriever = None


def retrieve(query: str, top_k: int = 5, service: Optional[str] = None) -> List[RetrievedRule]:
    """Module-level convenience wrapper around the singleton retriever."""
    return get_retriever().retrieve(query, top_k=top_k, service=service)
