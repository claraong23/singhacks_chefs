"""Opt-in smoke checks for an already deployed, isolated Clarity environment.

Set CLARITY_DEPLOY_URL and CLARITY_API_TOKEN to run safe read/authentication
checks. Set CLARITY_DEPLOY_MUTATION_CHECK=true only for a disposable hosted
database to create one synthetic inbound event and verify persistence.
"""

from __future__ import annotations

import json
import os
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4


DEPLOY_URL = os.environ.get("CLARITY_DEPLOY_URL", "").rstrip("/")
WRITE_TOKEN = os.environ.get("CLARITY_API_TOKEN", "")


@unittest.skipUnless(DEPLOY_URL and WRITE_TOKEN, "set CLARITY_DEPLOY_URL and CLARITY_API_TOKEN for deployed smoke checks")
class TestDeployedSmoke(unittest.TestCase):
    def request(self, path: str, payload: dict | None = None, token: str | None = None):
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(
            f"{DEPLOY_URL}{path}",
            data=json.dumps(payload).encode() if payload is not None else None,
            headers=headers,
            method="POST" if payload is not None else "GET",
        )
        try:
            with urlopen(request, timeout=20) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_read_only_health_and_write_lock_are_safe(self) -> None:
        code, health = self.request("/api/health")
        self.assertEqual(code, 200); self.assertEqual(health["status"], "ok")
        persistence = health["persistence"]
        self.assertEqual(persistence["storage"], "postgresql")
        self.assertTrue(persistence["hosted"])
        self.assertTrue(persistence["write_access_required"])
        self.assertNotIn("DATABASE_URL", json.dumps(health))
        self.assertNotIn(WRITE_TOKEN, json.dumps(health))
        self.assertEqual(self.request("/api/book")[0], 200)
        self.assertEqual(self.request("/api/not-a-route", {})[0], 401)
        self.assertEqual(self.request("/api/not-a-route", {}, "invalid-token")[0], 401)
        self.assertEqual(self.request("/api/not-a-route", {}, WRITE_TOKEN)[0], 404)
        self.assertEqual(self.request("/api/reset", {}, WRITE_TOKEN)[0], 403)

    @unittest.skipUnless(
        os.environ.get("CLARITY_DEPLOY_MUTATION_CHECK", "").lower() == "true",
        "set CLARITY_DEPLOY_MUTATION_CHECK=true only for a disposable hosted database",
    )
    def test_disposable_hosted_database_persists_a_synthetic_event(self) -> None:
        event_ref = f"HOSTED-SMOKE-{uuid4().hex[:12]}"
        payload = {
            "role": "operations", "source_system": "client_document", "external_event_id": event_ref,
            "schema_version": "v1", "client_id": "CL-0014",
            "affected_insight_ids": ["CL-0014-collateral-CF-0002"],
            "source_ref": f"smoke:{event_ref}", "summary": "Synthetic deployed persistence verification.",
            "occurred_at": "2026-08-26",
        }
        code, created = self.request("/api/integrations/inbound", payload, WRITE_TOKEN)
        self.assertEqual(code, 201, created)
        event_id = created["event"]["id"]
        code, replay = self.request("/api/integrations/inbound", payload, WRITE_TOKEN)
        self.assertEqual(code, 200); self.assertTrue(replay["replayed"])
        self.assertEqual(replay["event"]["id"], event_id)
        code, listed = self.request("/api/integrations?role=operations&client_id=CL-0014")
        self.assertEqual(code, 200)
        self.assertIn(event_id, {event["id"] for event in listed["inbound"]})


if __name__ == "__main__":
    unittest.main()
