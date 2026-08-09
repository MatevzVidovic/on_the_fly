"""Non-blocking local and PostgreSQL writer locks."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

try:  # POSIX is the supported deployment target; keep import errors readable.
    import fcntl
except ImportError:  # pragma: no cover - platforms without POSIX locking
    fcntl = None  # type: ignore[assignment]


class LockUnavailable(RuntimeError):
    pass


class WriterLockLost(LockUnavailable):
    """The dedicated advisory-lock session cannot prove it is still alive."""


def advisory_key(database: str, schema: str, table: str) -> int:
    """Deterministic signed bigint accepted by PostgreSQL pg_advisory_lock."""
    digest = hashlib.sha256(f"integration-core:{database}:{schema}:{table}".encode()).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


class LocalStateLock(AbstractContextManager["LocalStateLock"]):
    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle: Any | None = None

    def __enter__(self) -> "LocalStateLock":
        if fcntl is None:
            raise RuntimeError("local state locking requires POSIX fcntl")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            self._handle.close()
            self._handle = None
            raise LockUnavailable(f"another process holds {self.path}") from error
        return self

    def __exit__(self, *_: object) -> None:
        if self._handle is not None:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            self._handle.close()
            self._handle = None


class PostgresWriterLock(AbstractContextManager["PostgresWriterLock"]):
    """A session-level advisory lock; caller must keep the connection alive."""
    def __init__(self, connection: Any, database: str, schema: str, table: str) -> None:
        self.connection, self.key = connection, advisory_key(database, schema, table)
        self._held = False

    def __enter__(self) -> "PostgresWriterLock":
        self.acquire()
        return self

    def acquire(self) -> None:
        if self._held:
            raise RuntimeError("PostgreSQL writer advisory lock is already held")
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(%s)", (self.key,))
            acquired = cursor.fetchone()[0]
        if not acquired:
            raise LockUnavailable("another writer holds the PostgreSQL advisory lock")
        self._held = True

    def release(self) -> None:
        if not self._held:
            return
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", (self.key,))
            released = cursor.fetchone()[0]
        self._held = False
        if not released:
            raise WriterLockLost("PostgreSQL writer advisory lock was not held by its dedicated session")

    def __exit__(self, exc_type: object, *_: object) -> None:
        if self._held:
            try:
                self.release()
            except Exception:
                # Do not mask the lock-loss/data error that caused teardown;
                # a dead session has already released its advisory lock.
                if exc_type is None:
                    raise
            finally:
                self._held = False

    def ensure_held(self) -> None:
        """Prove the original lock session is live; never reacquire mid-run."""
        if not self._held:
            raise WriterLockLost("PostgreSQL writer advisory lock is no longer held")
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception as error:
            self._held = False
            raise WriterLockLost("PostgreSQL writer advisory-lock session was lost; refusing to continue") from error


class WriterRunContext(AbstractContextManager["WriterRunContext"]):
    """Acquire the local lock, then a dedicated autocommit PostgreSQL lock.

    The separate connection prevents a destination transaction rollback or
    reconnect from accidentally releasing the run-wide advisory lock.
    """
    def __init__(
        self,
        local_lock_path: Path,
        connect_lock_database: Callable[[], Any],
        database: str,
        schema: str,
        table: str,
    ) -> None:
        self._local = LocalStateLock(local_lock_path)
        self._connect = connect_lock_database
        self._identity = (database, schema, table)
        self._connection: Any | None = None
        self._postgres: PostgresWriterLock | None = None
        self._page_mutation_active = False

    @property
    def connection(self) -> Any:
        if self._connection is None:
            raise RuntimeError("writer run context is not active")
        return self._connection

    def __enter__(self) -> "WriterRunContext":
        self._local.__enter__()
        try:
            self._connection = self._connect()
            # psycopg supports assignment; use an explicit failure rather than
            # silently taking a transaction-scoped/dirty lock connection.
            self._connection.autocommit = True
            database, schema, table = self._identity
            self._postgres = PostgresWriterLock(self._connection, database, schema, table)
            self._postgres.__enter__()
        except BaseException:
            if self._connection is not None:
                close = getattr(self._connection, "close", None)
                if close is not None:
                    close()
                self._connection = None
            self._local.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        try:
            if self._postgres is not None:
                self._postgres.__exit__(exc_type, exc, traceback)
        finally:
            self._postgres = None
            if self._connection is not None:
                close = getattr(self._connection, "close", None)
                if close is not None:
                    close()
                self._connection = None
            self._local.__exit__(exc_type, exc, traceback)

    def ensure_held(self) -> None:
        if self._postgres is None:
            raise WriterLockLost("writer run context is not active")
        self._postgres.ensure_held()

    def begin_page_mutation(self, destination_connection: Any) -> None:
        """Atomically protect the active page with a transaction lock.

        A session advisory lock protects the run between pages.  PostgreSQL
        locks of the same key conflict across sessions, so page mutation uses
        a fail-closed handoff: release the verified session lock, immediately
        try the destination transaction lock, and write only if it succeeds.
        A competing writer during that handoff causes an error before writes.
        """
        if self._page_mutation_active:
            raise RuntimeError("a page mutation is already active")
        self.ensure_held()
        assert self._postgres is not None
        self._postgres.release()
        try:
            with destination_connection.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_xact_lock(%s)", (self._postgres.key,))
                acquired = cursor.fetchone()[0]
        except Exception:
            self._restore_session_lock()
            raise
        if not acquired:
            self._restore_session_lock()
            raise LockUnavailable("could not acquire page transaction advisory lock; no rows were written")
        self._page_mutation_active = True

    def end_page_mutation(self) -> None:
        """Restore the between-pages session lock after transaction end."""
        if not self._page_mutation_active:
            raise RuntimeError("no page mutation is active")
        try:
            self._restore_session_lock()
        finally:
            self._page_mutation_active = False

    def _restore_session_lock(self) -> None:
        if self._postgres is None:
            raise WriterLockLost("writer run context is not active")
        try:
            self._postgres.acquire()
        except Exception as error:
            raise WriterLockLost("could not restore PostgreSQL writer advisory lock after page handoff") from error
