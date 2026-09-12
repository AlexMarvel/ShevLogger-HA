import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "shevlogger"
    / "sensor_metadata.py"
)
SPEC = importlib.util.spec_from_file_location("shevlogger_sensor_metadata", MODULE_PATH)
METADATA = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(METADATA)


class SensorMetadataTests(unittest.TestCase):
    def metadata(self, description):
        unit = METADATA.inferred_unit(description)
        device_class = METADATA.inferred_device_class(description, unit)
        state_class = METADATA.inferred_state_class(description, device_class)
        return unit, device_class, state_class

    def test_daily_and_lifetime_energy_are_eligible_for_energy_dashboard(self):
        for key in (
            "today_production",
            "today_battery_charge",
            "today_energy_import",
            "total_energy_export",
            "pv_energy_today",
            "load_energy_total",
        ):
            with self.subTest(key=key):
                self.assertEqual(
                    self.metadata({"key": key, "name": key}),
                    ("kWh", "energy", "total_increasing"),
                )

    def test_live_power_and_battery_soc_have_measurement_state_class(self):
        self.assertEqual(
            self.metadata({"key": "pv_power", "name": "PV Power"}),
            ("W", "power", "measurement"),
        )
        self.assertEqual(
            self.metadata({"key": "battery_soc", "name": "Battery SOC"}),
            ("%", "battery", "measurement"),
        )

    def test_percentage_settings_are_not_misclassified_as_battery(self):
        self.assertEqual(
            self.metadata({"key": "output_load_percent", "name": "Load Percentage"}),
            ("%", None, None),
        )
        self.assertEqual(
            self.metadata({"key": "power_factor", "name": "Power Factor"}),
            ("%", "power_factor", "measurement"),
        )

    def test_control_names_are_not_misclassified_as_energy_counters(self):
        self.assertEqual(
            self.metadata({"key": "energy_pattern", "name": "Energy Pattern"}),
            (None, None, None),
        )

    def test_profile_metadata_remains_authoritative(self):
        description = {
            "key": "net_energy",
            "unit": "Wh",
            "deviceClass": "energy",
            "stateClass": "total",
        }
        self.assertEqual(self.metadata(description), ("Wh", "energy", "total"))


if __name__ == "__main__":
    unittest.main()
