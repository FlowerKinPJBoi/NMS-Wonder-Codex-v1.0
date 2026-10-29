"""Slow cloud storage must leave Discord's event loop free to acknowledge."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
import threading
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from ffc_game.ffc_wilds.async_store import GameIO
from ffc_game.ffc_wilds.cloud_backups import CloudBackups
from ffc_game.ffc_wilds.cloud_control import APPLICATION_ID, CHANNEL_ID, GUILD_ID
from ffc_game.ffc_wilds.cloud_runtime import CloudRuntime
from ffc_game.ffc_wilds.config import CATALOG_PATH, Settings
from ffc_game.ffc_wilds.engine import GameEngine
from ffc_game.ffc_wilds.host_actions import HostActions, UncertainHostAction
from ffc_game.ffc_wilds.migration import export_snapshot
from ffc_game.ffc_wilds.tips import TipSchedule


class ThreadedClient:
    """Real one-worker dispatch around a deterministic in-memory game engine."""

    def __init__(self, engine):
        self.engine = engine
        self.settings = Settings(GUILD_ID, CHANNEL_ID, APPLICATION_ID)
        self.main_thread = threading.get_ident()
        # The data remains SQLite so these tests need no external server; the
        # worker proxy selects exactly the production PostgreSQL dispatch path.
        self.io = GameIO(SimpleNamespace(backend="postgresql", _lock=engine._lock))
        self.game_lock = asyncio.Lock()
        self.game_channel = object()
        self.channel_ready = True
        self._host_failed = False
        self.persist_settings = False
        self.tips = TipSchedule(engine)
        self.sent = []
        self.send_hook = None

    def assert_host(self):
        raise AssertionError("Synchronous ownership checks must not run on the event loop")

    async def db_call(self, operation, *args, **kwargs):
        return await self.io.run(operation, *args, **kwargs)

    async def ensure_host(self):
        await self.db_call(lambda: None)

    def is_ready(self):
        return True

    def get_user(self, user_id):
        if threading.get_ident() != self.main_thread:
            raise AssertionError("Discord caches belong to the event loop")
        return SimpleNamespace(display_name="Synthetic explorer")

    async def send_public(self, text):
        await self.ensure_host()
        self.sent.append(text)
        if self.send_hook:
            await self.send_hook()
        await self.ensure_host()
        return SimpleNamespace(id=1500000000000000000 + len(self.sent))

    async def close_post(self, _event):
        await self.ensure_host()


class RuntimeControlThreadTests(unittest.IsolatedAsyncioTestCase):
    async def test_dormant_control_queries_and_reporting_stay_off_loop(self):
        loop, main_thread = asyncio.get_running_loop(), threading.get_ident()
        stop = asyncio.Event()
        calls = []

        def check(name, result=None):
            self.assertNotEqual(threading.get_ident(), main_thread)
            calls.append(name)
            return result

        def report(*_args):
            check("report")
            loop.call_soon_threadsafe(stop.set)

        store = SimpleNamespace(
            prepare=lambda: check("prepare"),
            state=lambda: check("state", {"cloud_active": False}),
            update_heartbeat=report,
        )
        runtime = CloudRuntime(store, database_url="unused", interval=0.001)
        await runtime.run(stop)
        self.assertEqual(calls, ["prepare", "state", "report"])

    async def test_command_claim_and_all_completion_paths_stay_off_loop(self):
        loop, main_thread = asyncio.get_running_loop(), threading.get_ident()
        for failure, terminal in ((None, "complete"), (ValueError("invalid"), "complete"),
                                  (UncertainHostAction("unknown"), "unknown"),
                                  (RuntimeError("lost"), "unknown")):
            with self.subTest(terminal=terminal, failure=type(failure).__name__):
                stop = asyncio.Event()
                calls = []

                def claim(_worker):
                    self.assertNotEqual(threading.get_ident(), main_thread)
                    calls.append("claim")
                    return {"id": str(uuid.uuid4()), "action": "pause", "arguments": {}, "actor": "PJ"}

                def finish(name, *_args, **_kwargs):
                    self.assertNotEqual(threading.get_ident(), main_thread)
                    calls.append(name)
                    loop.call_soon_threadsafe(stop.set)

                store = SimpleNamespace(claim_next=claim,
                    complete=lambda *a, **kw: finish("complete", *a, **kw),
                    mark_unknown=lambda *a, **kw: finish("unknown", *a, **kw))
                runtime = CloudRuntime(store, database_url="unused")
                client = SimpleNamespace(ensure_host=AsyncMock())
                action = SimpleNamespace(execute=AsyncMock(return_value={"ok": True}, side_effect=failure))
                with patch("ffc_game.ffc_wilds.host_actions.HostActions", return_value=action):
                    await runtime.command_loop(client, SimpleNamespace(create=AsyncMock()), stop)
                self.assertEqual(calls, ["claim", terminal])


class SharedGameWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = GameEngine(":memory:", CATALOG_PATH, clock=lambda: 1800000000.25)
        self.engine.configure_channel(GUILD_ID, CHANNEL_ID)
        self.engine.set_enabled(GUILD_ID, CHANNEL_ID, True)
        self.client = ThreadedClient(self.engine)
        self.main_thread = threading.get_ident()

    async def asyncTearDown(self):
        await self.client.io.close()
        self.engine.close()

    async def test_heartbeat_reads_game_on_worker_and_renders_names_on_loop(self):
        event = self.engine.spawn(GUILD_ID, CHANNEL_ID, kind="fish")
        self.engine.bind_message(event["id"], "1500000000000000001")
        self.engine.claim(GUILD_ID, CHANNEL_ID, "1500000000000000002", "catch", event_id=event["id"])
        stop, loop = asyncio.Event(), asyncio.get_running_loop()
        original_status = self.engine.status

        def status(*args, **kwargs):
            self.assertNotEqual(threading.get_ident(), self.main_thread)
            return original_status(*args, **kwargs)

        received = []

        def report(_worker, _state, snapshot):
            self.assertNotEqual(threading.get_ident(), self.main_thread)
            received.append(snapshot)
            loop.call_soon_threadsafe(stop.set)

        runtime = CloudRuntime(SimpleNamespace(update_heartbeat=report), database_url="unused")
        with patch.object(self.engine, "status", side_effect=status):
            await runtime.heartbeat_loop(self.client, Mock(), stop)
        self.assertEqual(received[0]["counts"]["catches"], 1)
        self.assertEqual(received[0]["recent_activity"][0]["display_name"], "Synthetic explorer")

    async def test_manual_event_prepare_and_commit_share_worker_and_never_replay(self):
        original_transaction = self.engine._transaction
        threads = []

        @contextmanager
        def transaction():
            self.assertNotEqual(threading.get_ident(), self.main_thread)
            threads.append(threading.get_ident())
            with original_transaction() as db:
                yield db

        actions = HostActions(self.client)
        request = str(uuid.uuid4())
        with patch.object(self.engine, "_transaction", transaction):
            result = await actions.execute("frenzy", {"grade": "S"}, request_id=request)
            replay = await actions.execute("frenzy", {"grade": "S"}, request_id=request)
        self.assertEqual(result, replay)
        self.assertEqual(result["seconds"], 240)
        self.assertEqual(len(self.client.sent), 1)
        self.assertEqual(len(set(threads)), 1)
        self.assertEqual(len(threads), 3)  # reserve, commit, replay lookup

    async def test_cancelled_heartbeat_finishes_before_host_cleanup(self):
        entered, release = threading.Event(), threading.Event()
        order = []

        def report(*_args):
            entered.set()
            if not release.wait(3):
                raise AssertionError("Test heartbeat was not released")
            order.append("report_finished")

        runtime = CloudRuntime(SimpleNamespace(update_heartbeat=report), database_url="unused")

        async def running_host():
            try:
                await runtime.heartbeat_loop(self.client, Mock(), asyncio.Event())
            finally:
                order.append("host_cleanup")

        task = asyncio.create_task(running_host())
        self.assertTrue(await asyncio.to_thread(entered.wait, 1))
        try:
            task.cancel()
            await asyncio.sleep(0.01)
            task.cancel()
            await asyncio.sleep(0.01)
            self.assertFalse(task.done())
            self.assertEqual(order, [])
        finally:
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(order, ["report_finished", "host_cleanup"])

    async def test_leadership_loss_after_announcement_prevents_event_commit(self):
        def lost():
            raise RuntimeError("synthetic ownership loss")

        async def lose_after_send():
            self.client.io.operation_guard = lost

        self.client.send_hook = lose_after_send
        with self.assertRaises(UncertainHostAction):
            await HostActions(self.client).execute("power_drive", {"multiplier": 3}, request_id=str(uuid.uuid4()))
        self.assertEqual(len(self.client.sent), 1)
        self.assertFalse(self.engine.activities.drive_status(GUILD_ID, CHANNEL_ID)["active"])
        row = self.engine.db.execute("SELECT result_json FROM requests WHERE operation='host:power_drive'").fetchone()
        self.assertIn('"phase": "prepared"', row[0])

    async def test_backup_export_queues_behind_game_write_on_same_worker(self):
        entered, release = threading.Event(), threading.Event()
        order = []

        def write():
            order.append("write_start")
            entered.set()
            if not release.wait(3):
                raise AssertionError("Test worker was not released")
            order.append("write_done")

        backups = CloudBackups(self.engine, Mock())
        backups.bind_client(self.client)
        original_export = export_snapshot

        def export(*args, **kwargs):
            self.assertNotEqual(threading.get_ident(), self.main_thread)
            order.append("export")
            return original_export(*args, **kwargs)

        def upload(snapshot):
            self.assertNotEqual(threading.get_ident(), self.main_thread)
            self.assertEqual(snapshot["payload"]["guild_id"], GUILD_ID)
            order.append("upload")
            return {"status": "verified"}

        running = asyncio.create_task(self.client.db_call(write))
        self.assertTrue(await asyncio.to_thread(entered.wait, 1))
        try:
            with patch("ffc_game.ffc_wilds.cloud_backups.export_snapshot", side_effect=export), \
                    patch.object(backups, "_upload", side_effect=upload):
                backup = asyncio.create_task(backups.create())
                await asyncio.sleep(0.02)
                self.assertEqual(order, ["write_start"])
                release.set()
                await running
                self.assertEqual(await backup, {"status": "verified"})
        finally:
            release.set()
            await running
        self.assertEqual(order, ["write_start", "write_done", "export", "upload"])

    async def test_cancelled_backup_keeps_lock_until_upload_and_metadata_finish(self):
        entered, release = threading.Event(), threading.Event()
        order = []
        backups = CloudBackups(self.engine, Mock())
        backups.bind_client(self.client)

        def upload(_snapshot):
            order.append("upload_start")
            entered.set()
            if not release.wait(3):
                raise AssertionError("Test upload was not released")
            order.append("metadata_finished")
            return {"status": "verified"}

        with patch.object(backups, "_upload", side_effect=upload) as upload_mock:
            task = asyncio.create_task(backups.create())
            self.assertTrue(await asyncio.to_thread(entered.wait, 1))
            try:
                task.cancel()
                await asyncio.sleep(0.01)
                task.cancel()
                await asyncio.sleep(0.01)
                self.assertFalse(task.done())
                self.assertTrue(backups._lock.locked())
                self.assertEqual(order, ["upload_start"])
            finally:
                release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            upload_mock.assert_called_once()
        self.assertFalse(backups._lock.locked())
        self.assertEqual(order, ["upload_start", "metadata_finished"])


if __name__ == "__main__":
    unittest.main()
