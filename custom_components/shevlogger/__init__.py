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
from .optional_entities import active_entities, entity_is_active, entity_platform


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
        raise ConfigEntryAuthFailed(str(error)) from error
    except ShevLoggerError as error:
        raise ConfigEntryNotReady(str(error)) from error
    all_entities = entity_payload.get("entities", [])
    coordinator = ShevLoggerCoordinator(
        hass,
        entry,
        api,
        int(entity_payload.get("metaRevision", 0)),
        all_entities,
    )
    coordinator.prime(info)
    await coordinator.async_config_entry_first_refresh()

    # Version 0.1 exposed writable parameters as read-only sensors. Remove
    # those obsolete registry entries before the native control entities are
    # created, otherwise Home Assistant keeps unavailable duplicates forever.
    registry = er.async_get(hass)
    device_id = str(info["device"]["id"])
    for description in all_entities:
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

        # Optional BMS/PACK telemetry must not leave a page of unavailable
        # entities when the inverter has no compatible BMS connection. The
        # coordinator reloads this same entry when its anchor appears later.
        if not entity_is_active(description, info) and description.get("key"):
            unique_id = f"{device_id}_{description['key']}"
            if old_entity_id := registry.async_get_entity_id(
                entity_platform(description), DOMAIN, unique_id
            ):
                registry.async_remove(old_entity_id)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = ShevLoggerRuntimeData(
        info=info,
        entities=active_entities(all_entities, info),
        coordinator=coordinator,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    hass.data[DOMAIN].pop(entry.entry_id)
    return True
