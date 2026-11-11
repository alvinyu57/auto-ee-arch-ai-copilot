import json
from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import Payload

pytestmark = pytest.mark.anyio


async def test_health_and_openapi(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0", "phase": 1}
    schema = (await client.get("/openapi.json")).json()
    assert set(schema["paths"]) >= {
        "/health",
        "/api/v1/architectures/validate",
        "/api/v1/architectures/topology",
        "/api/v1/architectures/path",
    }


async def test_validate_sample(client: AsyncClient, sample_payload: Payload) -> None:
    response = await client.post("/api/v1/architectures/validate", json=sample_payload)
    assert response.status_code == 200
    report = response.json()
    assert report["status"] == "NOT_EVALUATED"
    assert not any(item["status"] == "FAIL" for item in report["findings"])
    assert all("evidence" in item for item in report["findings"])


async def test_topology(client: AsyncClient, sample_payload: Payload) -> None:
    response = await client.post("/api/v1/architectures/topology", json=sample_payload)
    assert response.status_code == 200
    topology = response.json()
    assert len(topology["nodes"]) == 7
    assert len(topology["edges"]) == 6
    assert len(topology["connected_components"]) == 1
    assert topology["connectivity_scope"] == "physical"


@pytest.mark.parametrize(("destination", "exists"), [("b", True), ("isolated", False)])
async def test_path(client: AsyncClient, payload: Payload, destination: str, exists: bool) -> None:
    response = await client.post(
        "/api/v1/architectures/path",
        json={
            "architecture": payload,
            "source_device_id": "a",
            "destination_device_id": destination,
        },
    )
    assert response.status_code == 200
    assert response.json()["exists"] is exists
    assert response.json()["connectivity_scope"] == "physical"


async def test_path_unknown_device(client: AsyncClient, payload: Payload) -> None:
    response = await client.post(
        "/api/v1/architectures/path",
        json={"architecture": payload, "source_device_id": "a", "destination_device_id": "missing"},
    )
    assert response.status_code == 404
    assert "Unknown device" in response.json()["detail"]


@pytest.mark.parametrize("endpoint", ["validate", "topology", "path"])
@pytest.mark.parametrize("invalid", ["endpoint", "interface", "provider", "negative"])
async def test_invalid_architecture_client_error(
    client: AsyncClient, payload: Payload, endpoint: str, invalid: str
) -> None:
    if invalid == "endpoint":
        payload["links"][0]["destination"]["device_id"] = "missing"
    elif invalid == "interface":
        payload["links"][0]["destination"]["interface_id"] = "missing"
    elif invalid == "provider":
        payload["services"][0]["provider_ecu_id"] = "missing"
    else:
        payload["services"][0]["bandwidth_requirement_mbps"] = -1
    body: dict[str, Any] = (
        {"architecture": payload, "source_device_id": "a", "destination_device_id": "b"}
        if endpoint == "path"
        else payload
    )
    response = await client.post(f"/api/v1/architectures/{endpoint}", json=body)
    assert response.status_code == 422
    assert response.json()["detail"]


async def test_engineering_failure_is_a_report(client: AsyncClient, payload: Payload) -> None:
    payload["services"][0]["bandwidth_requirement_mbps"] = 120
    response = await client.post("/api/v1/architectures/validate", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "FAIL"


async def test_malformed_json(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/architectures/validate",
        content="{",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


async def test_api_is_stateless(client: AsyncClient, payload: Payload) -> None:
    first = (await client.post("/api/v1/architectures/topology", json=payload)).json()
    payload["id"] = "another"
    payload["ecus"] = []
    payload["links"] = []
    payload["services"] = []
    payload["requirements"] = []
    second = (await client.post("/api/v1/architectures/topology", json=payload)).json()
    assert len(first["nodes"]) == 3
    assert second["nodes"] == []
    assert second["architecture_id"] == "another"


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity", "1e309"])
async def test_nonfinite_json_numbers_are_client_errors(
    client: AsyncClient, payload: Payload, token: str
) -> None:
    payload["services"][0]["bandwidth_requirement_mbps"] = "NONFINITE"
    raw = json.dumps(payload).replace('"NONFINITE"', token)
    response = await client.post(
        "/api/v1/architectures/validate",
        content=raw,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    detail = response.json()["detail"][0]
    assert detail["loc"][:3] == ["body", "services", 0]
    assert detail["type"] == "finite_number"
