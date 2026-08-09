"""Optional bounded adaptive page-size selector; no state is persisted."""

from __future__ import annotations


class PageSizer:
    """Search for a large working size with exactly three bracket bisections.

    A failed page is always retried from its unchanged cursor.  We assume a
    page that fails at N implies larger pages are unsafe.  If that conflicts
    with a previous success at a larger size, that larger success is discarded
    and the downward search restarts; this is conservative under noisy errors.
    """

    def __init__(self, max_page_size: int, initial_page_size: int | None = None, constant_page_size: int | None = None) -> None:
        if max_page_size < 1:
            raise ValueError("max_page_size must be positive")
        if constant_page_size is not None and initial_page_size is not None:
            raise ValueError("constant_page_size and initial_page_size are mutually exclusive")
        if constant_page_size is not None and not 1 <= constant_page_size <= max_page_size:
            raise ValueError("constant_page_size must be within max_page_size")
        if initial_page_size is not None and not 1 <= initial_page_size <= max_page_size:
            raise ValueError("initial_page_size must be within max_page_size")
        self.maximum = max_page_size
        self.constant = constant_page_size
        self.current = constant_page_size or initial_page_size or max(1, max_page_size // 4)
        self._working: int | None = None
        self._failing: int | None = None
        self._bisections = 0
        self._refinement_pending = False
        self._stable = False

    @property
    def page_size(self) -> int:
        return self.current

    def _next_refinement_or_stable(self) -> int:
        assert self._working is not None and self._failing is not None
        if self._bisections >= 3 or self._working + 1 >= self._failing:
            self.current = self._working
            self._stable = True
            self._refinement_pending = False
        else:
            self.current = (self._working + self._failing) // 2
            self._refinement_pending = True
        return self.current

    def _record_refinement_result(self) -> None:
        if self._refinement_pending:
            self._bisections += 1
            self._refinement_pending = False

    def succeeded(self) -> int:
        if self.constant is not None:
            return self.current
        self._record_refinement_result()
        self._working = self.current if self._working is None else max(self._working, self.current)
        if self._failing is not None:
            return self._next_refinement_or_stable()
        if self.current >= self.maximum:
            self._stable = True
            return self.current
        self.current = min(self.maximum, self.current * 2)
        return self.current

    def failed_for_size(self) -> int:
        if self.constant is not None:
            raise RuntimeError("constant page size failed")
        if self._stable:
            # A later failure discards all old evidence and immediately begins
            # the same conservative downwards bracket search.
            return self.restart_after_later_failure()
        self._record_refinement_result()
        self._stable = False
        if self._working is not None and self.current < self._working:
            # A smaller failure invalidates the previous larger success under
            # the required conservative monotonicity assumption.
            self._working = None
            self._failing = self.current
            self._bisections = 0
        else:
            self._failing = self.current if self._failing is None else min(self._failing, self.current)
        if self._working is None:
            if self.current == 1:
                raise RuntimeError("page size 1 failed")
            self.current = max(1, self.current // 2)
            return self.current
        return self._next_refinement_or_stable()

    def restart_after_later_failure(self) -> int:
        if self.constant is not None:
            raise RuntimeError("constant page size failed")
        failed = self.current
        self._working = None
        self._failing = failed
        self._bisections = 0
        self._refinement_pending = False
        self._stable = False
        if failed == 1:
            raise RuntimeError("page size 1 failed")
        self.current = max(1, failed // 2)
        return self.current
