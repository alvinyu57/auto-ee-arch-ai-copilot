import json

import httpx
import pytest

from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.rag.errors import ConfigurationError, InvalidModelResponse, ProviderError
from ee_arch_copilot.rag.generation.answer_generator import AnswerGenerator, CompatibleLLMProvider
from ee_arch_copilot.rag.generation.prompts import SYSTEM_PROMPT, evidence_message
from ee_arch_copilot.rag.models import AskRequest, GenerationOptions
from ee_arch_copilot.rag.service import KnowledgeService
from tests.rag.conftest import ControlledLLM


def test_grounded_answer(indexed: KnowledgeService) -> None:
    answer = indexed.ask(AskRequest(question="REQ-ETH-001"))
    assert answer.evidence_status == "cited"
    assert answer.referenced_requirement_ids == ["REQ-ETH-001"]
    assert answer.citations[0].quote in answer.answer
    assert indexed.store.get_chunk(answer.citations[0].chunk_id) is not None


def test_no_evidence_skips_provider() -> None:
    provider = ControlledLLM()
    answer = AnswerGenerator(provider).answer("battery", [])
    assert answer.evidence_status == "insufficient"
    assert answer.citations == [] and provider.calls == 0
    with pytest.raises(ConfigurationError):
        AnswerGenerator(None).answer("battery", [])


@pytest.mark.parametrize("raw", ["not JSON", "{}", '{"answer":"x","citation_ids":"S1"}'])
def test_malformed_model_response(indexed: KnowledgeService, raw: str) -> None:
    with pytest.raises(InvalidModelResponse):
        AnswerGenerator(ControlledLLM(raw)).answer("gateway", indexed.store.chunks())


def test_http_llm_contract_and_untrusted_context(indexed: KnowledgeService) -> None:
    chunks = indexed.store.chunks()

    def handle(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content)
        assert data["model"] == "local-test-model"
        assert data["response_format"] == {"type": "json_object"}
        assert data["messages"][0]["content"] == SYSTEM_PROMPT
        assert "untrusted_evidence" in data["messages"][1]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"answer": "Supported excerpt [S1]", "citation_ids": ["S1"]}
                            )
                        }
                    }
                ]
            },
        )

    provider = CompatibleLLMProvider(
        Settings(llm_model="local-test-model"), httpx.MockTransport(handle)
    )
    answer = AnswerGenerator(provider).answer("gateway", chunks)
    assert answer.evidence_status == "cited" and answer.model == "local-test-model"
    assert (
        json.loads(evidence_message("question", chunks))["untrusted_evidence"][0]["text"]
        == chunks[0].text
    )
    assert "Never invent" in SYSTEM_PROMPT and "untrusted data" in SYSTEM_PROMPT
    with pytest.raises(ConfigurationError):
        CompatibleLLMProvider(Settings())


@pytest.mark.parametrize(
    "payload",
    [{}, {"choices": []}, {"choices": [{"message": {}}]}, {"choices": [{"message": "text"}]}],
)
def test_malformed_choices(indexed: KnowledgeService, payload: object) -> None:
    provider = CompatibleLLMProvider(
        Settings(llm_model="test"),
        httpx.MockTransport(lambda request: httpx.Response(200, json=payload)),
    )
    with pytest.raises(InvalidModelResponse):
        provider.generate("gateway", indexed.store.chunks(), GenerationOptions())


@pytest.mark.parametrize("status", [401, 429, 500])
def test_http_provider_failures(indexed: KnowledgeService, status: int) -> None:
    provider = CompatibleLLMProvider(
        Settings(llm_model="test"),
        httpx.MockTransport(
            lambda request: httpx.Response(status, text="credential must not be echoed")
        ),
    )
    with pytest.raises(ProviderError, match="Configured provider request failed") as error:
        provider.generate("gateway", indexed.store.chunks(), GenerationOptions())
    assert "credential" not in str(error.value)


def test_invalid_http_json(indexed: KnowledgeService) -> None:
    for body in ("not-json", "[]"):
        provider = CompatibleLLMProvider(
            Settings(llm_model="test"),
            httpx.MockTransport(lambda request, text=body: httpx.Response(200, text=text)),
        )
        with pytest.raises(ProviderError):
            provider.generate("gateway", indexed.store.chunks(), GenerationOptions())
