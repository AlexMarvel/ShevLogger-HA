"""Config flow for automatic discovery or manual ShevLogger setup."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import (
    ShevLoggerApi,
    ShevLoggerAuthError,
    ShevLoggerConnectionError,
    normalize_host,
)
from .const import CONF_TOKEN, DOMAIN


class ShevLoggerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create a config entry without requiring a fixed logger IP."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered_host: str | None = None
        self._discovered_name: str | None = None

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        properties = discovery_info.properties
        device_id = properties.get("id")
        if not device_id:
            return self.async_abort(reason="invalid_discovery")

        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})
        self._discovered_host = discovery_info.host
        self._discovered_name = properties.get("name") or discovery_info.name
        self.context["title_placeholders"] = {"name": self._discovered_name}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None and self._discovered_host:
            return await self._validate_and_create(
                self._discovered_host, user_input[CONF_TOKEN], errors, "confirm"
            )
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            errors=errors,
            description_placeholders={"name": self._discovered_name or "ShevLogger"},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            return await self._validate_and_create(
                user_input[CONF_HOST], user_input[CONF_TOKEN], errors, "user"
            )
        return self._manual_form(errors)

    def _manual_form(self, errors: dict[str, str]) -> ConfigFlowResult:
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_TOKEN): str,
                }
            ),
            errors=errors,
        )

    async def _validate_and_create(
        self,
        host: str,
        token: str,
        errors: dict[str, str],
        step_id: str,
    ) -> ConfigFlowResult:
        try:
            normalized_host = normalize_host(host)
            info = await ShevLoggerApi(
                async_get_clientsession(self.hass), normalized_host, token
            ).async_get_state()
            device = info["device"]
            device_id = str(device["id"])
        except ShevLoggerAuthError:
            errors["base"] = "invalid_auth"
        except (ShevLoggerConnectionError, KeyError, TypeError, ValueError):
            errors["base"] = "cannot_connect"
        else:
            await self.async_set_unique_id(device_id)
            self._abort_if_unique_id_configured(updates={CONF_HOST: normalized_host})
            return self.async_create_entry(
                title=str(device.get("name") or "ShevLogger"),
                data={CONF_HOST: normalized_host, CONF_TOKEN: token.strip()},
            )

        if step_id == "confirm":
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
                errors=errors,
                description_placeholders={"name": self._discovered_name or "ShevLogger"},
            )
        return self._manual_form(errors)
