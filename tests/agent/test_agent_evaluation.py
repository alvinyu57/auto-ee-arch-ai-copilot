import json
import sys
from pathlib import Path

import pytest

from ee_arch_copilot.agent import evaluation
from ee_arch_copilot.agent.evaluation import (
    aggregate,
    architecture_variant,
    evaluate,
    load_corpus,
    load_tasks,
    score_case,
)
from ee_arch_copilot.agent.models import AgentResponse
from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.domain.models import Architecture
from ee_arch_copilot.rag.errors import ConfigurationError
from ee_arch_copilot.rag.service import KnowledgeService
from ee_arch_copilot.services.validator import FindingStatus

DATASET = Path("data/evaluation/agent_tasks.json")


@pytest.mark.anyio
async def test_all_synthetic_acceptance_scenarios(
    agent_settings: Settings,
    agent_knowledge: KnowledgeService,
    sample: Architecture,
) -> None:
    load_corpus(agent_knowledge, Path.cwd())
    tasks = load_tasks(DATASET)
    assert len(tasks) >= 20
    report, responses = await evaluate(tasks, agent_knowledge, sample, agent_settings)
    assert report["mode"] == "scripted"
    assert report["task_completion_rate"] == 1
    assert report["evidence_integrity"] == 1 and report["engineering_status_preservation"] == 1
    assert report["engineering_status_cases"] == 6
    assert report["tool_selection_accuracy"] == pytest.approx(21 / 24)
    assert report["tool_argument_validity"] == pytest.approx(28 / 32)
    assert report["total_input_tokens"] is None and report["estimated_cost_usd"] is None
    by_id = {task.task_id: response for task, response in zip(tasks, responses, strict=True)}
    parallel = next(
        record.data["path"] for record in by_id["B04"].evidence if record.kind == "physical_path"
    )
    assert isinstance(parallel, dict) and parallel["link_ids"] == ["parallel-1"]
    # Negative controls: membership alone cannot make tampered evidence or statuses pass.
    case = tasks[0]
    tampered = by_id[case.task_id].model_copy(deep=True)
    tampered.citations[0].document_version = "invented-version"
    score = score_case(case, tampered, None, agent_knowledge)
    assert not score.evidence_integrity and not score.task_completed
    tampered = by_id["C02"].model_copy(deep=True)
    finding = next(
        item for item in tampered.findings if item.validation and item.validation.status == "FAIL"
    )
    assert finding.validation is not None
    finding.validation.status = FindingStatus.PASS
    task = next(task for task in tasks if task.task_id == "C02")
    score = score_case(task, tampered, architecture_variant(sample, "overload"), agent_knowledge)
    assert not score.engineering_status_preserved and not score.task_completed
    tampered = by_id["B01"].model_copy(deep=True)
    tampered.evidence[0].data["path"] = {"exists": False}
    score = score_case(tasks[3], tampered, sample, agent_knowledge)
    assert not score.evidence_integrity and not score.task_completed
    # Accepted sets are order independent and permit discovery before a path query.
    path_score = score_case(tasks[3], by_id["B01"], sample, agent_knowledge)
    assert path_score.tool_selection_correct


def test_cli_saves_measured_report_and_demo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report, demo = tmp_path / "report.json", tmp_path / "demo.json"
    monkeypatch.setattr(
        sys, "argv", ["agent-evaluation", "--output", str(report), "--demo-output", str(demo)]
    )
    evaluation.main()
    data = json.loads(report.read_text())
    assert data["mode"] == "scripted" and data["task_completion_rate"] == 1
    response = AgentResponse.model_validate_json(demo.read_text())
    assert response.citations and any(item.validation for item in response.findings)


def test_evaluation_rejects_empty_duplicates_and_failed_gold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError):
        aggregate([], "scripted")
    path = tmp_path / "tasks.json"
    task = load_tasks(DATASET)[0]
    for data in [[], [task.model_dump(), task.model_dump()]]:
        path.write_text(json.dumps(data))
        with pytest.raises(ValueError):
            load_tasks(path)
    task.required_requirement_ids = ["REQ-INVENTED-999"]
    path.write_text(json.dumps([task.model_dump()]))
    monkeypatch.setattr(
        sys,
        "argv",
        ["agent-evaluation", "--dataset", str(path), "--output", str(tmp_path / "failed.json")],
    )
    with pytest.raises(SystemExit, match="1"):
        evaluation.main()
    assert json.loads((tmp_path / "failed.json").read_text())["task_completion_rate"] == 0


def test_live_cli_requires_explicit_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGENT_PROVIDER", "none")
    monkeypatch.setattr(
        sys, "argv", ["agent-evaluation", "--live", "--output", str(tmp_path / "live.json")]
    )
    with pytest.raises(ConfigurationError):
        evaluation.main()
    assert not (tmp_path / "live.json").exists()
