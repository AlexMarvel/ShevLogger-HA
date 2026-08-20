"""Editable lookup parameters from the active inverter profile."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ShevLoggerRuntimeData
from .const import DOMAIN
from .coordinator import ShevLoggerCoordinator
from .entity import ShevLoggerEntity, option_value


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime: ShevLoggerRuntimeData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ShevLoggerSelect(runtime.coordinator, runtime.info, description)
        for description in runtime.entities
        if description.get("key")
        and description.get("writable") is True
        and description.get("platform") == "select"
        and isinstance(description.get("options"), dict)
    )


class ShevLoggerSelect(ShevLoggerEntity, SelectEntity):
    """A profile lookup exposed as a Home Assistant select."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: ShevLoggerCoordinator,
        info: dict[str, Any],
        description: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, info, description)
        self._values_by_option = {
            str(label): str(raw)
            for raw, label in description["options"].items()
        }
        self._attr_options = list(self._values_by_option)

    @property
    def current_option(self) -> str | None:
        state = str(self.raw_state)
        if state in self._values_by_option:
            return state
        return next(
            (
                option
                for option, raw in self._values_by_option.items()
                if raw == state
            ),
            None,
        )

    async def async_select_option(self, option: str) -> None:
        await self.async_write_value(option_value(self._values_by_option[option]))
