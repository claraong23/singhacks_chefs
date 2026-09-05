"""Hosted safety controls remain testable without a configured PostgreSQL service."""

from __future__ import annotations

import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from clarity import config
from clarity.api import ClarityHandler


class TestHostedControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from http.server import ThreadingHTTPServer
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ClarityHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=2)

    def request(self, path: str, payload: dict | None = None, token: str | None = None):
        headers = {"Content-Type": "application/json"}
        if token: headers["Authorization"] = f"Bearer {token}"
        request = Request(f"{self.base}{path}", data=json.dumps(payload).encode() if payload is not None else None, headers=headers, method="POST" if payload is not None else "GET")
        try:
            with urlopen(request) as response: return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_health_exposes_safe_local_persistence_metadata(self) -> None:
        code, body = self.request("/api/health")
        self.assertEqual(code, 200); self.assertEqual(body["persistence"]["storage"], "local_json")
        self.assertNotIn("DATABASE_URL", json.dumps(body))

    def test_hosted_writes_need_token_and_reset_stays_disabled(self) -> None:
        previous = config.API_TOKEN, config.HOSTED_MODE, config.ALLOW_DEMO_RESET
        config.API_TOKEN, config.HOSTED_MODE, config.ALLOW_DEMO_RESET = "unit-write-token", True, False
        try:
            code, _ = self.request("/api/not-a-route", {})
            self.assertEqual(code, 401)
            code, _ = self.request("/api/not-a-route", {}, "unit-write-token")
            self.assertEqual(code, 404)
            code, body = self.request("/api/reset", {}, "unit-write-token")
            self.assertEqual(code, 403); self.assertIn("disabled", body["error"])
        finally:
            config.API_TOKEN, config.HOSTED_MODE, config.ALLOW_DEMO_RESET = previous


if __name__ == "__main__":
    unittest.main()
