"""Narrow, explicit error classification used by adaptive paging."""

from __future__ import annotations

from typing import Any


# These are capacity/statement-duration failures for which retrying the same
# cursor with a smaller payload can reasonably help.  Do not add generic SQL,
# constraint, data-conversion, or connection errors to this list.
_ORACLE_SIZE_CODES = frozenset({1652, 30036, 4030, 1555})
_POSTGRES_SIZE_SQLSTATES = frozenset({"53100", "53200", "53400", "54000"})


def _oracle_code(error: BaseException) -> int | None:
    for value in (getattr(error, "code", None), getattr(getattr(error, "args", (None,))[0], "code", None)):
        if isinstance(value, int):
            return value
    return None


def _sqlstate(error: BaseException) -> str | None:
    for name in ("sqlstate", "pgcode"):
        value: Any = getattr(error, name, None)
        if isinstance(value, str):
            return value
    return None


def is_size_related_error(error: BaseException) -> bool:
    """True only for documented capacity/timeout classes safe to shrink.

    Oracle: ORA-01652, ORA-30036, ORA-04030 and ORA-01555.
    PostgreSQL: disk/memory/config/program limits.  Query cancellation
    (including SQLSTATE 57014) is intentionally not generic size evidence;
    an adapter may classify its own known statement timeout explicitly.
    All other errors must abort the run.
    """
    return _oracle_code(error) in _ORACLE_SIZE_CODES or _sqlstate(error) in _POSTGRES_SIZE_SQLSTATES
