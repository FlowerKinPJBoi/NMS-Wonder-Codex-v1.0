"""Owner isolation, bounded requests, and child-process lifecycle for FFC."""
from __future__ import annotations

import asyncio
import copy
import importlib
import json
import os
import sys
import types
import unittest
import uuid
from unittest.mock import patch

# Development tests may use the canonical source before root vendors it into
# api/ffc_game. Production always imports the committed vendored package.
try:
    import ffc_game.ffc_wilds.cloud_control as control
except ModuleNotFoundError:
    import ffc_wilds
    import ffc_wilds.cloud_control as control
    package = types.ModuleType("ffc_game")
    package.__path__ = []
    sys.modules["ffc_game"] = package
    sys.modules["ffc_game.ffc_wilds"] = ffc_wilds
    sys.modules["ffc_game.ffc_wilds.cloud_control"] = control

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.routers import ffc_control
from app.services.ffc_control import CloudSupervisor, RUNTIME_MODULE, start_cloud_service
from app.services import ffc_preflight


class FakeStore:
    def __init__(self):
        self.issued = []
        self.revoked = []
        self.received = []
        self.state_value = {"ok": True, "prepared": True, "runtime_ready": True,
                            "cloud_active": False, "state": "prepared", "bot_ready": False,
                            "available_actions": [], "counts": {"players": 4}}

    def state(self):
        return dict(self.state_value)

    def issue_session(self, actor):
        self.issued.append(actor)
        return {"access_token": "ffc1_" + "a" * 64, "token_type": "Bearer", "expires_at": 1800000000, "protocol": 1}

    def validate_session(self, token, *, expected_owner):
        if token != "ffc1_" + "a" * 64 or expected_owner != "PJ":
            raise control.ControlUnauthorized("Connect The Wilds Control Hub again.")
        return {"actor": "PJ", "expires_at": 1800000000}

    def enqueue(self, request_id, action, arguments, actor):
        control.validate_action(action, arguments)
        if not self.state_value["cloud_active"]:
            raise control.ControlConflict("The cloud host is not ready for this action.")
        self.received.append((request_id, action, arguments, actor))
        return {"id": request_id, "status": "queued", "result": None, "error": None}

    def get_command(self, request_id, actor):
        raise control.ControlNotFound("This request has not been received by the cloud host.")

    def revoke_session(self, token):
        self.revoked.append(token)

    def handoff_status(self):
        return {"cloud_active": self.state_value["cloud_active"], "import_digest": None, "stopped_confirmed": True}

    def set_active(self, active, import_digest=None, *, local_host_stopped=False):
        if active and (import_digest != "a" * 64 or not local_host_stopped):
            raise control.ControlConflict("Complete import verification before activating the cloud.")
        self.received.append(("activation", active, import_digest, local_host_stopped))
        self.state_value["cloud_active"] = active
        return self.state()


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(admin_api_key_pj="synthetic-owner-key",
                                 admin_api_key_boots="synthetic-other-admin",
                                 admin_api_key="synthetic-shared-key",
                                 tester_api_key_menomoo="synthetic-tester-key",
                                 analytics_owner_actor="PJ", database_url="", ffc_cloud_prepared=True)
        self.store = FakeStore()
        self.patches = [patch("app.services.security.get_settings", return_value=self.settings),
                        patch("app.routers.ffc_control.get_settings", return_value=self.settings),
                        patch("app.routers.ffc_control.get_control_store", return_value=self.store)]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.app = FastAPI()
        self.app.include_router(ffc_control.router)
        self.client = TestClient(self.app)
        self.owner_headers = {"X-Admin-Actor": "PJ", "X-Admin-Key": "synthetic-owner-key"}
        self.hub_headers = {"Authorization": "Bearer ffc1_" + "a" * 64}

    def test_public_health_contains_no_player_or_session_data(self):
        response = self.client.get("/ffc/control/health")
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()["handoff_required"])
        self.assertTrue(response.json()["runtime_ready"])
        for forbidden in ("counts", "players", "token", "database_url", "guild_id"):
            self.assertNotIn(forbidden, response.text)

    def test_only_named_owner_can_issue_scoped_token(self):
        self.assertEqual(200, self.client.post("/ffc/control/session", headers=self.owner_headers).status_code)
        for headers in ({}, {"X-Admin-Actor": "Boots", "X-Admin-Key": "synthetic-other-admin"},
                        {"X-Admin-Actor": "Menomoo", "X-Admin-Key": "synthetic-tester-key"},
                        {"X-Admin-Actor": "PJ", "X-Admin-Key": "synthetic-shared-key"}):
            with self.subTest(headers=headers):
                self.assertIn(self.client.post("/ffc/control/session", headers=headers).status_code, (401, 403))
        self.assertEqual(["PJ"], self.store.issued)

    def test_status_requires_scoped_token_and_rejects_plain_admin_key(self):
        self.assertEqual(401, self.client.get("/ffc/control/status").status_code)
        self.assertEqual(401, self.client.get("/ffc/control/status", headers=self.owner_headers).status_code)
        response = self.client.get("/ffc/control/status", headers=self.hub_headers)
        self.assertEqual(200, response.status_code)
        self.assertFalse(response.json()["cloud_active"])

    def test_prepared_host_cannot_receive_gameplay_command(self):
        body = {"request_id": str(uuid.uuid4()), "action": "spawn", "arguments": {"kind": "fish"}}
        self.assertEqual(409, self.client.post("/ffc/control/commands", headers=self.hub_headers, json=body).status_code)
        self.assertEqual([], self.store.received)

    def test_action_payload_validation_and_no_activation_route(self):
        self.store.state_value["cloud_active"] = True
        body = {"request_id": str(uuid.uuid4()), "action": "power_drive", "arguments": {"multiplier": 3}}
        response = self.client.post("/ffc/control/commands", headers=self.hub_headers, json=body)
        self.assertEqual(202, response.status_code)
        self.assertEqual(body["request_id"], response.json()["id"])
        for bad in ({**body, "extra": "no"}, {**body, "action": "activate"},
                    {**body, "arguments": {"multiplier": True}}, {**body, "arguments": []}):
            self.assertEqual(400, self.client.post("/ffc/control/commands", headers=self.hub_headers, json=bad).status_code)
        self.assertEqual(404, self.client.post("/ffc/control/activate", headers=self.owner_headers).status_code)

    def test_unknown_request_is_404_and_disconnect_does_not_stop_game(self):
        response = self.client.get("/ffc/control/commands/" + str(uuid.uuid4()), headers=self.hub_headers)
        self.assertEqual(404, response.status_code)
        self.assertEqual(200, self.client.post("/ffc/control/revoke", headers=self.hub_headers).status_code)
        self.assertEqual([], self.store.received)
        self.assertEqual(1, len(self.store.revoked))

    def test_internal_errors_do_not_return_credentials_or_query_details(self):
        with patch.object(self.store, "state", side_effect=RuntimeError("postgresql://private:do-not-leak@host/db")):
            response = self.client.get("/ffc/control/status", headers=self.hub_headers)
            self.assertEqual(503, response.status_code)
            self.assertNotIn("do-not-leak", response.text)
            self.assertNotIn("postgresql", response.text)
            health = self.client.get("/ffc/control/health")
            self.assertFalse(health.json()["prepared"])

    def test_real_api_middleware_bounds_streamed_bodies_and_disables_caching(self):
        main = importlib.import_module("app.main")
        client = TestClient(main.app)
        response = client.get("/ffc/control/status", headers=self.hub_headers)
        self.assertEqual("no-store", response.headers.get("Cache-Control"))
        oversized = client.post("/ffc/control/commands", headers={**self.hub_headers, "Content-Type": "application/json"},
                                content=iter([b" " * 5000, b" " * 5000]))
        self.assertEqual(413, oversized.status_code)

    def test_handoff_is_owner_only_and_never_a_scoped_hub_action(self):
        for method, path, body in (
                ("get", "/handoff", None),
                ("post", "/handoff/preflight", None),
                ("post", "/handoff/import", {}),
                ("post", "/handoff/activate", {"sha256": "a" * 64, "local_host_stopped": True}),
                ("post", "/handoff/deactivate", {"confirm": True})):
            kwargs = {"headers": self.hub_headers}
            if body is not None:
                kwargs["json"] = body
            response = getattr(self.client, method)("/ffc/control" + path, **kwargs)
            self.assertEqual(401, response.status_code)
        self.assertEqual(200, self.client.get("/ffc/control/handoff", headers=self.owner_headers).status_code)

    def test_activation_requires_explicit_handoff_and_configured_cloud_token(self):
        body = {"sha256": "a" * 64, "local_host_stopped": True}
        with patch.dict(os.environ, {"FFC_DISCORD_BOT_TOKEN": ""}):
            self.assertEqual(409, self.client.post("/ffc/control/handoff/activate", headers=self.owner_headers, json=body).status_code)
        with patch("app.routers.ffc_control.discord_preflight", return_value={"ok": True, "ready": True}) as preflight:
            for bad in ({**body, "local_host_stopped": False}, {**body, "local_host_stopped": 1}, {**body, "extra": "invalid"}):
                self.assertEqual(400, self.client.post("/ffc/control/handoff/activate", headers=self.owner_headers, json=bad).status_code)
            response = self.client.post("/ffc/control/handoff/activate", headers=self.owner_headers, json=body)
            self.assertEqual(200, response.status_code)
            self.assertNotIn("synthetic-unconnected-token", response.text)
            preflight.assert_called_once_with()
        self.assertEqual(400, self.client.post("/ffc/control/handoff/deactivate", headers=self.owner_headers, json={"confirm": 1}).status_code)
        self.assertEqual(200, self.client.post("/ffc/control/handoff/deactivate", headers=self.owner_headers, json={"confirm": True}).status_code)

    def test_owner_preflight_is_read_only_and_activation_rechecks_failure(self):
        body = {"sha256": "a" * 64, "local_host_stopped": True}
        with patch("app.routers.ffc_control.discord_preflight", return_value={"ok": True, "ready": True}):
            response = self.client.post("/ffc/control/handoff/preflight", headers=self.owner_headers)
            self.assertTrue(response.json()["ready"])
            self.assertEqual([], self.store.received)
        with patch("app.routers.ffc_control.discord_preflight", side_effect=control.ControlConflict("Wrong application.")):
            response = self.client.post("/ffc/control/handoff/activate", headers=self.owner_headers, json=body)
            self.assertEqual(409, response.status_code)
            self.assertFalse(self.store.state_value["cloud_active"])
            self.assertEqual([], self.store.received)

    def test_import_receipt_does_not_implicitly_activate(self):
        receipt = {"ok": True, "sha256": "a" * 64, "counts": {"profiles": 4}, "already_imported": False}
        with patch("app.routers.ffc_control.import_game_save", return_value=receipt) as import_save:
            response = self.client.post("/ffc/control/handoff/import", headers=self.owner_headers, json={"payload": {}, "sha256": "a" * 64})
            self.assertEqual(200, response.status_code)
            import_save.assert_called_once()
        self.assertFalse(self.store.state_value["cloud_active"])
        with patch("app.routers.ffc_control.import_game_save", side_effect=ValueError("specific private row data")):
            response = self.client.post("/ffc/control/handoff/import", headers=self.owner_headers, json={})
            self.assertEqual(400, response.status_code)
            self.assertNotIn("specific private row data", response.text)

    def test_public_prepared_requires_fresh_worker(self):
        self.store.state_value["runtime_ready"] = False
        response = self.client.get("/ffc/control/health")
        self.assertTrue(response.json()["schema_ready"])
        self.assertFalse(response.json()["prepared"])


class FakeProcess:
    def __init__(self, *, returncode=None, ignores_terminate=False):
        self.returncode = returncode
        self.event = asyncio.Event()
        if returncode is not None:
            self.event.set()
        self.ignores_terminate = ignores_terminate
        self.terminated = 0
        self.killed = 0

    async def wait(self):
        await self.event.wait()
        return self.returncode

    def terminate(self):
        self.terminated += 1
        if not self.ignores_terminate:
            self.returncode = -15
            self.event.set()

    def kill(self):
        self.killed += 1
        self.returncode = -9
        self.event.set()


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.token = "synthetic-only-discord-token-value"
        self.role = "1777777777777777777"
        allowed = sum(ffc_preflight.REQUIRED_PERMISSIONS.values())
        self.responses = {
            "/applications/@me": {"id": control.APPLICATION_ID, "flags": 1 << 19,
                                   "bot": {"id": control.APPLICATION_ID}},
            "/users/@me": {"id": control.APPLICATION_ID, "bot": True},
            "/guilds/" + control.GUILD_ID: {"id": control.GUILD_ID,
                "roles": [{"id": control.GUILD_ID, "permissions": "0"},
                          {"id": self.role, "permissions": str(allowed)}]},
            "/channels/" + control.CHANNEL_ID: {"id": control.CHANNEL_ID,
                "guild_id": control.GUILD_ID, "type": 0, "permission_overwrites": []},
            "/guilds/" + control.GUILD_ID + "/members/" + control.APPLICATION_ID:
                {"user": {"id": control.APPLICATION_ID}, "roles": [self.role]},
        }
        self.requests = []
        def request(path, token):
            self.assertEqual(self.token, token)
            self.requests.append(path)
            return copy.deepcopy(self.responses[path])
        for item in (patch.dict(os.environ, {"FFC_DISCORD_BOT_TOKEN": self.token}),
                     patch.object(ffc_preflight, "_discord_get", side_effect=request)):
            item.start()
            self.addCleanup(item.stop)

    def test_fixed_application_channel_and_permission_verification(self):
        result = ffc_preflight.discord_preflight()
        self.assertTrue(result["ready"])
        self.assertTrue(all(result["permissions"].values()))
        self.assertEqual(set(self.responses), set(self.requests))
        self.assertNotIn(self.token, json.dumps(result))

    def test_wrong_application_or_missing_message_content_fails_before_guild_read(self):
        app = self.responses["/applications/@me"]
        for changes in ({"id": "9999999999999999999"}, {"flags": 0}):
            previous = dict(app)
            app.update(changes)
            self.requests.clear()
            with self.assertRaises(control.ControlConflict):
                ffc_preflight.discord_preflight()
            self.assertEqual(["/applications/@me"], self.requests)
            app.clear()
            app.update(previous)

    def test_member_deny_overrides_role_allow_and_wrong_channel_fails(self):
        channel = self.responses["/channels/" + control.CHANNEL_ID]
        channel["permission_overwrites"] = [{"id": control.APPLICATION_ID, "type": 1,
            "allow": "0", "deny": str(ffc_preflight.REQUIRED_PERMISSIONS["send_messages"])}]
        with self.assertRaisesRegex(control.ControlConflict, "send_messages"):
            ffc_preflight.discord_preflight()
        channel["permission_overwrites"] = []
        channel["guild_id"] = "1999999999999999999"
        with self.assertRaisesRegex(control.ControlConflict, "text channel"):
            ffc_preflight.discord_preflight()

    def test_bot_user_must_match_runtime_application_identity(self):
        self.responses["/applications/@me"].pop("bot")
        self.responses["/users/@me"]["id"] = "1888888888888888888"
        with self.assertRaisesRegex(control.ControlConflict, "bot identity"):
            ffc_preflight.discord_preflight()
        self.assertEqual(["/applications/@me", "/users/@me"], self.requests)

    def test_combined_role_overwrites_then_member_allow_follow_discord_order(self):
        guild = self.responses["/guilds/" + control.GUILD_ID]
        guild["roles"][1]["permissions"] = "0"
        channel = self.responses["/channels/" + control.CHANNEL_ID]
        allowed = sum(ffc_preflight.REQUIRED_PERMISSIONS.values())
        channel["permission_overwrites"] = [
            {"id": control.GUILD_ID, "type": 0, "allow": "0", "deny": str(allowed)},
            {"id": self.role, "type": 0, "allow": str(allowed), "deny": "0"},
        ]
        self.assertTrue(ffc_preflight.discord_preflight()["ready"])
        channel["permission_overwrites"] = [
            {"id": self.role, "type": 0, "allow": "0", "deny": str(allowed)},
            {"id": control.APPLICATION_ID, "type": 1, "allow": str(allowed), "deny": "0"},
        ]
        self.assertTrue(ffc_preflight.discord_preflight()["ready"])


class DiscordTransportTests(unittest.TestCase):
    def test_redirects_and_network_errors_never_forward_or_expose_credentials(self):
        from unittest.mock import Mock
        token = "synthetic-only-discord-token-value"
        for failure in (302, 401, 429, TimeoutError("private " + token)):
            connection = Mock()
            if isinstance(failure, Exception):
                connection.request.side_effect = failure
            else:
                connection.getresponse.return_value.status = failure
            with patch.object(ffc_preflight.http.client, "HTTPSConnection", return_value=connection) as factory:
                with self.assertRaises(control.ControlError) as caught:
                    ffc_preflight._discord_get("/applications/@me", token)
                self.assertNotIn(token, str(caught.exception))
                factory.assert_called_once()
                self.assertEqual("discord.com", factory.call_args.args[0])
                self.assertEqual("GET", connection.request.call_args.args[0])
                self.assertEqual("/api/v10/applications/@me", connection.request.call_args.args[1])
                connection.request.assert_called_once()
                connection.close.assert_called_once()

    def test_success_is_bounded_and_malformed_reply_is_sanitized(self):
        from unittest.mock import Mock
        connection = Mock()
        response = connection.getresponse.return_value
        response.status = 200
        response.read.return_value = b'{"id":"1565167975248695456"}'
        with patch.object(ffc_preflight.http.client, "HTTPSConnection", return_value=connection):
            self.assertEqual(control.APPLICATION_ID, ffc_preflight._discord_get("/applications/@me", "synthetic-token")["id"])
            response.read.assert_called_with(ffc_preflight.MAX_RESPONSE_BYTES + 1)
            response.read.return_value = b"private server error text"
            with self.assertRaises(control.ControlUnavailable) as caught:
                ffc_preflight._discord_get("/applications/@me", "synthetic-token")
            self.assertNotIn("private server", str(caught.exception))


class SupervisorTests(unittest.IsolatedAsyncioTestCase):
    async def test_dormant_worker_launch_is_fixed_and_cleanly_reaped(self):
        process = FakeProcess()
        calls = []
        async def factory(*args, **kwargs):
            calls.append((args, kwargs))
            return process
        supervisor = CloudSupervisor(process_factory=factory, retry_initial=.01, retry_max=.02, stop_timeout=.02)
        supervisor.start()
        supervisor.start()
        await asyncio.sleep(.01)
        await supervisor.stop()
        self.assertEqual(1, len(calls))
        self.assertEqual((sys.executable, "-m", RUNTIME_MODULE), calls[0][0])
        self.assertEqual(1, process.terminated)
        self.assertEqual(0, process.killed)
        self.assertEqual(asyncio.subprocess.DEVNULL, calls[0][1]["stdout"])

    async def test_crash_restarts_with_delay_and_stubborn_child_is_killed(self):
        processes = [FakeProcess(returncode=2), FakeProcess(ignores_terminate=True)]
        calls = []
        async def factory(*args, **kwargs):
            calls.append(args)
            return processes[len(calls) - 1]
        supervisor = CloudSupervisor(process_factory=factory, retry_initial=.01, retry_max=.03, stop_timeout=.01)
        supervisor.start()
        await asyncio.sleep(.04)
        await supervisor.stop()
        self.assertEqual(2, len(calls))
        self.assertEqual(1, processes[1].terminated)
        self.assertEqual(1, processes[1].killed)

    async def test_unconfigured_api_does_not_spawn_a_worker(self):
        settings = Settings(database_url="", ffc_cloud_prepared=True)
        with patch("app.services.ffc_control.get_settings", return_value=settings), patch("app.services.ffc_control.CloudSupervisor") as factory:
            self.assertIsNone(await start_cloud_service())
            factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
