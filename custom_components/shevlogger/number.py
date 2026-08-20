"""Editable numeric parameters from the active inverter profile."""

from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ShevLoggerRuntimeData
from .const import DOMAIN
from .coordinator import ShevLoggerCoordinator
from .entity import ShevLoggerEntity, inferred_device_class, inferred_unit, parse_numeric


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime: ShevLoggerRuntimeData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ShevLoggerNumber(runtime.coordinator, runtime.info, description)
        for description in runtime.entities
        if description.get("key")
        and description.get("writable") is True
        and description.get("platform") == "number"
    )


class ShevLoggerNumber(ShevLoggerEntity, NumberEntity):
    """A number that writes its value back through the logger."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: ShevLoggerCoordinator,
        info: dict[str, Any],
        description: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, info, description)
        unit = inferred_unit(description)
        self._attr_native_unit_of_measurement = unit
        device_class = inferred_device_class(description, unit)
        self._attr_device_class = None if device_class == "battery" else device_class
        self._attr_native_min_value = float(description.get("min", -32768))
        self._attr_native_max_value = float(description.get("max", 65535))
        self._attr_native_step = float(description.get("step") or 1)

    @property
    def native_value(self) -> float | None:
        return parse_numeric(self.raw_state)

    async def async_set_native_value(self, value: float) -> None:
        await self.async_write_value(value)
