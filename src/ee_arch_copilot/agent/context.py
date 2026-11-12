"""An owned snapshot, with no filesystem, URL, or architecture-ID resolver."""

from dataclasses import dataclass

from ee_arch_copilot.agent.models import AnalyzeRequest
from ee_arch_copilot.domain.models import Architecture
from ee_arch_copilot.rag.models import SearchFilter


@dataclass(frozen=True)
class AgentContext:
    architecture: Architecture | None
    # A server-injected scope, never supplied by model arguments or HTTP request options.
    document_scope: SearchFilter

    @classmethod
    def from_request(
        cls, request: AnalyzeRequest, document_scope: SearchFilter | None = None
    ) -> "AgentContext":
        return cls(
            Architecture.model_validate(request.architecture.model_dump())
            if request.architecture is not None
            else None,
            SearchFilter.model_validate((document_scope or SearchFilter()).model_dump()),
        )

    def require_architecture(self) -> Architecture:
        if self.architecture is None:
            raise ValueError("architecture_unavailable")
        return self.architecture

    def filters(self, proposed: SearchFilter) -> SearchFilter:
        values = proposed.model_dump()
        for name, required in self.document_scope.model_dump().items():
            if required is not None:
                if values[name] is not None and values[name] != required:
                    raise ValueError("document_scope_denied")
                values[name] = required
        return SearchFilter.model_validate(values)
