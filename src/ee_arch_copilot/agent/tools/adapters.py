"""Thin service adapters. No network graph or engineering rule is implemented here."""

from collections.abc import Callable
from typing import Literal

from pydantic import Field

from ee_arch_copilot.agent.context import AgentContext
from ee_arch_copilot.domain.models.common import DomainModel, Identifier
from ee_arch_copilot.rag.models import SearchFilter, SearchResponse
from ee_arch_copilot.rag.service import KnowledgeService
from ee_arch_copilot.services.topology import (
    PhysicalPath,
    TopologyEdge,
    TopologyRepresentation,
    TopologyService,
)
from ee_arch_copilot.services.validator import ArchitectureValidator, ValidationReport

RuleID = Literal[
    "structure.consistency",
    "connectivity.physical_path",
    "bandwidth.traffic_evaluability",
    "bandwidth.nominal_link_budget",
    "requirement.evaluability",
]


class SearchArguments(DomainModel):
    query: str = Field(min_length=1, max_length=5000)
    top_k: int = Field(default=5, ge=1, le=10, strict=True)
    filters: SearchFilter = Field(default_factory=SearchFilter)


class TopologyArguments(DomainModel):
    max_nodes: int = Field(default=50, ge=1, le=100, strict=True)
    max_links: int = Field(default=50, ge=1, le=100, strict=True)


class TopologyResult(DomainModel):
    topology: TopologyRepresentation
    total_nodes: int
    total_links: int
    truncated: bool


class PathArguments(DomainModel):
    source_device_id: Identifier
    destination_device_id: Identifier


class PathResult(DomainModel):
    path: PhysicalPath
    links: list[TopologyEdge]
    route_note: str = (
        "One minimum-hop physical path; lexicographic link ID selects parallel edges. "
        "Other paths may exist. This is not the configured traffic route."
    )


class ValidationArguments(DomainModel):
    rule_ids: list[RuleID] | None = Field(default=None, min_length=1, max_length=5)


class ValidationResult(DomainModel):
    report: ValidationReport
    selected_rule_ids: list[RuleID] | None
    omitted_findings: int
    scope_note: str = (
        "Report status is the original full validator status. Selected rule filters limit "
        "returned findings, not the validator computation or the meaning of PASS. "
        "Retrieved prose is not automatically converted into reviewed structured constraints."
    )


class EngineeringTools:
    def __init__(self, context: AgentContext, knowledge: Callable[[], KnowledgeService]) -> None:
        self.context, self.knowledge = context, knowledge
        self._service: KnowledgeService | None = None
        self._revisions: dict[str, set[str | None]] = {}

    def search(self, args: SearchArguments) -> SearchResponse:
        filters = self.context.filters(args.filters)
        service = self.knowledge()
        self._service = service
        options = service.settings.retrieval_options().model_copy(
            update={"method": "hybrid", "final_top_k": args.top_k, "filters": filters}
        )
        with service.store.lock:
            result = service.search(args.query, options)
            for hit in result.hits:
                document_id = hit.chunk.document_id
                self._revisions.setdefault(document_id, set()).add(
                    service.store.get_revision(document_id)
                )
            return result

    def evidence_current(self) -> bool:
        if self._service is None:
            return True
        with self._service.store.lock:
            return all(
                revision is not None and self._service.store.is_current(document_id, revision)
                for document_id, revisions in self._revisions.items()
                for revision in revisions
            )

    def topology(self, args: TopologyArguments) -> TopologyResult:
        representation = TopologyService(self.context.require_architecture()).to_representation()
        nodes, links = len(representation.nodes), len(representation.edges)
        truncated = nodes > args.max_nodes or links > args.max_links
        if truncated:
            # Do not emit edges with absent endpoints, or partial components as if complete.
            representation.nodes = representation.nodes[: args.max_nodes]
            shown = {node.id for node in representation.nodes}
            representation.edges = [
                edge
                for edge in representation.edges
                if edge.source.device_id in shown and edge.destination.device_id in shown
            ][: args.max_links]
            representation.isolated_device_ids = [
                node for node in representation.isolated_device_ids if node in shown
            ]
            representation.connected_components = []
            representation.limitations += " Output truncated; connected components withheld."
        return TopologyResult(
            topology=representation, total_nodes=nodes, total_links=links, truncated=truncated
        )

    def path(self, args: PathArguments) -> PathResult:
        service = TopologyService(self.context.require_architecture())
        path = service.find_physical_path(args.source_device_id, args.destination_device_id)
        edges = {edge.id: edge for edge in service.to_representation().edges}
        return PathResult(
            path=path,
            links=[edges[link_id] for link_id in path.link_ids],
        )

    def validate(self, args: ValidationArguments) -> ValidationResult:
        report = ArchitectureValidator().validate(self.context.require_architecture())
        total = len(report.findings)
        if args.rule_ids is not None:
            report.findings = [item for item in report.findings if item.rule_id in args.rule_ids]
        return ValidationResult(
            report=report,
            selected_rule_ids=args.rule_ids,
            omitted_findings=total - len(report.findings),
        )
