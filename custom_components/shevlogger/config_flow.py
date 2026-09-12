"""Config flow for automatic discovery or manual ShevLogger setup."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import (
    ShevLoggerApi,
    ShevLoggerAuthError,
    ShevLoggerConnectionError,
    normalize_host,
)
from .const import CONF_TOKEN, DOMAIN


def _token_selector() -> TextSelector:
    """Keep both existing and newly entered credentials out of form defaults."""
    return TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


async def _device_info(api: ShevLoggerApi) -> dict[str, Any]:
    info = await api.async_get_state()
    device = info.get("device")
    if (
        not isinstance(device, dict)
        or not isinstance(device.get("id"), str)
        or not device["id"].strip()
    ):
        raise ShevLoggerConnectionError("Missing ShevLogger gateway identity")
    return device


class ShevLoggerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create a config entry without requiring a fixed gateway IP."""

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
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): _token_selector()}),
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
                    vol.Required(CONF_TOKEN): _token_selector(),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the address and optionally replace the existing LAN token."""
        return await self._update_connection("reconfigure", user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start recovery for the existing entry after a 401/403 response."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Require a freshly entered token and allow correcting the address."""
        return await self._update_connection("reauth_confirm", user_input)

    async def _update_connection(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        # Use the entry lookup/update API available since our minimum HA version.
        # Never create a new entry or change its identity, options or entity IDs.
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if entry is None or entry.domain != DOMAIN:
            return self.async_abort(reason="entry_not_found")
        if not entry.unique_id:
            return self.async_abort(reason="missing_identity")

        errors: dict[str, str] = {}
        host = entry.data[CONF_HOST]
        token_required = step_id == "reauth_confirm"
        if user_input is not None:
            host = user_input[CONF_HOST]
            submitted_token = user_input.get(CONF_TOKEN, "").strip()
            token = submitted_token or (
                "" if token_required else entry.data[CONF_TOKEN]
            )
            if not token:
                errors[CONF_TOKEN] = "token_required"
            else:
                original_data = entry.data
                try:
                    normalized_host = normalize_host(host)
                    device = await _device_info(
                        ShevLoggerApi(
                            async_get_clientsession(self.hass), normalized_host, token
                        )
                    )
                except ShevLoggerAuthError as error:
                    errors["base"] = error.reason
                except ShevLoggerConnectionError:
                    errors["base"] = "cannot_connect"
                except ValueError:
                    errors[CONF_HOST] = "invalid_host"
                else:
                    if device["id"] != entry.unique_id:
                        errors["base"] = "wrong_device"
                    elif (
                        self.hass.config_entries.async_get_entry(entry.entry_id)
                        is not entry
                        or entry.data != original_data
                    ):
                        return self.async_abort(reason="entry_changed")
                    else:
                        return self.async_update_reload_and_abort(
                            entry,
                            data={
                                **entry.data,
                                CONF_HOST: normalized_host,
                                CONF_TOKEN: token,
                            },
                            reason=(
                                "reauth_successful"
                                if token_required
                                else "reconfigure_successful"
                            ),
                        )

        token_field = (
            vol.Required(CONF_TOKEN) if token_required else vol.Optional(CONF_TOKEN)
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=host): str,
                    token_field: _token_selector(),
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
            device = await _device_info(
                ShevLoggerApi(
                    async_get_clientsession(self.hass), normalized_host, token
                )
            )
            device_id = device["id"]
        except ShevLoggerAuthError as error:
            errors["base"] = error.reason
        except ShevLoggerConnectionError:
            errors["base"] = "cannot_connect"
        except ValueError:
            errors["base"] = "invalid_host"
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
                data_schema=vol.Schema({vol.Required(CONF_TOKEN): _token_selector()}),
                errors=errors,
                description_placeholders={
                    "name": self._discovered_name or "ShevLogger"
                },
            )
        return self._manual_form(errors)
