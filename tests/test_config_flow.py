import copy
import unittest
from unittest.mock import AsyncMock, patch

import voluptuous as vol
from support import API, FLOW, FakeHass, FlowAbort


class ConfigFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.hass = FakeHass()
        self.entry = self.hass.entry
        self.original = copy.deepcopy(self.entry.data)
        self.flow = FLOW.ShevLoggerConfigFlow()
        self.flow.hass = self.hass
        self.flow.context = {"entry_id": self.entry.entry_id}
        self.api_patch = patch.object(FLOW, "ShevLoggerApi")
        self.api = self.api_patch.start()
        self.addCleanup(self.api_patch.stop)
        self.read = AsyncMock(
            return_value={"apiVersion": 1, "device": {"id": "SL-TEST"}}
        )
        self.api.return_value.async_get_state = self.read

    def unchanged(self):
        self.assertEqual(self.entry.data, self.original)
        self.assertEqual(self.hass.updates, [])
        self.assertEqual(self.hass.reloads, [])

    def token_field(self, result):
        schema = result["data_schema"].schema
        field = next(key for key in schema if key.schema == "token")
        self.assertIs(field.default, vol.UNDEFINED)
        self.assertEqual(schema[field].config["type"], "password")
        self.assertNotIn("stored-secret", str(result))
        self.assertNotIn("replacement-secret", str(result))
        return field

    async def test_reconfigure_prefills_host_but_never_token(self):
        result = await self.flow.async_step_reconfigure()
        self.assertEqual(result["step_id"], "reconfigure")
        self.assertIsInstance(self.token_field(result), vol.Optional)
        self.assertEqual(result["data_schema"]({}), {"host": "192.168.1.101"})
        self.read.assert_not_awaited()
        self.unchanged()

    async def test_ip_only_change_preserves_token_identity_and_metadata(self):
        result = await self.flow.async_step_reconfigure(
            {"host": "http://192.168.1.102/"}
        )
        self.api.assert_called_once_with(
            self.hass.session, "192.168.1.102", "stored-secret"
        )
        self.assertEqual(result, {"type": "abort", "reason": "reconfigure_successful"})
        self.assertIs(self.hass.entry, self.entry)
        self.assertEqual(self.entry.data, {**self.original, "host": "192.168.1.102"})
        self.assertEqual(self.entry.unique_id, "SL-TEST")
        self.assertEqual(self.entry.title, "My custom logger name")
        self.assertEqual(self.entry.options, {"keep": True})
        self.assertEqual(self.hass.reloads, ["original-entry"])

    async def test_whitespace_token_keeps_existing_secret(self):
        await self.flow.async_step_reconfigure({"host": "logger.local", "token": "   "})
        self.assertEqual(self.entry.data["token"], "stored-secret")

    async def test_token_only_change_uses_same_entry(self):
        await self.flow.async_step_reconfigure(
            {"host": "192.168.1.101", "token": " replacement-secret "}
        )
        self.assertEqual(
            self.entry.data, {**self.original, "token": "replacement-secret"}
        )
        self.assertEqual(self.hass.updates, ["original-entry"])

    async def test_reauth_allows_host_edit_and_requires_new_input(self):
        result = await self.flow.async_step_reauth(self.entry.data)
        self.assertEqual(result["step_id"], "reauth_confirm")
        self.assertIsInstance(self.token_field(result), vol.Required)
        with self.assertRaises(vol.Invalid):
            result["data_schema"]({})
        result = await self.flow.async_step_reauth_confirm(
            {"host": "logger.local", "token": "replacement-secret"}
        )
        self.assertEqual(result["reason"], "reauth_successful")
        self.assertEqual(
            self.entry.data,
            {**self.original, "host": "logger.local", "token": "replacement-secret"},
        )
        self.assertEqual(self.hass.reloads, ["original-entry"])

    async def test_blank_reauth_never_reuses_the_old_token(self):
        result = await self.flow.async_step_reauth_confirm(
            {"host": "logger.local", "token": "  "}
        )
        self.assertEqual(result["errors"], {"token": "token_required"})
        self.read.assert_not_awaited()
        self.unchanged()

    async def test_successful_reauth_reloads_even_if_token_is_unchanged(self):
        result = await self.flow.async_step_reauth_confirm(
            {"host": self.entry.data["host"], "token": "stored-secret"}
        )
        self.assertEqual(result["reason"], "reauth_successful")
        self.assertEqual(self.hass.reloads, ["original-entry"])

    async def test_wrong_logger_is_rejected_in_both_flows(self):
        self.read.return_value = {"device": {"id": "SL-OTHER"}}
        for step in (
            self.flow.async_step_reconfigure,
            self.flow.async_step_reauth_confirm,
        ):
            result = await step({"host": "other.local", "token": "replacement-secret"})
            self.assertEqual(result["errors"], {"base": "wrong_device"})
            self.token_field(result)
            self.unchanged()

    async def test_missing_or_malformed_identity_cannot_overwrite_entry(self):
        for device in (None, {}, {"id": None}, {"id": ""}, {"id": 7}, {"id": "  "}):
            self.read.return_value = {"device": device}
            result = await self.flow.async_step_reconfigure({"host": "new.local"})
            self.assertEqual(result["errors"], {"base": "cannot_connect"})
            self.unchanged()

    async def test_auth_errors_are_specific_and_do_not_leak_submitted_token(self):
        for reason in ("invalid_auth", "missing_bearer", "auth_rejected"):
            self.read.side_effect = API.ShevLoggerAuthError(403, reason)
            for step in (
                self.flow.async_step_reconfigure,
                self.flow.async_step_reauth_confirm,
            ):
                result = await step(
                    {"host": "new.local", "token": "replacement-secret"}
                )
                self.assertEqual(result["errors"], {"base": reason})
                self.token_field(result)
                self.unchanged()

    async def test_network_error_keeps_configuration_and_form_editable(self):
        self.read.side_effect = API.ShevLoggerConnectionError("offline")
        result = await self.flow.async_step_reconfigure({"host": "new.local"})
        self.assertEqual(result["errors"], {"base": "cannot_connect"})
        self.assertEqual(result["data_schema"]({})["host"], "new.local")
        self.unchanged()
        self.read.side_effect = None
        result = await self.flow.async_step_reconfigure({"host": "fixed.local"})
        self.assertEqual(result["reason"], "reconfigure_successful")

    async def test_bad_address_never_sends_the_token(self):
        for host in (
            "",
            "http://",
            "http://user:secret@logger.local",
            "https://logger.local",
            "logger.local:8123",
            "logger.local/api",
            "logger.local?token=secret",
        ):
            result = await self.flow.async_step_reconfigure({"host": host})
            self.assertEqual(result["errors"], {"host": "invalid_host"})
            self.unchanged()
        self.api.assert_not_called()

    async def test_entry_removed_during_validation_cannot_be_recreated(self):
        async def remove_entry():
            self.hass.entry = None
            return {"device": {"id": "SL-TEST"}}

        self.read.side_effect = remove_entry
        result = await self.flow.async_step_reconfigure({"host": "new.local"})
        self.assertEqual(result["reason"], "entry_changed")
        self.unchanged()

    async def test_concurrent_change_is_not_overwritten(self):
        async def change_entry():
            self.entry.data = {**self.original, "host": "changed.local"}
            return {"device": {"id": "SL-TEST"}}

        self.read.side_effect = change_entry
        result = await self.flow.async_step_reconfigure({"host": "new.local"})
        self.assertEqual(result["reason"], "entry_changed")
        self.assertEqual(self.entry.data["host"], "changed.local")
        self.assertEqual(self.hass.updates, [])

    async def test_missing_entry_or_identity_aborts_without_network(self):
        self.entry.unique_id = None
        result = await self.flow.async_step_reconfigure()
        self.assertEqual(result["reason"], "missing_identity")
        self.hass.entry = None
        result = await self.flow.async_step_reconfigure()
        self.assertEqual(result["reason"], "entry_not_found")
        self.api.assert_not_called()

    async def test_initial_setup_still_creates_entry_with_valid_identity(self):
        self.hass.entry = None
        result = await self.flow.async_step_user(
            {"host": "logger.local", "token": " new-secret "}
        )
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(
            result["data"], {"host": "logger.local", "token": "new-secret"}
        )
        self.assertEqual(self.flow.unique_id, "SL-TEST")

    async def test_existing_logger_cannot_be_duplicated_by_manual_setup(self):
        with self.assertRaises(FlowAbort) as error:
            await self.flow.async_step_user(
                {"host": "logger.local", "token": "stored-secret"}
            )
        self.assertEqual(error.exception.reason, "already_configured")
        self.unchanged()

    async def test_all_initial_forms_mask_token(self):
        self.token_field(await self.flow.async_step_user())
        self.token_field(await self.flow.async_step_confirm())


if __name__ == "__main__":
    unittest.main()
