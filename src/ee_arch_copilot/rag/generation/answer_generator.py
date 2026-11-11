from typing import Protocol

import httpx
from pydantic import ValidationError

from ee_arch_copilot.core.settings import DEFAULT_REQUIREMENT_PATTERN, Settings
from ee_arch_copilot.rag.errors import ConfigurationError, InvalidModelResponse
from ee_arch_copilot.rag.generation.citations import insufficient_response, validate_answer
from ee_arch_copilot.rag.generation.prompts import SYSTEM_PROMPT, evidence_message
from ee_arch_copilot.rag.models import AnswerResponse, Chunk, GenerationOptions, ModelAnswer
from ee_arch_copilot.rag.providers import post_json


class LLMProvider(Protocol):
    @property
    def model(self) -> str: ...

    def generate(self, question: str, chunks: list[Chunk], options: GenerationOptions) -> str: ...


class CompatibleLLMProvider:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        if not settings.llm_model:
            raise ConfigurationError("Configure LLM_MODEL before enabling answer generation")
        self.settings, self.transport, self.model = settings, transport, settings.llm_model

    def generate(self, question: str, chunks: list[Chunk], options: GenerationOptions) -> str:
        data = post_json(
            self.settings.llm_base_url,
            "/chat/completions",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": evidence_message(question, chunks)},
                ],
                "temperature": options.temperature,
                "max_tokens": options.max_tokens,
                "response_format": {"type": "json_object"},
            },
            self.settings.llm_api_key,
            self.settings.provider_timeout_seconds,
            self.transport,
        )
        try:
            choices = data["choices"]
            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                raise ValueError("Missing choices")
            message = choices[0]["message"]
            if not isinstance(message, dict) or not isinstance(message.get("content"), str):
                raise ValueError("Missing content")
            return str(message["content"])
        except (KeyError, ValueError, TypeError) as error:
            raise InvalidModelResponse("LLM provider returned malformed choices") from error


class AnswerGenerator:
    def __init__(
        self, provider: LLMProvider | None, requirement_pattern: str = DEFAULT_REQUIREMENT_PATTERN
    ) -> None:
        self.provider, self.requirement_pattern = provider, requirement_pattern

    def answer(
        self,
        question: str,
        chunks: list[Chunk],
        options: GenerationOptions | None = None,
    ) -> AnswerResponse:
        if self.provider is None:
            raise ConfigurationError("Answer generation requires a configured real LLM provider")
        if not chunks:
            return insufficient_response(self.provider.model)
        raw = self.provider.generate(question, chunks, options or GenerationOptions())
        try:
            response = ModelAnswer.model_validate_json(raw)
        except ValidationError as error:
            raise InvalidModelResponse(
                "LLM did not return the structured answer contract"
            ) from error
        return validate_answer(response, chunks, self.provider.model, self.requirement_pattern)
