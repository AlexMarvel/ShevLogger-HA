"""Editable boolean parameters from the active inverter profile."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ShevLoggerRuntimeData
from .const import DOMAIN
from .coordinator import ShevLoggerCoordinator
from .entity import ShevLoggerEntity, parse_numeric


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime: ShevLoggerRuntimeData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ShevLoggerSwitch(runtime.coordinator, runtime.info, description)
        for description in runtime.entities
        if description.get("key")
        and description.get("writable") is True
        and description.get("platform") == "switch"
    )


class ShevLoggerSwitch(ShevLoggerEntity, SwitchEntity):
    """A register flag exposed as a Home Assistant switch."""

    _attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self) -> bool | None:
        value = parse_numeric(self.raw_state)
        return None if value is None else value != 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.async_write_value(1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.async_write_value(0)
