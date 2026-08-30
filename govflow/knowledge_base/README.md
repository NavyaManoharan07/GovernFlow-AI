# Knowledge Base

Populated in Part 2 with MOCK/DEMONSTRATION regulatory documents for the
GovFlow AI hackathon demo. **None of this represents real current law** --
every file is headed "MOCK / DEMONSTRATION DATA — not real current law" and
every requirement cites an invented source (e.g. "Demo Municipal Business
Code §4.2 (MOCK)").

- `business_registration_requirements.md`
- `tax_registration_requirements.md`
- `food_license_requirements.md`
- `eligibility_rules.md`
- `required_documents.md`
- `service_dependencies.md`

Each numbered requirement follows the convention:

```
- REQ-<PREFIX>-<N>: <requirement text> (Service: <service_tag>) (Source: <citation>)
```

`backend/rag/` chunks these files by requirement line and indexes them with
a pure-Python TF-IDF retriever (see `backend/rag/retriever.py`) -- no
external embedding service or model download required, so the demo runs
identically offline. `retrieve_rules()` (backend/tools/rag_tools.py) is the
only sanctioned way agents read this knowledge base; RegulationAgent never
fabricates a requirement that retrieval didn't return.
