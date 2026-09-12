"""Home Assistant metadata inferred from profile sensor descriptions."""

from __future__ import annotations

from typing import Any


ENERGY_UNITS = frozenset(
    {"J", "kJ", "MJ", "GJ", "mWh", "Wh", "kWh", "MWh", "GWh", "TWh"}
)
MEASUREMENT_DEVICE_CLASSES = frozenset(
    {
        "apparent_power",
        "battery",
        "current",
        "energy_storage",
        "frequency",
        "power",
        "power_factor",
        "temperature",
        "voltage",
    }
)
ENERGY_COUNTER_TERMS = frozenset(
    {
        "charge",
        "consumption",
        "discharge",
        "energy",
        "export",
        "import",
        "production",
        "yield",
    }
)


def _sensor_text(description: dict[str, Any]) -> tuple[str, str]:
    key = str(description.get("key") or "").strip().lower()
    name = str(description.get("name") or "").strip().lower()
    return key, f"{key} {name}"


def _is_energy_counter(description: dict[str, Any]) -> bool:
    key, _ = _sensor_text(description)
    tokens = set(key.replace("-", "_").split("_"))
    period_counter = key.startswith(
        ("today_", "total_", "daily_", "monthly_", "yearly_", "lifetime_")
    ) and bool(tokens & ENERGY_COUNTER_TERMS)
    suffix_counter = key.endswith(
        (
            "_energy_today",
            "_energy_total",
            "_yield_today",
            "_yield_total",
        )
    )
    return period_counter or suffix_counter


def inferred_unit(description: dict[str, Any]) -> str | None:
    """Fill standard units when a profile omitted presentation metadata."""
    if unit := description.get("unit"):
        return str(unit)
    key, text = _sensor_text(description)
    if "energy pattern" in text or "energy_pattern" in key:
        return None
    if _is_energy_counter(description):
        return "kWh"
    if "power factor" in text or "power_factor" in key:
        return "%"
    if "apparent_power" in key or "apparent power" in text:
        return "VA"
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
    """Return a device class only when the sensor meaning is unambiguous."""
    if device_class := description.get("deviceClass"):
        return str(device_class)
    key, text = _sensor_text(description)
    if unit in ENERGY_UNITS:
        if any(term in text for term in ("capacity", "remaining", "stored")):
            return "energy_storage"
        return "energy"
    if unit == "%":
        if "power factor" in text or "power_factor" in key:
            return "power_factor"
        if "soc" in text or "state_of_charge" in key or "battery_level" in key:
            return "battery"
        return None
    return {
        "W": "power",
        "kW": "power",
        "VA": "apparent_power",
        "kVA": "apparent_power",
        "Hz": "frequency",
        "V": "voltage",
        "A": "current",
        "°C": "temperature",
    }.get(unit)


def inferred_state_class(
    description: dict[str, Any], device_class: str | None
) -> str | None:
    """Supply statistics metadata required by Home Assistant."""
    if state_class := description.get("stateClass"):
        return str(state_class)
    key, _ = _sensor_text(description)
    if device_class == "energy":
        return "total" if "net" in key else "total_increasing"
    if device_class in MEASUREMENT_DEVICE_CLASSES:
        return "measurement"
    return None
