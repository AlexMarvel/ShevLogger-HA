"""Dynamic sensor entities supplied by the active inverter profile."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ShevLoggerRuntimeData
from .const import DOMAIN
from .coordinator import ShevLoggerCoordinator
from .entity import ShevLoggerEntity, inferred_device_class, inferred_unit


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime: ShevLoggerRuntimeData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ShevLoggerSensor(runtime.coordinator, runtime.info, description)
        for description in runtime.entities
        if description.get("key")
        and (
            not description.get("writable")
            or description.get("platform", "sensor")
            not in {"number", "select", "switch"}
        )
    )


class ShevLoggerSensor(ShevLoggerEntity, SensorEntity):
    """One value from the profile; all instances share the same poll."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ShevLoggerCoordinator,
        info: dict[str, Any],
        description: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, info, description)
        unit = inferred_unit(description)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = inferred_device_class(description, unit)
        state_class = description.get("stateClass")
        if not state_class and self._attr_device_class in {
            "power",
            "frequency",
            "voltage",
            "current",
            "temperature",
        }:
            state_class = "measurement"
        self._attr_state_class = state_class or None

    @property
    def native_value(self) -> Any:
        value = self.raw_state
        modifier = self._description.get("modifier", 1)
        if isinstance(value, (int, float)) and isinstance(modifier, (int, float)):
            return value * modifier
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in {
                "key": self._key,
                "group": self._description.get("group"),
                "description": self._description.get("description"),
                "writable": self._description.get("writable", False),
                "platform": self._description.get("platform", "sensor"),
            }.items()
            if value not in (None, "")
        }
