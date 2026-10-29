"""Dormant by default; one PostgreSQL-fenced Discord host after handoff."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
import time
import uuid

from .cloud_control import APPLICATION_ID, GUILD_ID, CHANNEL_ID, ControlStore, leader_key
from .config import CATALOG_PATH, Settings

LOG = logging.getLogger("ffc_wilds.cloud")
HEARTBEAT_INTERVAL = 3
BACKUP_INTERVAL = 21600
SNAPSHOT_KEYS = {"bot_ready", "channel", "galaxy", "active_event", "effects", "counts",
                 "recent_activity", "last_backup", "available_actions", "error_code"}


async def wait_or_stop(stop, seconds):
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except asyncio.TimeoutError:
        pass


class CloudRuntime:
    def __init__(self, store, *, database_url, token="", engine_factory=None, bot_factory=None,
                 backup_factory=None, interval=HEARTBEAT_INTERVAL):
        self.store, self.database_url, self.token = store, database_url, token
        self.worker_id = str(uuid.uuid4())
        self.engine_factory, self.bot_factory = engine_factory, bot_factory
        self.backup_factory = backup_factory
        self.interval = interval

    def report(self, state, snapshot=None):
        self.store.update_heartbeat(self.worker_id, state, snapshot or {"bot_ready": False})

    async def run(self, stop):
        self.store.prepare()
        while not stop.is_set():
            state = self.store.state()
            if not state["cloud_active"]:
                # No game engine, Discord client, token lookup, or gateway here.
                self.report("prepared")
            elif not self.token.strip():
                self.report("waiting_for_token")
            elif not state.get("import_digest"):
                self.report("waiting_for_import")
            else:
                await self.run_active(stop, state)
            await wait_or_stop(stop, self.interval)

    async def run_active(self, stop, activation):
        from .engine import GameEngine
        from .migration import get_import_receipt

        engine = (self.engine_factory or GameEngine)(self.database_url, CATALOG_PATH,
                                                     schema=self.store.game_schema)
        key = leader_key(self.store.game_schema)
        client = None
        tasks = []
        generation = activation["activation_generation"]
        try:
            receipt = get_import_receipt(engine)
            if (not receipt or receipt.get("sha256") != activation["import_digest"]
                    or receipt.get("application_id") != APPLICATION_ID
                    or receipt.get("guild_id") != GUILD_ID or receipt.get("channel_id") != CHANNEL_ID):
                self.report("waiting_for_import")
                return
            if not engine.db.try_leader_lock(key):
                self.report("standby")
                return

            def guard():
                if not engine.db.verify_leader_lock(key):
                    raise RuntimeError("cloud_leadership_lost")
                current = self.store.state()
                if not current["cloud_active"] or current["activation_generation"] != generation:
                    raise RuntimeError("cloud_activation_changed")

            guard()
            mode = engine.status(GUILD_ID, CHANNEL_ID).get("mode", "community")
            settings = Settings(GUILD_ID, CHANNEL_ID, APPLICATION_ID, mode=mode)
            if self.bot_factory is None:
                from .discord_bot import WildsBot
                factory = WildsBot
            else:
                factory = self.bot_factory
            if self.backup_factory is None:
                from .cloud_backups import CloudBackups
                backups = CloudBackups(engine, self.store)
            else:
                backups = self.backup_factory(engine, self.store)
            client = factory(settings, engine=engine, operation_guard=guard,
                backup_callback=backups.create, persist_settings=False, automatic_backups=False)
            self.report("connecting")
            tasks = [asyncio.create_task(client.start(self.token), name="ffc-discord"),
                     asyncio.create_task(self.heartbeat_loop(client, guard, stop), name="ffc-heartbeat"),
                     asyncio.create_task(self.command_loop(client, backups, stop), name="ffc-controls"),
                     asyncio.create_task(self.backup_loop(client, backups, stop), name="ffc-backups"),
                     asyncio.create_task(stop.wait(), name="ffc-stop")]
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                if not task.cancelled() and task.exception():
                    raise task.exception()
            if not stop.is_set():
                raise RuntimeError("cloud_connection_stopped")
        finally:
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            if client is not None:
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(client.close(), timeout=10)
            with contextlib.suppress(Exception):
                engine.db.release_leader_lock(key)
            engine.close()

    async def heartbeat_loop(self, client, guard, stop):
        from .host_actions import status_snapshot
        while not stop.is_set():
            guard()
            snapshot = {key: value for key, value in status_snapshot(client).items() if key in SNAPSHOT_KEYS}
            state = ("running" if snapshot["channel"].get("enabled") else "paused") if snapshot["bot_ready"] else "connecting"
            self.report(state, snapshot)
            await wait_or_stop(stop, self.interval)

    async def command_loop(self, client, backups, stop):
        from .host_actions import HostActions, UncertainHostAction
        actions = HostActions(client, backup_callback=backups.create)
        while not stop.is_set():
            client.assert_host()
            command = self.store.claim_next(self.worker_id)
            if command is not None:
                try:
                    result = await actions.execute(command["action"], command["arguments"],
                        request_id=command["id"], actor=command["actor"])
                except asyncio.CancelledError:
                    raise
                except ValueError as exc:
                    self.store.complete(command["id"], self.worker_id,
                        error=str(exc))
                except UncertainHostAction:
                    self.store.mark_unknown(command["id"], self.worker_id)
                except Exception:
                    # A lost response can follow a successful remote mutation.
                    self.store.mark_unknown(command["id"], self.worker_id)
                    client.assert_host()
                else:
                    self.store.complete(command["id"], self.worker_id, result=result,
                        error=None if result.get("ok") else "The action could not complete.")
            await wait_or_stop(stop, 0.75)

    async def backup_loop(self, client, backups, stop):
        next_backup = 0.0
        while not stop.is_set():
            if client.is_ready() and client.channel_ready and time.monotonic() >= next_backup:
                client.assert_host()
                try:
                    await backups.create()
                except Exception:
                    # Retry in five minutes without delaying game appearances.
                    next_backup = time.monotonic() + 300
                    LOG.warning("Private FFC backup unavailable; retry scheduled.")
                else:
                    next_backup = time.monotonic() + BACKUP_INTERVAL
            await wait_or_stop(stop, self.interval)


async def main_async():
    database_url = os.environ.get("FFC_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
    store = ControlStore(database_url)
    runtime = CloudRuntime(store, database_url=database_url,
                           token=os.environ.get("FFC_DISCORD_BOT_TOKEN", ""))
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for value in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(value, stop.set)
    succeeded = False
    try:
        await runtime.run(stop)
        succeeded = True
    except Exception:
        with contextlib.suppress(Exception):
            runtime.report("error", {"bot_ready": False, "error_code": "host_unavailable"})
        # Never serialize exception text that may contain a connection secret.
        LOG.error("FFC cloud host stopped safely; supervised restart will retry.")
        return 1
    finally:
        if succeeded:
            with contextlib.suppress(Exception):
                runtime.report("offline")
    return 0


def main():
    logging.basicConfig(level=logging.WARNING)
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
