"""Small availability state machine independent from Home Assistant internals."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Any


@dataclass
class AvailabilityTracker:
    """Debounce short LAN and inverter interruptions without hiding outages."""

    grace_seconds: float
    last_logger_success: float | None = None
    last_inverter_success: float | None = None
    state: str = "offline"

    def record_snapshot(self, data: dict[str, Any], now: float | None = None) -> None:
        """Record one valid HTTP snapshot and its inverter freshness."""
        current = monotonic() if now is None else now
        self.last_logger_success = current

        diagnostics = data.get("diagnostics")
        age_ms = diagnostics.get("lastSuccessAgeMs") if isinstance(diagnostics, dict) else None
        if isinstance(age_ms, (int, float)) and not isinstance(age_ms, bool) and age_ms >= 0:
            # The logger reports the real age of the last successful Modbus
            # frame. Do not replace it with the HTTP response time: doing so on
            # every request would extend a stale inverter snapshot forever.
            self.last_inverter_success = current - (float(age_ms) / 1000.0)
        elif data.get("available") is True:
            self.last_inverter_success = current

        if data.get("available") is True and self.inverter_fresh(current):
            self.state = "online"
        else:
            self.state = "degraded" if self.inverter_fresh(current) else "offline"

    def record_http_failure(self, now: float | None = None) -> None:
        """Keep a recent snapshot through a short HTTP interruption."""
        current = monotonic() if now is None else now
        self.state = "degraded" if self.data_fresh(current) else "offline"

    def logger_fresh(self, now: float | None = None) -> bool:
        current = monotonic() if now is None else now
        return (
            self.last_logger_success is not None
            and current - self.last_logger_success <= self.grace_seconds
        )

    def inverter_fresh(self, now: float | None = None) -> bool:
        current = monotonic() if now is None else now
        return (
            self.last_inverter_success is not None
            and current - self.last_inverter_success <= self.grace_seconds
        )

    def data_fresh(self, now: float | None = None) -> bool:
        current = monotonic() if now is None else now
        return self.logger_fresh(current) and self.inverter_fresh(current)
