"""Database-neutral page runner with commit-before-checkpoint semantics."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from time import sleep as default_sleep
from typing import Any, Generic, TypeVar

from .signals import InterruptController
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
        reconnect: Callable[[], None] | None = None,
        is_reconnectable: Callable[[Exception], bool] | None = None,
        max_reconnect_attempts: int = 3,
        reconnect_initial_delay_seconds: float = 1.0,
        reconnect_max_delay_seconds: float = 30.0,
        sleep: Callable[[float], None] = default_sleep,
        interrupts: InterruptController | None = None,
    ) -> None:
        self.path, self.identity = checkpoint_path, identity
        self.fetch_page, self.write_page, self.transaction = fetch_page, write_page, transaction
        self.run_context = run_context
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

    def run(self, *, fresh: bool = False) -> PageRunResult:
        # The writer context intentionally encloses checkpoint loading: no
        # caller may decide to resume/reset state before owning both locks.
        with self.run_context():
            checkpoint = read_checkpoint(self.path, self.identity, fresh=fresh)
            if checkpoint.completed:
                return PageRunResult(checkpoint, False)
            reconnect_attempts = 0
            while True:
                try:
                    page = self.fetch_page(checkpoint.cursor)
                    if page is None:
                        checkpoint = Checkpoint(self.identity, checkpoint.cursor, checkpoint.pages, checkpoint.rows, True)
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
                    with self.transaction():
                        self.write_page(page.rows)
                    checkpoint = Checkpoint(
                        self.identity, page.next_cursor, checkpoint.pages + 1, checkpoint.rows + len(page.rows), False
                    )
                    save_checkpoint(self.path, checkpoint)
                except Exception as error:
                    # A first SIGINT can make an Oracle driver surface a break
                    # exception from fetch/write.  It is a graceful stop, not
                    # a connection failure: the active transaction has rolled
                    # back and the previous checkpoint remains authoritative.
                    if self.interrupts.stop_requested:
                        return PageRunResult(checkpoint, True)
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
                        self.sleep(delay)
                        try:
                            self.reconnect()
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
