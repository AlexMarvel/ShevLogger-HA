"""Dynamic sensor entities supplied by the active inverter profile."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ShevLoggerRuntimeData
from .const import DOMAIN
from .coordinator import ShevLoggerCoordinator


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
    )


class ShevLoggerSensor(CoordinatorEntity[ShevLoggerCoordinator], SensorEntity):
    """One value from the profile; all instances share the same poll."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ShevLoggerCoordinator,
        info: dict[str, Any],
        description: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        device = info["device"]
        self._key = str(description["key"])
        self._description = description
        self._attr_unique_id = f"{device['id']}_{self._key}"
        self._attr_name = str(description.get("name") or self._key)
        self._attr_native_unit_of_measurement = description.get("unit") or None
        self._attr_device_class = description.get("deviceClass") or None
        self._attr_state_class = description.get("stateClass") or None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device["id"]))},
            name=str(device.get("name") or "ShevLogger"),
            manufacturer=str(device.get("manufacturer") or "SmartShev"),
            model=str(device.get("model") or "ShevLogger"),
            sw_version=str(device.get("firmware") or ""),
            configuration_url=f"http://{coordinator.api.host}/",
        )

    @property
    def native_value(self) -> Any:
        value = (self.coordinator.data.get("states") or {}).get(self._key)
        modifier = self._description.get("modifier", 1)
        if isinstance(value, (int, float)) and isinstance(modifier, (int, float)):
            return value * modifier
        return value

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and bool(self.coordinator.data.get("available"))
            and self.native_value is not None
        )

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
