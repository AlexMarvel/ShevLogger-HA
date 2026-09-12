"""Shared state polling for ShevLogger entities."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ShevLoggerApi, ShevLoggerAuthError, ShevLoggerError
from .availability import AvailabilityTracker
from .const import AVAILABILITY_GRACE_SECONDS, DEFAULT_SCAN_INTERVAL_SECONDS, DOMAIN
from .optional_entities import optional_presence_signature

_LOGGER = logging.getLogger(__name__)


class ShevLoggerCoordinator(DataUpdateCoordinator[dict]):
    """Fetch all gateway values with one request shared by every entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: ShevLoggerApi,
        meta_revision: int,
        entities: list[dict],
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
        self._entities = entities
        self._optional_signature: tuple[tuple[str, bool], ...] | None = None
        self.availability = AvailabilityTracker(AVAILABILITY_GRACE_SECONDS)

    def prime(self, data: dict) -> None:
        """Seed the coordinator with the state already read during setup."""
        self._optional_signature = optional_presence_signature(
            self._entities, data
        )
        self.availability.record_snapshot(data)
        self.async_set_updated_data(data)

    @property
    def data_available(self) -> bool:
        """Keep entities stable through bounded LAN/Modbus interruptions."""
        return self.availability.data_fresh()

    async def _async_update_data(self) -> dict:
        try:
            data = await self.api.async_get_state()
        except ShevLoggerAuthError as error:
            raise ConfigEntryAuthFailed(str(error)) from error
        except ShevLoggerError as error:
            self.availability.record_http_failure()
            if self.data and self.availability.data_fresh():
                _LOGGER.debug(
                    "ShevLogger update interrupted; retaining the last snapshot "
                    "during the %ss grace window: %s",
                    AVAILABILITY_GRACE_SECONDS,
                    error,
                )
                return self.data
            raise UpdateFailed(str(error)) from error

        self.availability.record_snapshot(data)
        reload_required = False
        if data.get("metaRevision") != self.meta_revision:
            # A changed inverter profile means the entity catalogue changed.
            # Reload only once; setup will remember the new revision.
            self.meta_revision = data.get("metaRevision")
            reload_required = True
        optional_signature = optional_presence_signature(self._entities, data)
        if optional_signature != self._optional_signature:
            # Optional BMS/PACK entities are rebuilt only when the inverter
            # starts or stops publishing their own presence anchor.
            self._optional_signature = optional_signature
            reload_required = True
        if reload_required:
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.config_entry.entry_id)
            )
        return data
