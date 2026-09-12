import importlib.util
import unittest
from pathlib import Path


PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "shevlogger"
    / "optional_entities.py"
)
SPEC = importlib.util.spec_from_file_location("shevlogger_optional_entities", PATH)
OPTIONAL = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(OPTIONAL)


class OptionalEntitiesTests(unittest.TestCase):
    def setUp(self):
        self.entities = [
            {"key": "load_power", "platform": "sensor"},
            {
                "key": "bms_voltage",
                "platform": "sensor",
                "availabilityAnchor": "bms_voltage",
            },
            {
                "key": "bms_temperature",
                "platform": "sensor",
                "availabilityAnchor": "bms_voltage",
            },
            {
                "key": "pack1_cycles",
                "platform": "sensor",
                "availabilityAnchor": "pack1_voltage",
            },
        ]

    def test_absent_bms_groups_do_not_create_unavailable_entities(self):
        state = {
            "data": {
                "load_power": 650,
                "bms_voltage": None,
                "pack1_voltage": None,
            }
        }
        self.assertEqual(
            [item["key"] for item in OPTIONAL.active_entities(self.entities, state)],
            ["load_power"],
        )
        self.assertEqual(
            OPTIONAL.optional_presence_signature(self.entities, state),
            (("bms_voltage", False), ("pack1_voltage", False)),
        )

    def test_group_appears_only_when_its_own_anchor_has_data(self):
        state = {
            "data": {
                "load_power": 650,
                "bms_voltage": 52.4,
                "pack1_voltage": None,
            }
        }
        self.assertEqual(
            [item["key"] for item in OPTIONAL.active_entities(self.entities, state)],
            ["load_power", "bms_voltage", "bms_temperature"],
        )
        self.assertEqual(
            OPTIONAL.optional_presence_signature(self.entities, state),
            (("bms_voltage", True), ("pack1_voltage", False)),
        )

    def test_writable_platform_cleanup_uses_the_native_domain(self):
        self.assertEqual(
            OPTIONAL.entity_platform(
                {"key": "limit", "writable": True, "platform": "number"}
            ),
            "number",
        )
        self.assertEqual(
            OPTIONAL.entity_platform({"key": "voltage", "platform": "number"}),
            "sensor",
        )


if __name__ == "__main__":
    unittest.main()
