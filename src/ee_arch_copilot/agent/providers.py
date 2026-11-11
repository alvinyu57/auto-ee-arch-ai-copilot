"""Native chat/completions function calling over the existing compatible HTTP boundary."""

from typing import Annotated, Literal, Protocol

import httpx
from pydantic import Field, JsonValue, ValidationError

from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.domain.models.common import DomainModel
from ee_arch_copilot.rag.errors import ConfigurationError, InvalidModelResponse
from ee_arch_copilot.rag.providers import post_json_async


class FunctionCall(DomainModel):
    name: Annotated[str, Field(min_length=1, max_length=128)]
    arguments: str


class ToolCall(DomainModel):
    id: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")]
    type: Literal["function"] = "function"
    function: FunctionCall


class TokenUsage(DomainModel):
    input_tokens: int = Field(ge=0, strict=True)
    output_tokens: int = Field(ge=0, strict=True)


class ProviderReply(DomainModel):
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list, max_length=50)
    usage: TokenUsage | None = None

    def message(self) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            result["tool_calls"] = [call.model_dump(mode="json") for call in self.tool_calls]
        return result


class AgentProvider(Protocol):
    @property
    def model(self) -> str: ...

    async def complete(
        self, messages: list[dict[str, JsonValue]], tools: list[dict[str, JsonValue]]
    ) -> ProviderReply: ...


class CompatibleAgentProvider:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings, self.transport = settings, transport
        self.model = settings.agent_model or settings.llm_model
        if settings.agent_provider != "openai_compatible" or not self.model.strip():
            raise ConfigurationError("Configure AGENT_PROVIDER and AGENT_MODEL (or LLM_MODEL)")
        try:
            endpoint = httpx.URL(settings.llm_base_url)
            if endpoint.scheme not in {"http", "https"} or not endpoint.host or endpoint.userinfo:
                raise ValueError("Invalid provider endpoint")
        except (httpx.InvalidURL, ValueError) as error:
            raise ConfigurationError(
                "Configure a trusted HTTP(S) LLM_BASE_URL without credentials"
            ) from error

    async def complete(
        self, messages: list[dict[str, JsonValue]], tools: list[dict[str, JsonValue]]
    ) -> ProviderReply:
        data = await post_json_async(
            self.settings.llm_base_url,
            "/chat/completions",
            {
                "model": self.model,
                "messages": list(messages),
                "tools": list(tools),
                "tool_choice": "auto",
                "response_format": {"type": "json_object"},
                "max_tokens": self.settings.agent_max_output_tokens,
                "store": False,
            },
            self.settings.llm_api_key,
            self.settings.provider_timeout_seconds,
            self.transport,
            self.settings.agent_max_provider_response_bytes,
        )
        try:
            choices = data["choices"]
            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                raise ValueError("Missing choices")
            if choices[0].get("finish_reason") not in {"stop", "tool_calls"}:
                raise ValueError("Incomplete provider reply")
            message = choices[0]["message"]
            if not isinstance(message, dict) or message.get("role") != "assistant":
                raise ValueError("Missing assistant message")
            usage = data.get("usage")
            tokens = None
            if usage is not None:
                if not isinstance(usage, dict):
                    raise ValueError("Malformed usage")
                tokens = TokenUsage.model_validate(
                    {
                        "input_tokens": usage["prompt_tokens"],
                        "output_tokens": usage["completion_tokens"],
                    }
                )
            reply = ProviderReply.model_validate(
                {
                    "content": message.get("content"),
                    "tool_calls": message.get("tool_calls") or [],
                    "usage": tokens,
                }
            )
            if not reply.tool_calls and not reply.content:
                raise ValueError("Empty response or refusal")
            return reply
        except (KeyError, ValueError, TypeError, ValidationError) as error:
            raise InvalidModelResponse("Malformed native tool-calling response") from error
