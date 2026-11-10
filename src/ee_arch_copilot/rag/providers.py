"""Small HTTP boundary shared by the two independent provider adapters."""

from typing import cast

import httpx
from pydantic import JsonValue, SecretStr

from ee_arch_copilot.rag.errors import ProviderError


def post_json(
    base_url: str,
    endpoint: str,
    payload: dict[str, JsonValue],
    api_key: SecretStr | None,
    timeout: float,
    transport: httpx.BaseTransport | None,
) -> dict[str, JsonValue]:
    headers = {"Authorization": f"Bearer {api_key.get_secret_value()}"} if api_key else {}
    try:
        with httpx.Client(timeout=timeout, transport=transport, follow_redirects=False) as client:
            response = client.post(base_url.rstrip("/") + endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Expected object")
        return cast(dict[str, JsonValue], data)
    except (httpx.HTTPError, ValueError) as error:
        raise ProviderError(
            "Configured provider request failed or returned invalid JSON"
        ) from error
