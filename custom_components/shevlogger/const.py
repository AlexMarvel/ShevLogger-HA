"""Constants for the ShevLogger integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "shevlogger"

CONF_TOKEN = "token"
DEFAULT_SCAN_INTERVAL_SECONDS = 5

PLATFORMS = [Platform.NUMBER, Platform.SELECT, Platform.SENSOR, Platform.SWITCH]
