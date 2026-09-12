"""Constants for the ShevLogger integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "shevlogger"

CONF_TOKEN = "token"
DEFAULT_SCAN_INTERVAL_SECONDS = 3
AVAILABILITY_GRACE_SECONDS = 30
HTTP_REQUEST_ATTEMPTS = 2
HTTP_REQUEST_TIMEOUT_SECONDS = 3
HTTP_RETRY_DELAY_SECONDS = 0.25

PLATFORMS = [Platform.NUMBER, Platform.SELECT, Platform.SENSOR, Platform.SWITCH]
