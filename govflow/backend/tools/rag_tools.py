"""RAG retrieval tool. Thin wrapper over backend.rag.retriever."""

from __future__ import annotations

from backend.rag.retriever import retrieve
from backend.tools.registry import register_tool
from backend.tools.schemas import RetrieveRulesInput, RetrieveRulesResult


@register_tool(
    "retrieve_rules",
    RetrieveRulesInput,
    RetrieveRulesResult,
    description="Retrieves applicable knowledge-base rules for a query, optionally filtered by service.",
    rate_limited=False,
)
def retrieve_rules(data: RetrieveRulesInput) -> RetrieveRulesResult:
    rules = retrieve(data.query, top_k=data.top_k, service=data.service)
    return RetrieveRulesResult(rules=rules)
