"""Serialize cloud database work without blocking Discord's event loop.

GameIO uses the engine's existing connection and lock; it never reconnects or
weakens ownership checks. Callbacks must be synchronous database operations.
They must not mutate Discord/client state from the worker thread. SQLite keeps
the local host's inline behavior. Await close() before closing the engine.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import inspect
import threading
from typing import Any, Callable, TypeVar
import weakref


T = TypeVar("T")


class GuardFailed(RuntimeError):
    """Only an ownership-guard failure, distinct from an operation failure."""


# A second live owner must not create another executor for the same PG engine.
# The weak owner avoids retaining an otherwise-unused engine forever. Submitted
# bound callbacks retain their owner until their work has actually completed.
_OWNER_LOCK = threading.Lock()
_OWNERS: dict[int, weakref.ReferenceType["GameIO"]] = {}


async def _completion_before_cancel(future: asyncio.Future[T]) -> T:
    """Delay cancellation until the shielded work is irrevocably finished.

Repeated Task.cancel() calls cannot release an enclosing game lock while a
thread is still committing. If both cancellation and an operation failure
occur, consume the latter and propagate cancellation after completion.
"""
    cancelled = False
    while not future.done():
        try:
            await asyncio.shield(future)
        except asyncio.CancelledError:
            cancelled = True
        except BaseException:
            # The operation's exception is re-raised by result() below, unless
            # the caller was cancelled while waiting for that operation.
            break
    if cancelled:
        try:
            future.result()
        except BaseException:
            pass
        raise asyncio.CancelledError
    return future.result()


def _require_sync_result(value: T) -> T:
    if inspect.isawaitable(value):
        if inspect.iscoroutine(value):
            value.close()
        raise TypeError("GameIO callbacks must be synchronous database operations.")
    return value


class GameIO:
    """One serialized database worker for one PostgreSQL game engine.

    ``operation_guard`` is deliberately public so an adapter may supply a
    dynamic guard or replace it in tests. It executes under the engine lock
    immediately before each guarded operation. ``guard=False`` is reserved for
    explicitly chosen startup, inspection, and cleanup operations.

    Cancelling run() does not abandon submitted work. Cancellation is delivered
    only after that work finishes, allowing callers to keep their game lock and
    connection alive until any commit is settled.
    """

    def __init__(self, engine, operation_guard: Callable[[], None] | None = None):
        if operation_guard is not None and not callable(operation_guard):
            raise TypeError("operation_guard must be callable or None.")
        self.engine = engine
        self.operation_guard = operation_guard
        self._threaded = getattr(engine, "backend", "sqlite") == "postgresql"
        self._executor: ThreadPoolExecutor | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._closing = False
        self._closed = False
        self._guard_failed = False
        self._close_task: asyncio.Task[None] | None = None
        self._owner_ref: weakref.ReferenceType[GameIO] | None = None
        if self._threaded:
            with _OWNER_LOCK:
                previous_ref = _OWNERS.get(id(engine))
                previous = previous_ref() if previous_ref is not None else None
                if previous is not None and not previous._closed:
                    raise RuntimeError("A GameIO worker already owns this game engine.")
                self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ffc-game-db")
                self._owner_ref = weakref.ref(self)
                _OWNERS[id(engine)] = self._owner_ref

    @property
    def closed(self) -> bool:
        return self._closed

    def _running_loop(self) -> asyncio.AbstractEventLoop:
        loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = loop
        elif loop is not self._loop:
            raise RuntimeError("A GameIO worker must stay on its original event loop.")
        return loop

    def _invoke(self, operation: Callable[..., T], args: tuple, kwargs: dict, guard: bool) -> T:
        with self.engine._lock:
            if guard and self._guard_failed:
                raise GuardFailed("Cloud game ownership could not be verified.")
            operation_guard = self.operation_guard
            if guard and operation_guard is not None:
                try:
                    _require_sync_result(operation_guard())
                except Exception:
                    # Fence in the worker immediately. A second queued operation
                    # must not run before the event loop observes this failure
                    # and marks its Discord client as permanently closed.
                    self._guard_failed = True
                    # A guard may wrap connection credentials in its exception.
                    # Do not propagate its detail or chained traceback.
                    raise GuardFailed("Cloud game ownership could not be verified.") from None
            return _require_sync_result(operation(*args, **kwargs))

    async def run(self, operation: Callable[..., T], *args: Any,
                  guard: bool = True, **kwargs: Any) -> T:
        if self._closing or self._closed:
            raise RuntimeError("The GameIO worker is closing or closed.")
        if not callable(operation):
            raise TypeError("A synchronous database operation is required.")
        if type(guard) is not bool:
            raise TypeError("guard must be True or False.")
        if not self._threaded:
            return self._invoke(operation, args, kwargs, guard)
        loop = self._running_loop()
        future = loop.run_in_executor(self._executor, self._invoke, operation, args, kwargs, guard)
        return await _completion_before_cancel(future)

    def _release_owner(self) -> None:
        if self._owner_ref is not None:
            with _OWNER_LOCK:
                if _OWNERS.get(id(self.engine)) is self._owner_ref:
                    del _OWNERS[id(self.engine)]
            self._owner_ref = None

    async def _finish_close(self) -> None:
        # shutdown must not run on the game executor itself, nor block Discord's
        # event loop. A short-lived joining thread avoids borrowing or changing
        # the application's default executor. Only the game executor runs DB
        # operations, and shutdown drains running AND already-queued operations.
        if self._executor is not None:
            finished = threading.Event()
            errors: list[BaseException] = []

            def shutdown():
                try:
                    self._executor.shutdown(wait=True, cancel_futures=False)
                except BaseException as error:
                    errors.append(error)
                finally:
                    finished.set()

            joiner = threading.Thread(target=shutdown, name="ffc-game-db-close", daemon=True)
            joiner.start()
            while not finished.is_set() or joiner.is_alive():
                await asyncio.sleep(0.005)
            joiner.join(timeout=0)
            if errors:
                raise errors[0]
        self._closed = True
        self._release_owner()

    async def close(self) -> None:
        if self._closed:
            return
        if not self._threaded:
            self._closing = True
            self._closed = True
            return
        self._running_loop()
        if self._close_task is None:
            self._closing = True
            self._close_task = asyncio.create_task(self._finish_close(), name="ffc-game-db-close")
        await _completion_before_cancel(self._close_task)
