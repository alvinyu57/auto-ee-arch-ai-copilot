import json

import httpx
import pytest
from pydantic import SecretStr

from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.rag.embeddings.base import validate_vectors
from ee_arch_copilot.rag.embeddings.providers import (
    CompatibleEmbeddingProvider,
    HashEmbeddingProvider,
    create_embedding_provider,
)
from ee_arch_copilot.rag.errors import ConfigurationError, ProviderError


def test_hash_embeddings_distinct_and_stable() -> None:
    provider = HashEmbeddingProvider()
    gateway, battery = provider.embed_documents(
        ["Gateway Ethernet 1000BASE-T1", "Lithium cathode battery"]
    )
    query = provider.embed_query("Gateway Ethernet")
    assert gateway == provider.embed_query("Gateway Ethernet 1000BASE-T1")
    assert gateway != battery
    assert sum(a * b for a, b in zip(query, gateway, strict=True)) > sum(
        a * b for a, b in zip(query, battery, strict=True)
    )
    assert sum(value * value for value in gateway) == pytest.approx(1)
    assert provider.embed_query("the and") == [0.0] * 384


def test_http_embedding_batch_order_and_auth() -> None:
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-only"
        data = json.loads(request.content)
        calls.append(data)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": index, "embedding": [float(index + 1)] * 32}
                    for index in reversed(range(len(data["input"])))
                ]
            },
        )

    settings = Settings(
        embedding_provider="openai_compatible",
        embedding_model="test-embed",
        embedding_dimension=32,
        embedding_api_key=SecretStr("test-only"),
        embedding_batch_size=2,
    )
    provider = CompatibleEmbeddingProvider(settings, httpx.MockTransport(handle))
    vectors = provider.embed_documents(["a", "b", "c"])
    assert vectors == [[1.0] * 32, [2.0] * 32, [1.0] * 32]
    assert len(calls) == 2
    assert provider.embed_query("a") == [1.0] * 32
    assert provider.identity != HashEmbeddingProvider(32).identity
    assert "test-only" not in repr(settings)
    assert isinstance(create_embedding_provider(settings), CompatibleEmbeddingProvider)
    assert isinstance(create_embedding_provider(Settings()), HashEmbeddingProvider)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"data": [1]},
        {"data": [{"index": 2, "embedding": [1]}]},
        {"data": [{"index": 0, "embedding": "bad"}]},
    ],
)
def test_bad_embedding_response(payload: object) -> None:
    provider = CompatibleEmbeddingProvider(
        Settings(embedding_dimension=32),
        httpx.MockTransport(lambda request: httpx.Response(200, json=payload)),
    )
    with pytest.raises(ProviderError):
        provider.embed_query("gateway")


@pytest.mark.parametrize(
    ("vectors", "count", "dimension"),
    [([], 1, 2), ([[1.0]], 1, 2), ([[0.0, 0.0]], 1, 2), ([[float("nan"), 1.0]], 1, 2)],
)
def test_embedding_validation(vectors: list[list[float]], count: int, dimension: int) -> None:
    with pytest.raises(ProviderError):
        validate_vectors(vectors, count, dimension)


def test_model_configuration() -> None:
    with pytest.raises(ConfigurationError):
        create_embedding_provider(Settings(embedding_model="other"))
    with pytest.raises(ConfigurationError):
        create_embedding_provider(Settings(embedding_provider="openai_compatible"))
