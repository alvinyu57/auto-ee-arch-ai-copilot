"""Explicitly injected test provider; never selectable through production settings.

Scripts implement the native model protocol. They do not execute engineering tools or
replace orchestration. Callbacks can inspect real tool messages before replying.
"""

import json
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy

from pydantic import JsonValue

from ee_arch_copilot.agent.providers import FunctionCall, ProviderReply, ToolCall
from ee_arch_copilot.rag.errors import InvalidModelResponse

type Messages = list[dict[str, JsonValue]]
type ScriptStep = ProviderReply | Callable[[Messages], ProviderReply]


class ScriptedProvider:
    model = "scripted-offline-only"

    def __init__(self, responses: Sequence[ScriptStep]) -> None:
        self.responses = list(responses)
        self.histories: list[Messages] = []
        self.specifications: list[list[dict[str, JsonValue]]] = []

    async def complete(
        self, messages: Messages, tools: list[dict[str, JsonValue]]
    ) -> ProviderReply:
        index = len(self.histories)
        self.histories.append(deepcopy(messages))
        self.specifications.append(deepcopy(tools))
        if index >= len(self.responses):
            raise InvalidModelResponse("Script exhausted")
        step = self.responses[index]
        return step(messages) if callable(step) else step.model_copy(deep=True)


def tool_reply(name: str, arguments: Mapping[str, JsonValue], call_id: str) -> ProviderReply:
    return ProviderReply(
        tool_calls=[
            ToolCall(
                id=call_id,
                function=FunctionCall(name=name, arguments=json.dumps(arguments)),
            )
        ]
    )


def referenced_final(messages: Messages) -> ProviderReply:
    """Protocol fixture, reading evidence labels from the actual registry results."""
    references: list[str] = []
    for message in messages:
        if message["role"] == "tool" and isinstance(message.get("content"), str):
            payload = json.loads(str(message["content"]))
            references.extend(
                item["evidence_id"] for item in payload.get("evidence_references", [])
            )
    references = list(dict.fromkeys(references))
    return ProviderReply(
        content=json.dumps(
            {
                "summary": "Collected engineering evidence is available for review.",
                "findings": [
                    {
                        "description": "Review source and computation evidence within its scope.",
                        "finding_type": "interpretation",
                        "evidence_references": references,
                    }
                ]
                if references
                else [],
                "recommendations": [
                    {
                        "description": "Review unsupported constraints and supply missing inputs.",
                        "finding_type": "recommendation",
                        "evidence_references": references,
                    }
                ],
                "unresolved_questions": []
                if references
                else ["Which source documents or architecture should be supplied?"],
                "insufficient_evidence": not references,
            }
        )
    )
