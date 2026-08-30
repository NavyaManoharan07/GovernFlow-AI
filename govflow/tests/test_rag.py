from backend.rag.documents import load_chunks
from backend.rag.retriever import TfidfRetriever, get_retriever, retrieve


def test_load_chunks_parses_requirement_lines():
    chunks = load_chunks()
    assert len(chunks) > 30
    req_chunks = [c for c in chunks if "REQ-" in c.chunk_id]
    assert len(req_chunks) > 20
    food_license_chunks = [c for c in req_chunks if "food_license" in c.service_tags]
    assert len(food_license_chunks) > 0
    # Every requirement chunk must carry a citation, and the citation must
    # be clearly marked as mock/demo data (not something a user could
    # mistake for a real legal source).
    for chunk in req_chunks:
        assert chunk.source
        assert "MOCK" in chunk.source


def test_retrieve_food_license_documents_returns_cited_results():
    results = retrieve("food license documents", top_k=5)
    assert len(results) > 0
    for r in results:
        assert 0.0 <= r.confidence <= 1.0
        assert r.source
        assert r.requirement
    # At least one result should be clearly about food license documentation.
    assert any("food" in r.requirement.lower() or "food" in r.source.lower() for r in results)


def test_retrieve_filtered_by_service_only_returns_relevant_or_general_chunks():
    results = retrieve("what do I need to submit", top_k=10, service="food_license")
    retriever = get_retriever()
    for r in results:
        # Every returned chunk must be tagged either food_license or general
        # -- the filter must not leak chunks tagged for a different specific
        # service (e.g. tax_registration-only chunks).
        matches = [
            c
            for c in retriever._chunks  # noqa: SLF001 -- test introspection only
            if c.text == r.requirement and c.source == r.source
        ]
        assert matches
        assert "food_license" in matches[0].service_tags or "general" in matches[0].service_tags


def test_irrelevant_query_returns_no_hallucinated_results():
    results = retrieve("what is the weather forecast for tomorrow in Paris", top_k=5)
    assert results == []


def test_retriever_never_returns_text_not_in_corpus():
    """Guards against the retriever fabricating content: every returned
    requirement string must be an exact chunk from the knowledge base."""
    chunks = load_chunks()
    corpus_texts = {c.text for c in chunks}
    retriever = TfidfRetriever(chunks)
    for query in ["business registration", "tax tier turnover", "hygiene inspection"]:
        for result in retriever.retrieve(query, top_k=5):
            assert result.requirement in corpus_texts
