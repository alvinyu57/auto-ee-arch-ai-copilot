import json
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, cast

import pytest
from httpx import ASGITransport, AsyncClient

from ee_arch_copilot.core.settings import Settings
from ee_arch_copilot.domain.models import Architecture
from ee_arch_copilot.main import create_app

Payload = dict[str, Any]
EXAMPLES = Path(__file__).resolve().parents[1] / "data" / "examples"


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    # Local unit tests must not use a developer's live credentials, index, or budgets.
    for key in tuple(os.environ):
        if key.casefold() in Settings.model_fields:
            monkeypatch.delenv(key)
    monkeypatch.setitem(Settings.model_config, "env_file", None)


@pytest.fixture
def sample_payload() -> Payload:
    return cast(Payload, json.loads((EXAMPLES / "centralized_architecture.json").read_text()))


@pytest.fixture
def sample(sample_payload: Payload) -> Architecture:
    return Architecture.model_validate(sample_payload)


@pytest.fixture
def payload() -> Payload:
    return {
        "id": "test-architecture",
        "name": "Synthetic test architecture",
        "ecus": [
            {
                "id": name,
                "name": name,
                "ecu_type": "other",
                "interfaces": [{"id": "eth0", "technology": "ethernet", "nominal_speed_mbps": 100}],
            }
            for name in ("a", "b", "isolated")
        ],
        "links": [
            {
                "id": "ab",
                "source": {"device_id": "a", "interface_id": "eth0"},
                "destination": {"device_id": "b", "interface_id": "eth0"},
                "technology": "ethernet",
                "nominal_bandwidth_mbps": 100,
            }
        ],
        "services": [
            {
                "id": "svc",
                "name": "Synthetic stream",
                "provider_ecu_id": "a",
                "consumer_ecu_ids": ["b"],
                "protocol": "SOME/IP",
                "bandwidth_requirement_mbps": 40,
                "traffic_routes": [{"consumer_ecu_id": "b", "link_ids": ["ab"]}],
            }
        ],
        "requirements": [
            {
                "id": "REQ-CONN",
                "description": "Synthetic physical path requirement",
                "requirement_type": "connectivity",
                "constraints": {
                    "kind": "connectivity",
                    "source_device_id": "a",
                    "destination_device_id": "b",
                },
            },
            {
                "id": "REQ-BW",
                "description": "Synthetic nominal budget requirement",
                "requirement_type": "bandwidth",
                "constraints": {"kind": "bandwidth", "link_ids": ["ab"]},
            },
        ],
    }


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as connection:
        yield connection
