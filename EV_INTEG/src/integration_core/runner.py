"""Database-neutral page runner with commit-before-checkpoint semantics."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from time import sleep as default_sleep
from typing import Any, Generic, TypeVar

from .signals import InterruptController
from .locks import LockUnavailable
from .state import Checkpoint, RunIdentity, read_checkpoint, save_checkpoint


Row = TypeVar("Row")


@dataclass(frozen=True, slots=True)
class Page(Generic[Row]):
    rows: tuple[Row, ...]
    next_cursor: tuple[Any, ...]


@dataclass(frozen=True, slots=True)
class PageRunResult:
    checkpoint: Checkpoint
    stopped_by_signal: bool


class PageRunner(Generic[Row]):
    """Run pages at-least-once: destination commit always precedes checkpoint."""
    def __init__(
        self,
        checkpoint_path: Path,
        identity: RunIdentity,
        fetch_page: Callable[[tuple[Any, ...] | None], Page[Row] | None],
        write_page: Callable[[tuple[Row, ...]], None],
        transaction: Callable[[], AbstractContextManager[Any]],
        run_context: Callable[[], AbstractContextManager[Any]],
        *,
        prepare_checkpoint: Callable[[Checkpoint], Checkpoint | None] | None = None,
        reconnect: Callable[[], None] | None = None,
        is_reconnectable: Callable[[Exception], bool] | None = None,
        max_reconnect_attempts: int = 3,
        reconnect_initial_delay_seconds: float = 1.0,
        reconnect_max_delay_seconds: float = 30.0,
        sleep: Callable[[float], None] = default_sleep,
        interrupts: InterruptController | None = None,
        on_page_committed: Callable[[Page[Row]], None] | None = None,
        on_page_size_error: Callable[[Exception], bool] | None = None,
        complete_checkpoint: Callable[[Checkpoint], Checkpoint] | None = None,
    ) -> None:
        self.path, self.identity = checkpoint_path, identity
        self.fetch_page, self.write_page, self.transaction = fetch_page, write_page, transaction
        self.run_context = run_context
        self.prepare_checkpoint = prepare_checkpoint
        if (reconnect is None) != (is_reconnectable is None):
            raise ValueError("reconnect and is_reconnectable must be provided together")
        if max_reconnect_attempts < 0:
            raise ValueError("max_reconnect_attempts must not be negative")
        if reconnect_initial_delay_seconds < 0 or reconnect_max_delay_seconds < reconnect_initial_delay_seconds:
            raise ValueError("reconnect delays must be non-negative and ordered")
        self.reconnect, self.is_reconnectable = reconnect, is_reconnectable
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_initial_delay_seconds = reconnect_initial_delay_seconds
        self.reconnect_max_delay_seconds = reconnect_max_delay_seconds
        self.sleep = sleep
        self.interrupts = interrupts or InterruptController()
        self.on_page_committed = on_page_committed
        self.on_page_size_error = on_page_size_error
        self.complete_checkpoint = complete_checkpoint

    def run(self, *, fresh: bool = False, context: Any | None = None) -> PageRunResult:
        # The writer context intentionally encloses checkpoint loading: no
        # caller may decide to resume/reset state before owning both locks.
        if context is None:
            with self.run_context() as acquired:
                return self._run(fresh, acquired)
        return self._run(fresh, context)

    def _run(self, fresh: bool, context: Any) -> PageRunResult:
            ensure_held = getattr(context, "ensure_held", None)
            begin_page_mutation = getattr(context, "begin_page_mutation", None)
            end_page_mutation = getattr(context, "end_page_mutation", None)
            if not callable(ensure_held) or not callable(begin_page_mutation) or not callable(end_page_mutation):
                raise RuntimeError("run_context must provide writer advisory-lock liveness and page-handoff methods")
            checkpoint = read_checkpoint(self.path, self.identity, fresh=fresh)
            if self.prepare_checkpoint is not None:
                prepared = self.prepare_checkpoint(checkpoint)
                if prepared is None:
                    return PageRunResult(checkpoint, True)
                if prepared.identity != self.identity:
                    raise RuntimeError("prepared checkpoint has a different run identity")
                if prepared != checkpoint:
                    checkpoint = prepared
                    save_checkpoint(self.path, checkpoint)
            if checkpoint.completed:
                return PageRunResult(checkpoint, False)
            if self.interrupts.stop_requested:
                return PageRunResult(checkpoint, True)
            reconnect_attempts = 0
            while True:
                try:
                    # A graceful SIGINT applies only to the page that was
                    # active when it arrived.  Never begin a later fetch.
                    if self.interrupts.stop_requested:
                        return PageRunResult(checkpoint, True)
                    ensure_held()
                    page = self.fetch_page(checkpoint.cursor)
                    if page is None:
                        # Final source fetch can be long-running too.  Never
                        # publish a completed checkpoint after the run lock
                        # session has been lost.
                        ensure_held()
                        checkpoint = Checkpoint(self.identity, checkpoint.cursor, checkpoint.pages, checkpoint.rows, True, checkpoint.metadata)
                        if self.complete_checkpoint is not None:
                            checkpoint = self.complete_checkpoint(checkpoint)
                            if checkpoint.identity != self.identity or not checkpoint.completed:
                                raise RuntimeError("completion checkpoint must retain identity and be completed")
                        save_checkpoint(self.path, checkpoint)
                        return PageRunResult(checkpoint, False)
                    if not page.rows:
                        raise RuntimeError("a non-final page must contain rows")
                    if len(page.next_cursor) != len(self.identity.source_page_keys):
                        raise RuntimeError("page cursor does not match declared source_page_keys")
                    if checkpoint.cursor is not None and page.next_cursor <= checkpoint.cursor:
                        raise RuntimeError("page cursor did not advance")
                    # Any error here rolls back.  An error after the context
                    # exits but before save_checkpoint intentionally causes an
                    # idempotent replay from the unchanged checkpoint cursor.
                    # Fetches can be long-running; prove the dedicated lock
                    # session is still alive immediately before mutation.
                    ensure_held()
                    handoff_started = False
                    try:
                        with self.transaction() as destination_connection:
                            begin_page_mutation(destination_connection)
                            handoff_started = True
                            self.write_page(page.rows)
                    finally:
                        # The xact lock is released by the transaction context
                        # before the dedicated session lock is restored. If
                        # restoration loses to another writer, refuse to
                        # checkpoint this committed (idempotent) page.
                        if handoff_started:
                            end_page_mutation()
                    # Size evidence is valid only after the destination
                    # transaction committed.  Fetch success alone says
                    # nothing about capacity for the complete page operation.
                    if self.on_page_committed is not None:
                        self.on_page_committed(page)
                    checkpoint = Checkpoint(
                        self.identity, page.next_cursor, checkpoint.pages + 1, checkpoint.rows + len(page.rows), False, checkpoint.metadata
                    )
                    save_checkpoint(self.path, checkpoint)
                except Exception as error:
                    # A first SIGINT can make an Oracle driver surface a break
                    # exception from fetch/write.  It is a graceful stop, not
                    # a connection failure: the active transaction has rolled
                    # back and the previous checkpoint remains authoritative.
                    if isinstance(error, LockUnavailable):
                        raise
                    if self.interrupts.stop_requested:
                        return PageRunResult(checkpoint, True)
                    # Capacity failure is retried from the unchanged
                    # checkpoint cursor with an adapter-selected smaller page.
                    # It applies equally to source fetch and destination work.
                    if self.on_page_size_error is not None and self.on_page_size_error(error):
                        continue
                    if self.reconnect is None or self.is_reconnectable is None or not self.is_reconnectable(error):
                        raise
                    while True:
                        if reconnect_attempts >= self.max_reconnect_attempts:
                            raise error
                        delay = min(
                            self.reconnect_max_delay_seconds,
                            self.reconnect_initial_delay_seconds * (2 ** reconnect_attempts),
                        )
                        reconnect_attempts += 1
                        if self.interrupts.stop_requested:
                            return PageRunResult(checkpoint, True)
                        self.sleep(delay)
                        if self.interrupts.stop_requested:
                            return PageRunResult(checkpoint, True)
                        try:
                            self.reconnect()
                            if self.interrupts.stop_requested:
                                return PageRunResult(checkpoint, True)
                            break
                        except Exception as reconnect_error:
                            if self.interrupts.stop_requested:
                                return PageRunResult(checkpoint, True)
                            if not self.is_reconnectable(reconnect_error):
                                raise
                            error = reconnect_error
                    # Refetch; never reuse a possibly partial/stale page.
                    continue
                # A committed page proves the connection is usable again, so
                # subsequent transient failures receive the full retry budget.
                reconnect_attempts = 0
                if self.interrupts.stop_requested:
                    return PageRunResult(checkpoint, True)
