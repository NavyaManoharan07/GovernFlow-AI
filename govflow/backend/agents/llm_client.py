"""Shared Gemini wrapper. Every agent that calls Gemini goes through this.

Uses the `google-genai` SDK (the current unified Google GenAI SDK --
`from google import genai`), NOT the older `google-generativeai` package
and NOT the Google ADK agent framework. See the module docstring at the
bottom of this file for why.

Every call requests structured JSON output via response_schema (a Pydantic
model passed directly -- the SDK converts it to a JSON schema for the API
and parses the response back into an instance of that same model) and
validates the result. If the SDK's automatic parsing comes back empty for
any reason, this falls back to manually parsing response.text as JSON and
validating it against the Pydantic model by hand. Either path is retried
up to MAX_RETRIES times on failure. Callers never receive raw text for
anything that drives workflow state -- only a validated Pydantic instance.
"""

from __future__ import annotations

import json
import logging
import os
from typing import List, Optional, Protocol, Type, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger("govflow.agents.llm_client")

T = TypeVar("T", bound=BaseModel)

MAX_RETRIES = 2  # total attempts = MAX_RETRIES + 1, per spec ("max 2 retries")


class LLMClientError(Exception):
    """Raised when a Gemini call fails validation/parsing after all retries."""


class LLMClient(Protocol):
    """Structural interface both GeminiClient and StubGeminiClient satisfy."""

    def generate_structured(
        self,
        system_prompt: str,
        user_content: str,
        response_model: Type[T],
        *,
        temperature: float = 0.2,
    ) -> T: ...


class GeminiClient:
    """Thin wrapper around google-genai's Client, always in structured-output mode."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Set it in .env or the environment before "
                "constructing GeminiClient. For tests, use StubGeminiClient instead."
            )
        # Imported lazily so importing backend.agents.llm_client never requires
        # google-genai to be installed unless a real Gemini call is actually made
        # (tests / offline dev use StubGeminiClient exclusively).
        from google import genai

        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
        self._client = genai.Client(api_key=api_key)

    def generate_structured(
        self,
        system_prompt: str,
        user_content: str,
        response_model: Type[T],
        *,
        temperature: float = 0.2,
    ) -> T:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=response_model,
            temperature=temperature,
        )

        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=user_content,
                    config=config,
                )
                parsed = getattr(response, "parsed", None)
                if isinstance(parsed, response_model):
                    return parsed
                # Fallback: manual JSON parse + validation, in case the SDK's
                # auto-parse didn't produce an instance of our exact model.
                text = response.text
                if not text:
                    raise LLMClientError("Gemini returned an empty response")
                data = json.loads(text)
                return response_model.model_validate(data)
            except (ValidationError, json.JSONDecodeError, LLMClientError) as exc:
                last_error = exc
                logger.warning(
                    "Gemini structured-output attempt %d/%d failed validation for %s: %s",
                    attempt + 1,
                    MAX_RETRIES + 1,
                    response_model.__name__,
                    exc,
                )
            except Exception as exc:  # noqa: BLE001 -- SDK/network errors, retried too
                last_error = exc
                logger.warning(
                    "Gemini call attempt %d/%d raised %s: %s",
                    attempt + 1,
                    MAX_RETRIES + 1,
                    type(exc).__name__,
                    exc,
                )

        raise LLMClientError(
            f"Gemini structured-output call for {response_model.__name__} failed after "
            f"{MAX_RETRIES + 1} attempts: {last_error}"
        )


class StubGeminiClient:
    """Test double. Returns pre-programmed canned responses instead of
    calling the real API. Records every call for assertions."""

    def __init__(
        self,
        responses_by_model: Optional[dict] = None,
        sequence: Optional[List[BaseModel]] = None,
    ) -> None:
        self._responses_by_model = dict(responses_by_model or {})
        self._sequence = list(sequence) if sequence is not None else None
        self.calls: List[dict] = []

    def set_response(self, model: Type[BaseModel] | str, value: BaseModel) -> None:
        """Test ergonomics: register/replace the canned response for a
        given response_model (by class or name) after construction."""
        key = model if isinstance(model, str) else model.__name__
        self._responses_by_model[key] = value

    def generate_structured(
        self,
        system_prompt: str,
        user_content: str,
        response_model: Type[T],
        *,
        temperature: float = 0.2,
    ) -> T:
        self.calls.append(
            {"system_prompt": system_prompt, "user_content": user_content, "response_model": response_model}
        )
        if self._sequence:
            return self._sequence.pop(0)

        key = response_model.__name__
        if key in self._responses_by_model:
            canned = self._responses_by_model[key]
            return canned.pop(0) if isinstance(canned, list) else canned

        raise LLMClientError(
            f"StubGeminiClient has no canned response registered for {key}. "
            f"Pass responses_by_model={{'{key}': <instance or list>}} or call set_response()."
        )


# ---------------------------------------------------------------------------
# Model string note (Part 2 deliverable disclosure)
#
# GEMINI_MODEL defaults to "gemini-3.5-flash" per the task brief ("Gemini
# 3.5 Flash (GA, released May 2026)"). This sandbox has no GEMINI_API_KEY,
# so the model string could NOT be verified live against the
# models.list() endpoint or AI Studio. If the real identifier differs,
# it's a one-line fix: set GEMINI_MODEL in .env -- nothing else in this
# codebase hardcodes the model name.
# ---------------------------------------------------------------------------
