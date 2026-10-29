"""The cloud DB worker must not delay Gateway acknowledgements or outlive close."""
from __future__ import annotations

import asyncio
import threading
import time
import unittest

from ffc_game.ffc_wilds.async_store import GameIO, GuardFailed


class Engine:
    def __init__(self, backend="postgresql"):
        self.backend = backend
        self._lock = threading.RLock()
        self.db = object()  # Identity must survive every call; no reconnection.


async def entered(event: threading.Event):
    deadline = time.monotonic() + 2
    while not event.is_set():
        if time.monotonic() >= deadline:
            raise AssertionError("The synthetic worker did not start.")
        await asyncio.sleep(0.001)


class GameIOTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.workers = []
        self.releases = []
        # The restricted test runner can delay a cross-thread selector wakeup
        # until its next timer. Keep a small timer active, as the real Gateway
        # heartbeat/scheduler also do. This never performs DB work or releases
        # any test latch; the responsiveness test still checks independent ticks.
        async def pulse():
            while True:
                await asyncio.sleep(0.01)
        self.pulse = asyncio.create_task(pulse())

    def worker(self, engine=None, guard=None):
        io = GameIO(engine or Engine(), guard)
        self.workers.append(io)
        return io

    def release_event(self):
        event = threading.Event()
        self.releases.append(event)
        return event

    async def asyncTearDown(self):
        for release in self.releases:
            release.set()
        for io in self.workers:
            await io.close()
        self.pulse.cancel()
        await asyncio.gather(self.pulse, return_exceptions=True)

    async def test_slow_cloud_operation_leaves_event_loop_responsive(self):
        io = self.worker()
        started, release = threading.Event(), self.release_event()
        main_thread = threading.get_ident()
        original_connection = io.engine.db

        def operation():
            started.set()
            if not release.wait(2):
                raise AssertionError("The event loop could not release the DB worker.")
            return threading.get_ident(), io.engine.db

        task = asyncio.create_task(io.run(operation))
        await entered(started)
        ticks = 0
        for _ in range(5):
            await asyncio.sleep(0.005)
            ticks += 1
        self.assertFalse(task.done())
        release.set()
        thread, connection = await task
        self.assertEqual(ticks, 5)
        self.assertNotEqual(thread, main_thread)
        self.assertIs(connection, original_connection)

    async def test_operations_are_serialized_on_one_worker_and_under_engine_lock(self):
        io = self.worker()
        started, release = threading.Event(), self.release_event()
        order, threads, lock_held = [], set(), []

        def operation(number):
            threads.add(threading.get_ident())
            lock_held.append(io.engine._lock._is_owned())
            order.append((number, "start"))
            if number == 1:
                started.set()
                if not release.wait(2):
                    raise AssertionError("Release not delivered.")
            order.append((number, "finish"))
            return number

        first = asyncio.create_task(io.run(operation, 1))
        await entered(started)
        second = asyncio.create_task(io.run(operation, 2))
        third = asyncio.create_task(io.run(operation, 3))
        await asyncio.sleep(0.01)
        self.assertEqual(order, [(1, "start")])
        release.set()
        self.assertEqual(await asyncio.gather(first, second, third), [1, 2, 3])
        self.assertEqual(order, [(1, "start"), (1, "finish"), (2, "start"), (2, "finish"),
                                 (3, "start"), (3, "finish")])
        self.assertEqual(len(threads), 1)
        self.assertTrue(all(lock_held))

    async def test_cancel_waits_for_commit_before_releasing_outer_game_lock(self):
        io = self.worker()
        started, release = threading.Event(), self.release_event()
        outer = asyncio.Lock()
        commits, cleanup = [], []

        def commit():
            started.set()
            if not release.wait(2):
                raise AssertionError("Release not delivered.")
            commits.append("committed")

        async def action():
            try:
                async with outer:
                    await io.run(commit)
            finally:
                cleanup.append(list(commits))

        task = asyncio.create_task(action())
        await entered(started)
        task.cancel()
        await asyncio.sleep(0.01)
        task.cancel()  # A second cancellation must not escape the drain.
        await asyncio.sleep(0.01)
        self.assertFalse(task.done())
        self.assertTrue(outer.locked())
        self.assertEqual(cleanup, [])
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertFalse(outer.locked())
        self.assertEqual(cleanup, [["committed"]])

    async def test_guard_failure_is_distinct_and_prevents_operation(self):
        calls = []
        engine = Engine()

        def guard():
            self.assertTrue(engine._lock._is_owned())
            calls.append("guard")
            raise RuntimeError("synthetic private connection detail")

        io = self.worker(engine, guard)
        with self.assertRaises(GuardFailed) as error:
            await io.run(lambda: calls.append("operation"))
        self.assertEqual(calls, ["guard"])
        self.assertNotIn("private", str(error.exception))
        self.assertIsNone(error.exception.__cause__)
        self.assertTrue(error.exception.__suppress_context__)

    async def test_operation_failure_is_not_misreported_as_guard_failure(self):
        original = ValueError("synthetic operation failure")
        calls = []
        io = self.worker(guard=lambda: calls.append("guard"))

        def operation():
            raise original

        with self.assertRaises(ValueError) as error:
            await io.run(operation)
        self.assertIs(error.exception, original)
        self.assertNotIsInstance(error.exception, GuardFailed)
        self.assertEqual(calls, ["guard"])
        self.assertEqual(await io.run(lambda: "still owned"), "still owned")

    async def test_guard_false_and_dynamic_guard_are_respected(self):
        io = self.worker(guard=lambda: (_ for _ in ()).throw(RuntimeError("fenced")))
        self.assertEqual(await io.run(lambda a, *, b: a + b, 2, b=3, guard=False), 5)
        io.operation_guard = lambda: None
        self.assertEqual(await io.run(lambda: 7), 7)
        io.operation_guard = lambda: (_ for _ in ()).throw(RuntimeError("fenced"))
        with self.assertRaises(GuardFailed):
            await io.run(lambda: 7)
        # A different guard cannot undo a failed ownership check on this owner.
        io.operation_guard = lambda: None
        with self.assertRaises(GuardFailed):
            await io.run(lambda: 7)
        self.assertEqual(await io.run(lambda: "cleanup", guard=False), "cleanup")

    async def test_first_guard_failure_fences_already_queued_operations(self):
        started, release = threading.Event(), self.release_event()
        guard_calls, writes = [], []

        def transient_guard():
            guard_calls.append(True)
            if len(guard_calls) == 1:
                started.set()
                if not release.wait(2):
                    raise AssertionError("Release not delivered.")
                raise RuntimeError("synthetic transient guard failure")
            # A later guard would succeed, but that must not revive this owner.

        io = self.worker(guard=transient_guard)
        first = asyncio.create_task(io.run(lambda: writes.append("first")))
        await entered(started)
        second = asyncio.create_task(io.run(lambda: writes.append("second")))
        await asyncio.sleep(0.01)
        release.set()
        results = await asyncio.gather(first, second, return_exceptions=True)
        self.assertTrue(all(isinstance(result, GuardFailed) for result in results))
        self.assertEqual(guard_calls, [True])
        self.assertEqual(writes, [])

    async def test_sqlite_execution_stays_on_calling_thread(self):
        engine = Engine("sqlite")
        io = self.worker(engine)
        self.assertEqual(await io.run(threading.get_ident), threading.get_ident())
        self.assertIsNone(io._executor)
        self.assertTrue(await io.run(engine._lock._is_owned))

    async def test_duplicate_cloud_owner_refused_until_original_is_closed(self):
        engine = Engine()
        first = self.worker(engine)
        with self.assertRaisesRegex(RuntimeError, "already owns"):
            GameIO(engine)
        await first.close()
        replacement = self.worker(engine)
        self.assertEqual(await replacement.run(lambda: 42), 42)

    async def test_close_drains_worker_and_rejects_new_operations(self):
        io = self.worker()
        started, release = threading.Event(), self.release_event()
        done = []

        def operation():
            started.set()
            if not release.wait(2):
                raise AssertionError("Release not delivered.")
            done.append(True)

        action = asyncio.create_task(io.run(operation))
        await entered(started)
        closing = asyncio.create_task(io.close())
        await asyncio.sleep(0.01)
        self.assertFalse(closing.done())
        with self.assertRaisesRegex(RuntimeError, "closing or closed"):
            await io.run(lambda: None)
        release.set()
        await asyncio.gather(action, closing)
        self.assertEqual(done, [True])
        self.assertTrue(io.closed)
        await io.close()  # Idempotent.

    async def test_cancelled_close_still_drains_before_propagating(self):
        io = self.worker()
        started, release = threading.Event(), self.release_event()
        done = []

        def operation():
            started.set()
            if not release.wait(2):
                raise AssertionError("Release not delivered.")
            done.append(True)

        action = asyncio.create_task(io.run(operation))
        await entered(started)
        closing = asyncio.create_task(io.close())
        await asyncio.sleep(0)
        closing.cancel()
        await asyncio.sleep(0.01)
        closing.cancel()
        await asyncio.sleep(0.01)
        self.assertFalse(closing.done())
        self.assertFalse(io.closed)
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await closing
        await action
        self.assertEqual(done, [True])
        self.assertTrue(io.closed)

    async def test_cancel_consumes_late_operation_failure_without_abandoning_work(self):
        io = self.worker()
        started, release = threading.Event(), self.release_event()
        completed = []

        def operation():
            started.set()
            if not release.wait(2):
                raise AssertionError("Release not delivered.")
            completed.append(True)
            raise ValueError("synthetic late failure")

        task = asyncio.create_task(io.run(operation))
        await entered(started)
        task.cancel()
        await asyncio.sleep(0.01)
        self.assertFalse(task.done())
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(completed, [True])

    async def test_async_operation_is_rejected_without_running_its_body(self):
        io = self.worker()
        calls = []

        async def operation():
            calls.append(True)

        with self.assertRaisesRegex(TypeError, "synchronous"):
            await io.run(operation)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
