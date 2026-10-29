"""FFC's isolated cloud controls and supervised, dormant-by-default worker."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from functools import lru_cache
from pathlib import Path

from ffc_game.ffc_wilds.cloud_control import APPLICATION_ID, CHANNEL_ID, GUILD_ID, ControlStore

from ..config import get_settings

logger = logging.getLogger(__name__)
RUNTIME_MODULE = "ffc_game.ffc_wilds.cloud_runtime"
API_ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def get_control_store() -> ControlStore:
    # DATABASE_URL remains in the existing cloud environment; never return or
    # log it and never place it in a process command line.
    return ControlStore(get_settings().database_url)


def import_game_save(snapshot: dict) -> dict:
    """Owner-only route helper; game importer validates every table and value."""
    from ffc_game.ffc_wilds.config import CATALOG_PATH
    from ffc_game.ffc_wilds.engine import GameEngine
    from ffc_game.ffc_wilds.migration import import_snapshot, validate_snapshot

    checked = validate_snapshot(snapshot, expected_application_id=APPLICATION_ID,
                                expected_guild_id=GUILD_ID, expected_channel_id=CHANNEL_ID)

    def perform() -> dict:
        engine = GameEngine(get_settings().database_url, CATALOG_PATH, schema="ffc_wilds")
        try:
            return import_snapshot(checked, engine, expected_application_id=APPLICATION_ID,
                                   expected_guild_id=GUILD_ID, expected_channel_id=CHANNEL_ID)
        finally:
            engine.close()

    return get_control_store().import_verified(perform)


class CloudSupervisor:
    """One child per API process; the database elects the actual game leader.

    Child output is deliberately not forwarded: status/error codes are stored
    in the control plane. The API logs only fixed lifecycle events/exit codes.
    This also prevents accidental credentials in a child traceback from being
    recorded by Wonder Codex's general request-error logging.
    """

    def __init__(self, *, process_factory=None, retry_initial: float = 5.0,
                 retry_max: float = 60.0, stop_timeout: float = 15.0):
        self._factory = process_factory or asyncio.create_subprocess_exec
        self._retry_initial = retry_initial
        self._retry_max = retry_max
        self._stop_timeout = stop_timeout
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._process = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="ffc-cloud-supervisor")

    async def _reap(self) -> None:
        process = self._process
        if process is None:
            return
        if process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(process.wait(), timeout=self._stop_timeout)
            except asyncio.TimeoutError:
                if process.returncode is None:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                await process.wait()
        self._process = None

    async def _pause(self, delay: float) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass

    async def _run(self) -> None:
        retry = self._retry_initial
        try:
            while not self._stop.is_set():
                began = time.monotonic()
                try:
                    self._process = await self._factory(
                        sys.executable, "-m", RUNTIME_MODULE, cwd=str(API_ROOT),
                        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.STDOUT,
                        env={**os.environ, "PYTHONUNBUFFERED": "1"},
                    )
                    waiter = asyncio.create_task(self._process.wait())
                    stop_waiter = asyncio.create_task(self._stop.wait())
                    try:
                        await asyncio.wait({waiter, stop_waiter}, return_when=asyncio.FIRST_COMPLETED)
                        if self._stop.is_set():
                            await self._reap()
                            break
                        logger.warning("FFC cloud worker exited; retrying after a delay (code %s).", waiter.result())
                        self._process = None
                    finally:
                        stop_waiter.cancel()
                        await asyncio.gather(stop_waiter, return_exceptions=True)
                        if not waiter.done():
                            waiter.cancel()
                        await asyncio.gather(waiter, return_exceptions=True)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning("FFC cloud worker could not start (%s).", type(exc).__name__)
                    await self._reap()
                if time.monotonic() - began >= 60:
                    retry = self._retry_initial
                await self._pause(retry)
                retry = min(self._retry_max, max(self._retry_initial, retry * 2))
        finally:
            await self._reap()

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task
            self._task = None


async def start_cloud_service() -> CloudSupervisor | None:
    if not get_settings().ffc_cloud_prepared or not get_settings().database_url.strip():
        return None
    try:
        await asyncio.to_thread(get_control_store().prepare)
    except Exception as exc:
        # The isolated game feature must never take the main website down.
        # The worker retries preparation; public health stays truthful meanwhile.
        logger.warning("FFC cloud preparation is waiting for its database (%s).", type(exc).__name__)
    supervisor = CloudSupervisor()
    supervisor.start()
    return supervisor
