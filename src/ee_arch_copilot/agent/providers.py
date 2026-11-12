"""Native Responses and Chat Completions calling over the shared HTTP boundary."""

from typing import Annotated, Literal, Protocol, cast

import httpx
from pydantic import Field, JsonValue, ValidationError

from ee_arch_copilot.agent.models import ModelFinal
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
    # Replayed verbatim for stateless reasoning/tool continuation; never returned or logged.
    native_output: list[dict[str, JsonValue]] = Field(default_factory=list)

    def message(self) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            result["tool_calls"] = [call.model_dump(mode="json") for call in self.tool_calls]
        if self.native_output:
            result["response_output"] = list(self.native_output)
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
        self.api_mode = settings.agent_api_mode
        if self.api_mode == "auto":
            self.api_mode = "responses" if endpoint.host == "api.openai.com" else "chat_completions"

    async def complete(
        self, messages: list[dict[str, JsonValue]], tools: list[dict[str, JsonValue]]
    ) -> ProviderReply:
        if self.api_mode == "responses":
            return await self._complete_responses(messages, tools)
        return await self._complete_chat(messages, tools)

    async def _complete_chat(
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

    @staticmethod
    def _response_input(messages: list[dict[str, JsonValue]]) -> list[dict[str, JsonValue]]:
        history: list[dict[str, JsonValue]] = []
        for message in messages:
            native = message.get("response_output")
            if message["role"] == "assistant" and native is not None:
                if not isinstance(native, list) or any(
                    not isinstance(item, dict) for item in native
                ):
                    raise InvalidModelResponse("Invalid native continuation history")
                history.extend(cast(list[dict[str, JsonValue]], native))
            elif message["role"] == "tool":
                history.append(
                    {
                        "type": "function_call_output",
                        "call_id": message["tool_call_id"],
                        "output": message["content"],
                    }
                )
            else:
                content = message.get("content")
                if content is not None:
                    history.append({"role": message["role"], "content": content})
                calls = message.get("tool_calls", [])
                if not isinstance(calls, list):
                    raise InvalidModelResponse("Invalid function-call history")
                for raw in calls:
                    call = ToolCall.model_validate(raw)
                    history.append(
                        {
                            "type": "function_call",
                            "call_id": call.id,
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        }
                    )
        return history

    async def _complete_responses(
        self, messages: list[dict[str, JsonValue]], tools: list[dict[str, JsonValue]]
    ) -> ProviderReply:
        definitions: list[dict[str, JsonValue]] = []
        for tool in tools:
            function = tool.get("function")
            if tool.get("type") != "function" or not isinstance(function, dict):
                raise InvalidModelResponse("Only explicit function definitions are supported")
            definitions.append({"type": "function", **function})
        data = await post_json_async(
            self.settings.llm_base_url,
            "/responses",
            {
                "model": self.model,
                "input": list(self._response_input(messages)),
                "tools": list(definitions),
                "tool_choice": "auto",
                "store": False,
                "include": ["reasoning.encrypted_content"],
                "max_output_tokens": self.settings.agent_max_output_tokens,
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "agent_final",
                        "schema": ModelFinal.model_json_schema(),
                        "strict": True,
                    }
                },
            },
            self.settings.llm_api_key,
            self.settings.provider_timeout_seconds,
            self.transport,
            self.settings.agent_max_provider_response_bytes,
        )
        try:
            if data.get("status") != "completed":
                raise ValueError("Provider response incomplete or failed")
            output = data["output"]
            if not isinstance(output, list) or any(not isinstance(item, dict) for item in output):
                raise ValueError("Missing native output items")
            native = cast(list[dict[str, JsonValue]], output)
            calls: list[ToolCall] = []
            texts: list[str] = []
            for item in native:
                if item["type"] == "function_call":
                    if item.get("status", "completed") != "completed":
                        raise ValueError("Incomplete function call")
                    calls.append(
                        ToolCall.model_validate(
                            {
                                "id": item["call_id"],
                                "function": {
                                    "name": item["name"],
                                    "arguments": item["arguments"],
                                },
                            }
                        )
                    )
                elif item["type"] == "message":
                    if item.get("role") != "assistant" or not isinstance(item.get("content"), list):
                        raise ValueError("Invalid assistant output")
                    for part in cast(list[JsonValue], item["content"]):
                        if (
                            not isinstance(part, dict)
                            or part.get("type") != "output_text"
                            or not isinstance(part.get("text"), str)
                        ):
                            raise ValueError("Refusal or invalid output text")
                        texts.append(str(part["text"]))
                elif item["type"] != "reasoning":
                    raise ValueError("Unsupported provider output type")
            usage = data.get("usage")
            tokens = None
            if usage is not None:
                if not isinstance(usage, dict):
                    raise ValueError("Malformed token usage")
                tokens = TokenUsage.model_validate(
                    {
                        "input_tokens": usage["input_tokens"],
                        "output_tokens": usage["output_tokens"],
                    }
                )
            if not calls and not texts:
                raise ValueError("Empty provider response")
            return ProviderReply(
                content="".join(texts) or None,
                tool_calls=calls,
                usage=tokens,
                native_output=native,
            )
        except (KeyError, ValueError, TypeError) as error:
            raise InvalidModelResponse("Malformed native Responses API response") from error
