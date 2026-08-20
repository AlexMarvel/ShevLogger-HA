"""Shared state polling for ShevLogger entities."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ShevLoggerApi, ShevLoggerAuthError, ShevLoggerError
from .const import DEFAULT_SCAN_INTERVAL_SECONDS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ShevLoggerCoordinator(DataUpdateCoordinator[dict]):
    """Fetch all logger values with one request shared by every entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: ShevLoggerApi,
        meta_revision: int,
    ) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS),
        )
        self.api = api
        self.meta_revision = meta_revision

    async def _async_update_data(self) -> dict:
        try:
            data = await self.api.async_get_state()
        except ShevLoggerAuthError as error:
            raise ConfigEntryAuthFailed from error
        except ShevLoggerError as error:
            raise UpdateFailed(str(error)) from error

        if data.get("metaRevision") != self.meta_revision:
            # A changed inverter profile means the entity catalogue changed.
            # Reload only once; setup will remember the new revision.
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.config_entry.entry_id)
            )
            self.meta_revision = data.get("metaRevision")
        return data
