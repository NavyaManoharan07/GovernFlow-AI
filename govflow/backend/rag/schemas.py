from pydantic import BaseModel, Field


class RetrievedRule(BaseModel):
    """One retrieved knowledge-base chunk.

    Confidence is a similarity score in [0, 1] -- not a probability of
    correctness. Callers (RegulationAgent in particular) must treat a
    result list where every confidence is below the retriever's relevance
    floor as "no applicable rule found", not as a rule to report.
    """

    requirement: str
    source: str
    confidence: float = Field(ge=0.0, le=1.0)
