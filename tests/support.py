"""Small HA boundary doubles; integration code and voluptuous run unchanged.

These tests run on Windows without a Home Assistant installation. Framework
entry/update calls mirror the public 2024.8 signatures (not newer-only helpers).
They test our flow decisions, not the Home Assistant frontend or registries.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import voluptuous as vol


class FlowAbort(Exception):
    def __init__(self, reason):
        self.reason = reason


class ConfigFlow:
    def __init_subclass__(cls, *, domain):
        cls.domain = domain

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_abort(self, *, reason):
        return {"type": "abort", "reason": reason}

    async def async_set_unique_id(self, unique_id):
        self.unique_id = unique_id

    def _abort_if_unique_id_configured(self, *, updates=None):
        if self.hass.entry and self.hass.entry.unique_id == self.unique_id:
            raise FlowAbort("already_configured")

    def async_create_entry(self, *, title, data):
        return {"type": "create_entry", "title": title, "data": data}

    def async_update_reload_and_abort(self, entry, *, data, reason):
        # Deliberately accepts only the API parameters supported in HA 2024.8.
        entry.data = data
        self.hass.updates.append(entry.entry_id)
        self.hass.reloads.append(entry.entry_id)
        return self.async_abort(reason=reason)


class TextSelector:
    def __init__(self, config):
        self.config = config

    def __call__(self, value):
        return vol.Schema(str)(value)


def module(name, **attrs):
    result = ModuleType(name)
    result.__dict__.update(attrs)
    return result


def load_integration():
    root = Path(__file__).resolve().parents[1] / "custom_components" / "shevlogger"
    name = "_shevlogger_flow_tests"
    package = module(name)
    package.__path__ = [str(root)]
    entries = module(
        "homeassistant.config_entries", ConfigFlow=ConfigFlow, ConfigFlowResult=dict
    )
    replacements = {
        name: package,
        "homeassistant": module("homeassistant", config_entries=entries),
        "homeassistant.config_entries": entries,
        "homeassistant.const": module(
            "homeassistant.const",
            CONF_HOST="host",
            Platform=SimpleNamespace(
                NUMBER="number", SELECT="select", SENSOR="sensor", SWITCH="switch"
            ),
        ),
        "homeassistant.helpers": module("homeassistant.helpers"),
        "homeassistant.helpers.aiohttp_client": module(
            "homeassistant.helpers.aiohttp_client",
            async_get_clientsession=lambda hass: hass.session,
        ),
        "homeassistant.helpers.selector": module(
            "homeassistant.helpers.selector",
            TextSelector=TextSelector,
            TextSelectorConfig=dict,
            TextSelectorType=SimpleNamespace(PASSWORD="password"),
        ),
        "homeassistant.helpers.service_info": module(
            "homeassistant.helpers.service_info"
        ),
        "homeassistant.helpers.service_info.zeroconf": module(
            "homeassistant.helpers.service_info.zeroconf", ZeroconfServiceInfo=object
        ),
    }
    with patch.dict(sys.modules, replacements):
        loaded = {}
        for part in ("const", "api", "config_flow"):
            spec = importlib.util.spec_from_file_location(
                f"{name}.{part}", root / f"{part}.py"
            )
            loaded[part] = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = loaded[part]
            spec.loader.exec_module(loaded[part])
        return loaded["api"], loaded["config_flow"]


API, FLOW = load_integration()


class FakeHass:
    def __init__(self):
        self.entry = SimpleNamespace(
            entry_id="original-entry",
            domain="shevlogger",
            unique_id="SL-TEST",
            title="My custom logger name",
            options={"keep": True},
            data={"host": "192.168.1.101", "token": "stored-secret", "keep": "value"},
        )
        self.session = object()
        self.updates = []
        self.reloads = []
        self.config_entries = SimpleNamespace(async_get_entry=self.get_entry)

    def get_entry(self, entry_id):
        return self.entry if self.entry and self.entry.entry_id == entry_id else None
