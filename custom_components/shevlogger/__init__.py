"""ShevLogger Home Assistant integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ShevLoggerApi, ShevLoggerAuthError, ShevLoggerError
from .const import CONF_TOKEN, DOMAIN, PLATFORMS
from .coordinator import ShevLoggerCoordinator


@dataclass
class ShevLoggerRuntimeData:
    """Data fetched once when the integration starts."""

    info: dict[str, Any]
    entities: list[dict[str, Any]]
    coordinator: ShevLoggerCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api = ShevLoggerApi(
        async_get_clientsession(hass), entry.data["host"], entry.data[CONF_TOKEN]
    )
    try:
        info = await api.async_get_state()
        entity_payload = await api.async_get_schema()
    except ShevLoggerAuthError as error:
        raise ConfigEntryAuthFailed from error
    except ShevLoggerError as error:
        raise ConfigEntryNotReady(str(error)) from error
    coordinator = ShevLoggerCoordinator(
        hass, entry, api, int(entity_payload.get("metaRevision", 0))
    )
    await coordinator.async_config_entry_first_refresh()

    # Version 0.1 exposed writable parameters as read-only sensors. Remove
    # those obsolete registry entries before the native control entities are
    # created, otherwise Home Assistant keeps unavailable duplicates forever.
    registry = er.async_get(hass)
    device_id = str(info["device"]["id"])
    for description in entity_payload.get("entities", []):
        if (
            description.get("writable") is True
            and description.get("platform") in {"number", "select", "switch"}
            and description.get("key")
        ):
            unique_id = f"{device_id}_{description['key']}"
            if old_entity_id := registry.async_get_entity_id(
                "sensor", DOMAIN, unique_id
            ):
                registry.async_remove(old_entity_id)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = ShevLoggerRuntimeData(
        info=info,
        entities=entity_payload.get("entities", []),
        coordinator=coordinator,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    hass.data[DOMAIN].pop(entry.entry_id)
    return True
