"""Typed allowlist; arguments and results cross this boundary for every execution."""

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from typing import cast
from uuid import uuid4

from pydantic import BaseModel, JsonValue, ValidationError

from ee_arch_copilot.agent.models import ToolExecution
from ee_arch_copilot.agent.policies import AgentPolicy
from ee_arch_copilot.agent.tools.adapters import (
    EngineeringTools,
    PathArguments,
    SearchArguments,
    TopologyArguments,
    ValidationArguments,
)
from ee_arch_copilot.services.topology import UnknownDeviceError


def json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()


@dataclass(frozen=True)
class ToolDefinition[Args: BaseModel, Result: BaseModel]:
    name: str
    description: str
    arguments: type[Args]
    result: type[Result]
    handler: Callable[[Args], Result]
    timeout_seconds: float
    read_only: bool = True

    def invoke(self, arguments: BaseModel) -> BaseModel:
        return self.result.model_validate(self.handler(cast(Args, arguments)).model_dump())

    def specification(self) -> dict[str, JsonValue]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.arguments.model_json_schema(),
                # Optional defaults are supported by compatible servers; strict validation
                # is performed locally rather than claiming OpenAI strict-schema mode.
                "strict": False,
            },
        }


@dataclass
class ToolOutcome:
    execution: ToolExecution
    payload: BaseModel | None = None


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition[BaseModel, BaseModel]] = {}

    def register[Args: BaseModel, Result: BaseModel](
        self, tool: ToolDefinition[Args, Result]
    ) -> None:
        if tool.name in self._tools or not tool.read_only or tool.timeout_seconds <= 0:
            raise ValueError("Tool must be unique, read-only, and have a positive timeout")
        self._tools[tool.name] = cast(ToolDefinition[BaseModel, BaseModel], tool)

    def specifications(self) -> list[dict[str, JsonValue]]:
        return [tool.specification() for tool in self._tools.values()]

    async def execute(
        self, name: str, arguments: str, call_id: str, policy: AgentPolicy, remaining: float
    ) -> ToolOutcome:
        started = monotonic()
        execution = ToolExecution(
            execution_id=uuid4().hex,
            tool_call_id=call_id,
            tool_name=name if name in self._tools else "unregistered",
            status="REJECTED",
            duration_ms=0,
        )
        outcome = ToolOutcome(execution)
        try:
            tool = self._tools.get(name)
            if tool is None:
                execution.error_code = "unknown_tool"
            elif len(arguments.encode()) > policy.max_argument_bytes:
                execution.error_code = "argument_size_limit"
            else:
                parsed = tool.arguments.model_validate_json(arguments, strict=True)
                execution.arguments_valid = True
                payload = await asyncio.wait_for(
                    asyncio.to_thread(tool.invoke, parsed),
                    timeout=min(tool.timeout_seconds, policy.tool_timeout_seconds, remaining),
                )
                size = len(json_bytes(payload.model_dump(mode="json")))
                if size > policy.max_tool_result_bytes:
                    execution.status, execution.error_code = "LIMIT", "tool_result_size_limit"
                else:
                    outcome.payload = payload
                    execution.status, execution.result_bytes = "SUCCEEDED", size
        except ValidationError:
            execution.error_code = "invalid_arguments_or_result"
        except TimeoutError:
            execution.status, execution.error_code = "TIMEOUT", "tool_timeout"
        except UnknownDeviceError:
            execution.arguments_valid = False
            execution.status, execution.error_code = "ERROR", "unknown_device"
        except ValueError as error:
            if str(error) == "document_scope_denied":
                execution.arguments_valid = False
            execution.status = "ERROR"
            execution.error_code = (
                str(error)
                if str(error) in {"architecture_unavailable", "document_scope_denied"}
                else "tool_failed"
            )
        except Exception:
            # Provider/storage errors may contain sensitive details. Never echo them.
            # CancelledError is a BaseException and deliberately propagates to the caller.
            execution.status, execution.error_code = "ERROR", "tool_failed"
        finally:
            execution.duration_ms = (monotonic() - started) * 1000
        return outcome


def engineering_registry(tools: EngineeringTools, timeout_seconds: float) -> ToolRegistry:
    # Explicit registration only. No reflection, imports, eval, shell, URLs, or write tools.
    from ee_arch_copilot.agent.tools.adapters import (
        PathResult,
        TopologyResult,
        ValidationResult,
    )
    from ee_arch_copilot.rag.models import SearchResponse

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            "search_requirements",
            "Hybrid retrieval of indexed requirements and source citations; no answer generation. "
            "Document filters only narrow authorized scope. Empty hits mean no retrieved evidence.",
            SearchArguments,
            SearchResponse,
            tools.search,
            timeout_seconds,
        )
    )
    registry.register(
        ToolDefinition(
            "get_architecture_topology",
            "Inspect the request architecture's physical device IDs, names, links and components. "
            "Use this to discover endpoint IDs. Bounded output; no VLAN or service analysis.",
            TopologyArguments,
            TopologyResult,
            tools.topology,
            timeout_seconds,
        )
    )
    registry.register(
        ToolDefinition(
            "find_physical_path",
            "Find one physical path between exact device IDs in the request architecture. "
            "Does not establish traffic routing, VLAN, IP, TSN or application reachability.",
            PathArguments,
            PathResult,
            tools.path,
            timeout_seconds,
        )
    )
    registry.register(
        ToolDefinition(
            "validate_architecture",
            "Run the existing deterministic validator on the request architecture. Preserves "
            "PASS/FAIL/NOT_EVALUATED, rule IDs, requirement IDs, components and evidence. "
            "Only supported structured constraints and declared traffic are assessed.",
            ValidationArguments,
            ValidationResult,
            tools.validate,
            timeout_seconds,
        )
    )
    return registry
