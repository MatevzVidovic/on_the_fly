"""Pure comparison and selection rules for the KN audit.

This module deliberately has no database driver imports.  Database adapters only
turn their cursors into mappings and feed them to ``compare_all_rows``.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Iterable, Iterator
from zoneinfo import ZoneInfo

LJ = ZoneInfo("Europe/Ljubljana")
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$#]*$")


class AuditError(Exception):
    pass


def qi(name: str) -> str:
    if not isinstance(name, str) or not IDENT.fullmatch(name):
        raise AuditError(f"unsafe identifier: {name!r}")
    return '"' + name + '"'


def parse_cutoff(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise AuditError("--as-of must be ISO-8601") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise AuditError("--as-of must include a UTC offset")
    return result.astimezone(timezone.utc)


def normalize_temporal(value: Any, mode: str, *, field: str) -> datetime:
    """Normalise to an instant.

    ``oracle_native_local`` means Oracle DATE/TIMESTAMP without a zone denotes
    Europe/Ljubljana local time (including the historical DST rule).  Text mode
    accepts *only* offset-bearing ISO-8601 timestamps, preventing a driver or
    session locale from silently changing a cutoff comparison.
    """
    if mode == "iso8601_text":
        if not isinstance(value, str):
            raise AuditError(f"{field} must be ISO-8601 text")
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise AuditError(f"{field} is malformed ISO-8601 text") from exc
        if value.tzinfo is None or value.utcoffset() is None:
            raise AuditError(f"{field} ISO-8601 text must include an offset")
    elif mode == "oracle_native_local":
        if isinstance(value, date) and not isinstance(value, datetime):
            value = datetime.combine(value, datetime.min.time())
        if not isinstance(value, datetime):
            raise AuditError(f"{field} is not an Oracle date/timestamp")
        if value.tzinfo is None:
            value = value.replace(tzinfo=LJ)
    elif mode == "postgres_timestamp":
        if not isinstance(value, datetime):
            raise AuditError(f"{field} is not a PostgreSQL timestamp")
        if value.tzinfo is None:
            # PostgreSQL target timestamps are a documented Ljubljana-local
            # contract; reject accidental text/driver conversions elsewhere.
            value = value.replace(tzinfo=LJ)
    else:
        raise AuditError(f"unsupported temporal mode: {mode}")
    return value.astimezone(timezone.utc)


def numeric_key(value: Any) -> Decimal:
    """A cross-engine total order only for finite numeric keys.

    Text and UUID keys are rejected: Oracle and PostgreSQL can sort them under
    different collations, which would invalidate a streaming merge.
    """
    if isinstance(value, bool) or isinstance(value, float):
        raise AuditError("composite keys must be finite integer/Decimal values; bool/float are unsupported")
    if not isinstance(value, (int, Decimal)):
        raise AuditError(f"composite keys must be numeric; got {type(value).__name__}")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise AuditError("invalid numeric composite key") from exc
    if not result.is_finite():
        raise AuditError("non-finite numeric composite key")
    return result


def key_of(row: dict[str, Any], names: list[str]) -> tuple[Decimal, ...]:
    try:
        values = tuple(row[x] for x in names)
    except KeyError as exc:
        raise AuditError("source/target aliases missing from query output") from exc
    if any(v is None for v in values):
        raise AuditError("null composite key")
    return tuple(numeric_key(v) for v in values)


@dataclass(frozen=True)
class KeyMap:
    source: str
    target: str


@dataclass(frozen=True)
class Selection:
    name: str
    integration_id: str
    target_table: str
    target_schema: str
    keys: tuple[KeyMap, ...]
    source_date: str
    target_date: str
    source_temporal_mode: str
    target_temporal_mode: str = "postgres_timestamp"

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "Selection":
        if not isinstance(row, dict):
            raise AuditError("each selection table must be an object")
        try:
            keys = tuple(KeyMap(x["source"], x["target"]) for x in row["keys"])
            out = cls(row.get("name", row["target_table"]), str(row["integration_id"]), row["target_table"],
                row.get("target_schema", "public"), keys, row["source_date"], row["target_date"],
                row["source_temporal_mode"], row.get("target_temporal_mode", "postgres_timestamp"))
        except (KeyError, TypeError, ValueError) as exc:
            raise AuditError(f"bad selection: {row!r}; source_temporal_mode is required") from exc
        if not out.keys:
            raise AuditError(f"{out.name}: at least one key is required")
        if out.source_temporal_mode not in {"oracle_native_local", "iso8601_text"}:
            raise AuditError("source_temporal_mode must be oracle_native_local or iso8601_text")
        if out.target_temporal_mode != "postgres_timestamp":
            raise AuditError("target_temporal_mode must be postgres_timestamp")
        if not re.fullmatch(r"[A-Za-z0-9-]{1,100}", out.integration_id):
            raise AuditError("invalid integration id")
        if not re.fullmatch(r"[A-Za-z0-9_. -]{1,100}", out.name):
            raise AuditError("unsafe selection name")
        for v in (out.target_table, out.target_schema, out.source_date, out.target_date,
                  *(p for k in out.keys for p in (k.source, k.target))): qi(v)
        source_aliases = [x.source for x in out.keys] + [out.source_date]
        target_aliases = [x.target for x in out.keys] + [out.target_date]
        if len({x.lower() for x in source_aliases}) != len(source_aliases) or len({x.lower() for x in target_aliases}) != len(target_aliases):
            raise AuditError(f"{out.name}: duplicate key mapping")
        return out


def validated_stream(rows: Iterable[dict[str, Any]], keys: list[str], datecol: str, temporal_mode: str) -> Iterator[dict[str, Any]]:
    previous: tuple[Decimal, ...] | None = None
    for row in rows:
        if datecol not in row:
            raise AuditError("source/target date alias missing from query output")
        key = key_of(row, keys)
        if previous is not None and key <= previous:
            raise AuditError("duplicate or unordered numeric composite key")
        previous = key
        normalize_temporal(row[datecol], temporal_mode, field=datecol)
        yield row


def compare_eligible_rows(source: Iterable[dict[str, Any]], target: Iterable[dict[str, Any]],
                          skeys: list[str], tkeys: list[str], sdate: str, tdate: str,
                          source_mode: str, target_mode: str, limit: int = 20,
                          on_delta: Callable[[str, dict[str, dict[str, Any]]], None] | None = None):
    """Merge streams already constrained by ``date < cutoff`` in the DB."""
    si = iter(validated_stream(source, skeys, sdate, source_mode))
    ti = iter(validated_stream(target, tkeys, tdate, target_mode))
    names = ("source_only", "target_only", "date_changed_mismatch")
    counts = Counter(); samples = {x: [] for x in names}
    def add(kind, payload):
        counts[kind] += 1
        if on_delta: on_delta(kind, payload)
        if len(samples[kind]) < limit: samples[kind].append(payload)
    s, t = next(si, None), next(ti, None)
    while s is not None or t is not None:
        if s is None: add("target_only", {"target": t}); t = next(ti, None); continue
        if t is None: add("source_only", {"source": s}); s = next(si, None); continue
        a, b = key_of(s, skeys), key_of(t, tkeys)
        if a < b: add("source_only", {"source": s}); s = next(si, None)
        elif b < a: add("target_only", {"target": t}); t = next(ti, None)
        else:
            if normalize_temporal(s[sdate], source_mode, field=sdate) != normalize_temporal(t[tdate], target_mode, field=tdate):
                add("date_changed_mismatch", {"source": s, "target": t})
            s, t = next(si, None), next(ti, None)
    return {x: counts[x] for x in names}, samples
