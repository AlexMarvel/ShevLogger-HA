import unittest

from aiohttp import ClientSession, web
from support import API


class Response:
    def __init__(self, status, payload):
        self.status = status
        self.payload = payload

    async def read(self):
        return self.payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class Session:
    def __init__(self, status, payload):
        self.response = Response(status, payload)
        self.calls = []

    def request(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.response


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_http_rejects_old_token_and_accepts_replacement(self):
        calls = []

        async def state(request):
            calls.append(request.headers.get("Authorization"))
            if calls[-1] != "Bearer replacement-test-token":
                return web.json_response({"error": "credential_mismatch"}, status=403)
            return web.json_response({"apiVersion": 1, "device": {"id": "SL-TEST"}})

        app = web.Application()
        app.router.add_get("/api/v1/state", state)
        runner = web.AppRunner(app)
        await runner.setup()
        self.addAsyncCleanup(runner.cleanup)
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = runner.addresses[0][1]
        async with ClientSession() as session:
            client = API.ShevLoggerApi(session, "127.0.0.1", "old-test-token")
            # A random loopback port avoids touching any real logger in tests.
            client._base_url = f"http://127.0.0.1:{port}/api/v1"
            with self.assertRaises(API.ShevLoggerAuthError) as caught:
                await client.async_get_state()
            self.assertEqual(caught.exception.reason, "invalid_auth")
            client = API.ShevLoggerApi(session, "127.0.0.1", "replacement-test-token")
            client._base_url = f"http://127.0.0.1:{port}/api/v1"
            self.assertEqual(
                (await client.async_get_state())["device"]["id"], "SL-TEST"
            )
        self.assertEqual(
            calls, ["Bearer old-test-token", "Bearer replacement-test-token"]
        )

    async def test_known_auth_reasons_include_status_without_response_body(self):
        for status, code, reason in (
            (401, "missing_bearer", "missing_bearer"),
            (403, "credential_mismatch", "invalid_auth"),
        ):
            payload = ('{"error":"' + code + '","token":"private-secret"}').encode()
            with self.assertRaises(API.ShevLoggerAuthError) as caught:
                await API.ShevLoggerApi._raise_for_status(Response(status, payload))
            self.assertEqual(caught.exception.reason, reason)
            self.assertIn(str(status), str(caught.exception))
            self.assertNotIn("private-secret", str(caught.exception))

    async def test_unknown_or_malformed_auth_bodies_still_fail_closed(self):
        for payload in (
            b"private-secret",
            b"\xff",
            b"[]",
            b"null",
            b'{"error":"private-secret"}',
            b'{"error":["missing_bearer"]}',
            b"x" * 5000,
        ):
            for status in (401, 403):
                with self.assertRaises(API.ShevLoggerAuthError) as caught:
                    await API.ShevLoggerApi._raise_for_status(Response(status, payload))
                self.assertEqual(caught.exception.reason, "auth_rejected")
                self.assertNotIn("private-secret", str(caught.exception))

    async def test_auth_rejection_is_not_retried_or_treated_as_live_data(self):
        session = Session(403, b'{"error":"credential_mismatch"}')
        client = API.ShevLoggerApi(session, "192.168.1.101", "private-secret")
        with self.assertRaises(API.ShevLoggerAuthError):
            await client.async_get_state()
        self.assertEqual(len(session.calls), 1)

    async def test_authenticated_read_keeps_token_in_header_and_refuses_redirects(self):
        session = Session(200, b'{"apiVersion":1,"device":{"id":"SL-TEST"}}')
        client = API.ShevLoggerApi(session, "192.168.1.101", " private-secret ")
        result = await client.async_get_state()
        self.assertEqual(result["device"]["id"], "SL-TEST")
        args, kwargs = session.calls[0]
        self.assertEqual(args, ("GET", "http://192.168.1.101/api/v1/state"))
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer private-secret"})
        self.assertIs(kwargs["allow_redirects"], False)

    async def test_redirect_is_reported_as_connection_error(self):
        with self.assertRaisesRegex(API.ShevLoggerConnectionError, "redirect refused"):
            await API.ShevLoggerApi._raise_for_status(Response(302, b""))

    async def test_unsupported_success_payload_remains_connection_error(self):
        for payload in (b"[]", b"null", b'{"apiVersion":2}', b"not-json"):
            session = Session(200, payload)
            client = API.ShevLoggerApi(session, "logger.local", "private-secret")
            original_delay = API.HTTP_RETRY_DELAY_SECONDS
            API.HTTP_RETRY_DELAY_SECONDS = 0
            try:
                with self.assertRaises(API.ShevLoggerConnectionError):
                    await client.async_get_state()
            finally:
                API.HTTP_RETRY_DELAY_SECONDS = original_delay

    def test_host_normalization_accepts_local_ipv4_and_hostname(self):
        for raw, expected in (
            ("192.168.1.101", "192.168.1.101"),
            (" http://192.168.1.101/ ", "192.168.1.101"),
            ("http://Logger.local:80/", "logger.local"),
        ):
            self.assertEqual(API.normalize_host(raw), expected)

    def test_ambiguous_or_unsupported_addresses_are_rejected(self):
        for raw in (
            "",
            "http://",
            "https://logger.local",
            "logger.local:81",
            "logger.local:bad",
            "logger.local/api",
            "logger.local?x=1",
            "logger.local#x",
            "user:private-secret@logger.local",
            "bad host",
            "[::1]",
        ):
            with self.assertRaises(ValueError, msg=raw):
                API.normalize_host(raw)


if __name__ == "__main__":
    unittest.main()
