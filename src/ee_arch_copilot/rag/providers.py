"""Small HTTP boundary shared by the two independent provider adapters."""

import json
from typing import cast

import httpx
from pydantic import JsonValue, SecretStr

from ee_arch_copilot.rag.errors import ProviderError


async def post_json_async(
    base_url: str,
    endpoint: str,
    payload: dict[str, JsonValue],
    api_key: SecretStr | None,
    timeout: float,
    transport: httpx.AsyncBaseTransport | None,
    max_response_bytes: int,
) -> dict[str, JsonValue]:
    """Cancellable HTTP with a bounded response, shared by the Phase 3 adapter."""
    headers = {"Authorization": f"Bearer {api_key.get_secret_value()}"} if api_key else {}
    provider_code: str | None = None
    try:
        async with (
            httpx.AsyncClient(
                timeout=timeout, transport=transport, follow_redirects=False
            ) as client,
            client.stream(
                "POST", base_url.rstrip("/") + endpoint, json=payload, headers=headers
            ) as response,
        ):
            body = bytearray()
            async for block in response.aiter_bytes(chunk_size=4096):
                body.extend(block)
                if len(body) > max_response_bytes:
                    raise ValueError("Provider response exceeds size limit")
            if response.is_error:
                try:
                    error_data = json.loads(body)
                    details = error_data.get("error") if isinstance(error_data, dict) else None
                    code = details.get("code") if isinstance(details, dict) else None
                    provider_code = code if isinstance(code, str) else None
                except ValueError:
                    pass
            response.raise_for_status()
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("Expected object")
        return cast(dict[str, JsonValue], data)
    except httpx.HTTPStatusError as error:
        raise ProviderError(
            "Configured provider rejected the request",
            code=provider_code,
            http_status=error.response.status_code,
        ) from error
    except (httpx.HTTPError, ValueError) as error:
        raise ProviderError("Configured provider failed or exceeded response limits") from error


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
