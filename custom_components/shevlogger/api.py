"""Small asynchronous client for the local ShevLogger API."""

from __future__ import annotations

import json as json_module
import logging
from typing import Any
from urllib.parse import urlsplit

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout

_LOGGER = logging.getLogger(__name__)


class ShevLoggerError(Exception):
    """Base API error."""


class ShevLoggerAuthError(ShevLoggerError):
    """The logger rejected the activation key."""


class ShevLoggerConnectionError(ShevLoggerError):
    """The logger cannot be reached or returned malformed data."""


def normalize_host(value: str) -> str:
    """Return only the hostname or IP entered by the user/discovery flow."""
    raw = value.strip().rstrip("/")
    parsed = urlsplit(raw if "://" in raw else f"http://{raw}")
    if not parsed.hostname:
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
        try:
            async with self._session.request(
                method,
                f"{self._base_url}/{path}",
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=ClientTimeout(total=5),
                json=json,
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
            await response.read()
            raise ShevLoggerAuthError("Invalid activation key")
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
