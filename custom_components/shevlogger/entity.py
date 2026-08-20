"""Shared helpers for entities supplied by a ShevLogger profile."""

from __future__ import annotations

from typing import Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import ShevLoggerError
from .const import DOMAIN
from .coordinator import ShevLoggerCoordinator


def inferred_unit(description: dict[str, Any]) -> str | None:
    """Fill common electrical units when an older profile omitted metadata."""
    if unit := description.get("unit"):
        return str(unit)
    key = str(description.get("key") or "").lower()
    name = str(description.get("name") or "").lower()
    text = f"{key} {name}"
    if "power factor" in text or "energy pattern" in text:
        return None
    if "power" in text:
        return "W"
    if "frequency" in text:
        return "Hz"
    if "voltage" in text:
        return "V"
    if "current" in text:
        return "A"
    if "temperature" in text:
        return "°C"
    if "soc" in text or "percent" in text or "percentage" in text:
        return "%"
    return None


def inferred_device_class(description: dict[str, Any], unit: str | None) -> str | None:
    """Return a device class only when the unit makes the meaning unambiguous."""
    if device_class := description.get("deviceClass"):
        return str(device_class)
    return {
        "W": "power",
        "Hz": "frequency",
        "V": "voltage",
        "A": "current",
        "°C": "temperature",
        "%": "battery",
    }.get(unit)


def parse_numeric(value: Any) -> float | None:
    """Convert a numeric API state without accepting booleans."""
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def option_value(value: str) -> int | float:
    """Convert a lookup key back to the numeric register value."""
    parsed = float(value)
    return int(parsed) if parsed.is_integer() else parsed


class ShevLoggerEntity(CoordinatorEntity[ShevLoggerCoordinator]):
    """Base entity sharing identity, state and write behavior."""

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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device["id"]))},
            name=str(device.get("name") or "ShevLogger"),
            manufacturer=str(device.get("manufacturer") or "SmartShev"),
            model=str(device.get("model") or "ShevLogger"),
            sw_version=str(device.get("firmware") or ""),
            configuration_url=f"http://{coordinator.api.host}/",
        )

    @property
    def raw_state(self) -> Any:
        """Return the value already held in coordinator memory."""
        return (self.coordinator.data.get("data") or {}).get(self._key)

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and bool(self.coordinator.data.get("available"))
            and self.raw_state is not None
        )

    async def async_write_value(self, value: int | float) -> None:
        """Write a value and immediately refresh all sibling entities."""
        try:
            await self.coordinator.api.async_write(self._key, value)
        except ShevLoggerError as error:
            raise HomeAssistantError(
                f"Не вдалося змінити {self._attr_name}: {error}"
            ) from error
        await self.coordinator.async_request_refresh()
