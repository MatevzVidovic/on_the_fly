"""Two-stage SIGINT policy shared by page-based commands."""

from __future__ import annotations

import signal
from types import FrameType
from typing import Callable


class InterruptController:
    """First Ctrl-C requests a checkpointed stop; second aborts immediately."""
    def __init__(self, announce: Callable[[str], None] | None = None) -> None:
        self.stop_requested = False
        self._previous: signal.Handlers | None = None
        self._announce = announce or (lambda _message: None)

    def handle(self, _signum: int | None = None, _frame: FrameType | None = None) -> None:
        if self.stop_requested:
            raise KeyboardInterrupt
        self.stop_requested = True
        self._announce("SIGINT received: finishing the current page, checkpointing it, then stopping. Press Ctrl-C again to abort immediately.")

    def __enter__(self) -> "InterruptController":
        self._previous = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self.handle)
        signal.siginterrupt(signal.SIGINT, False)
        return self

    def __exit__(self, *_: object) -> None:
        if self._previous is not None:
            signal.signal(signal.SIGINT, self._previous)
            self._previous = None
