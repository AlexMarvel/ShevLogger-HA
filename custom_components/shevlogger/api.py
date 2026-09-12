"""Small asynchronous client for the local ShevLogger API."""

from __future__ import annotations

import asyncio
import json as json_module
import logging
from typing import Any
from urllib.parse import urlsplit

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout

from .const import (
    HTTP_REQUEST_ATTEMPTS,
    HTTP_REQUEST_TIMEOUT_SECONDS,
    HTTP_RETRY_DELAY_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


class ShevLoggerError(Exception):
    """Base API error."""


class ShevLoggerAuthError(ShevLoggerError):
    """An authorization failure with a safe, translatable reason."""

    def __init__(self, status: int, reason: str = "auth_rejected") -> None:
        messages = {
            "invalid_auth": "LAN access token does not match the gateway",
            "missing_bearer": "Gateway did not receive a Bearer authorization header",
            "auth_rejected": "LAN authorization rejected; check the gateway address and token",
        }
        self.reason = reason if reason in messages else "auth_rejected"
        super().__init__(f"{messages[self.reason]} (HTTP {status})")


class ShevLoggerConnectionError(ShevLoggerError):
    """The gateway cannot be reached or returned malformed data."""


def normalize_host(value: str) -> str:
    """Return only the hostname or IP entered by the user/discovery flow."""
    raw = value.strip()
    parsed = urlsplit(raw if "://" in raw else f"http://{raw}")
    if (
        not parsed.hostname
        or parsed.scheme != "http"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 80)
        or parsed.netloc.endswith(":")
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or any(char.isspace() for char in parsed.hostname)
        or ":" in parsed.hostname
    ):
        raise ValueError("invalid host")
    return parsed.hostname


class ShevLoggerApi:
    """Client that performs one HTTP request per method call."""

    def __init__(self, session: ClientSession, host: str, token: str) -> None:
        self._session = session
        self.host = normalize_host(host)
        self._token = token.strip()
        self._base_url = f"http://{self.host}/api/v1"

    async def _json(
        self,
        path: str,
        *,
        method: str = "GET",
        json: dict[str, Any] | None = None,
        require_api_version: bool = True,
    ) -> dict[str, Any]:
        last_error: ShevLoggerConnectionError | None = None
        for attempt in range(HTTP_REQUEST_ATTEMPTS):
            try:
                return await self._json_once(
                    path,
                    method=method,
                    json=json,
                    require_api_version=require_api_version,
                )
            except ShevLoggerAuthError:
                raise
            except ShevLoggerConnectionError as error:
                last_error = error
                if attempt + 1 < HTTP_REQUEST_ATTEMPTS:
                    await asyncio.sleep(HTTP_RETRY_DELAY_SECONDS)

        assert last_error is not None
        raise last_error

    async def _json_once(
        self,
        path: str,
        *,
        method: str = "GET",
        json: dict[str, Any] | None = None,
        require_api_version: bool = True,
    ) -> dict[str, Any]:
        try:
            async with self._session.request(
                method,
                f"{self._base_url}/{path}",
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=ClientTimeout(total=HTTP_REQUEST_TIMEOUT_SECONDS),
                json=json,
                allow_redirects=False,
            ) as response:
                await self._raise_for_status(response)
                raw_payload = await response.read()
                try:
                    text_payload = raw_payload.decode("utf-8")
                except UnicodeDecodeError as error:
                    # Older firmware could expose one malformed byte from a
                    # profile label and make Home Assistant retry forever.
                    # Preserve the JSON structure and replace only that bad
                    # display character; numeric values remain untouched.
                    _LOGGER.warning(
                        "ShevLogger returned invalid UTF-8 at byte %s; "
                        "replacing the malformed display character",
                        error.start,
                    )
                    text_payload = raw_payload.decode("utf-8", errors="replace")
                payload = json_module.loads(text_payload)
        except ShevLoggerError:
            raise
        except (ClientError, TimeoutError, ValueError, TypeError) as error:
            raise ShevLoggerConnectionError(str(error)) from error

        if not isinstance(payload, dict) or (
            require_api_version and payload.get("apiVersion") != 1
        ):
            raise ShevLoggerConnectionError("Unsupported ShevLogger API response")
        return payload

    @staticmethod
    async def _raise_for_status(response: ClientResponse) -> None:
        if response.status in (401, 403):
            raw = await response.read()
            reason = "auth_rejected"
            try:
                payload = json_module.loads(raw) if len(raw) <= 4096 else None
            except (ValueError, UnicodeDecodeError):
                payload = None
            # Never include arbitrary response text (or credentials) in errors.
            if isinstance(payload, dict):
                if payload.get("error") == "credential_mismatch":
                    reason = "invalid_auth"
                elif payload.get("error") == "missing_bearer":
                    reason = "missing_bearer"
            raise ShevLoggerAuthError(response.status, reason)
        if 300 <= response.status < 400:
            await response.read()
            raise ShevLoggerConnectionError(
                "HTTP redirect refused; check the gateway address"
            )
        if response.status >= 400:
            await response.read()
            raise ShevLoggerConnectionError(f"HTTP {response.status}")

    async def async_get_schema(self) -> dict[str, Any]:
        entities: list[dict[str, Any]] = []
        cursor = 0
        first_page: dict[str, Any] | None = None
        # Firmware pages keep the ESP32 JSON document bounded. The hard limit
        # also prevents a broken device from creating an infinite setup loop.
        for _ in range(16):
            page = await self._json(f"schema?cursor={cursor}")
            if first_page is None:
                first_page = page
            elif page.get("metaRevision") != first_page.get("metaRevision"):
                raise ShevLoggerConnectionError("Profile changed during setup")

            page_entities = page.get("entities")
            if not isinstance(page_entities, list):
                raise ShevLoggerConnectionError("Invalid entity catalogue")
            entities.extend(item for item in page_entities if isinstance(item, dict))
            if page.get("done") is True:
                result = dict(first_page)
                result["entities"] = entities
                return result

            next_cursor = page.get("nextCursor")
            if not isinstance(next_cursor, int) or next_cursor <= cursor:
                raise ShevLoggerConnectionError("Invalid entity cursor")
            cursor = next_cursor

        raise ShevLoggerConnectionError("Entity catalogue is too large")

    async def async_get_state(self) -> dict[str, Any]:
        """Return the same canonical state document used by the mobile app."""
        return await self._json("state")

    async def async_write(self, key: str, value: int | float) -> dict[str, Any]:
        """Write one profile parameter directly to the inverter."""
        payload = await self._json(
            "write",
            method="POST",
            json={"key": key, "value": value},
            require_api_version=False,
        )
        if payload.get("ok") is not True:
            raise ShevLoggerConnectionError(
                str(payload.get("error") or "The inverter rejected the value")
            )
        return payload
