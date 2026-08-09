"""Table facts shared by integration commands, deliberately without a DSL."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def _identifier(value: str, label: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} must be a plain SQL identifier: {value!r}")
    return value.lower()


@dataclass(frozen=True, slots=True)
class TableSpec:
    """Facts needed to move one selected integration result into PostgreSQL."""

    name: str
    source_sql: Path
    target_schema: str
    target_table: str
    membership_key: str
    source_page_keys: tuple[str, ...]
    date_change: str | None = None
    version: int = 1
    insert_policy: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _identifier(self.name, "table spec name"))
        object.__setattr__(self, "source_sql", Path(self.source_sql))
        if not self.source_sql.name or self.source_sql.suffix.lower() != ".sql":
            raise ValueError("source_sql must name a .sql file")
        object.__setattr__(self, "target_schema", _identifier(self.target_schema, "target schema"))
        object.__setattr__(self, "target_table", _identifier(self.target_table, "target table"))
        object.__setattr__(self, "membership_key", _identifier(self.membership_key, "membership key"))
        keys = tuple(_identifier(key, "source page key") for key in self.source_page_keys)
        if not keys or len(set(keys)) != len(keys):
            raise ValueError("source_page_keys must contain one or more distinct identifiers")
        object.__setattr__(self, "source_page_keys", keys)
        if self.date_change is not None:
            object.__setattr__(self, "date_change", _identifier(self.date_change, "date_change"))
        if self.version < 1:
            raise ValueError("table spec version must be positive")
        if self.insert_policy is not None and self.insert_policy not in {"default", "copy-managed"}:
            raise ValueError("insert_policy must be 'default', 'copy-managed', or None")

    @property
    def target_relation(self) -> str:
        return f"{self.target_schema}.{self.target_table}"


@dataclass(frozen=True, slots=True)
class CheckSpec:
    """Checker-only options; transfer behavior must not depend on these."""

    compare_columns: tuple[str, ...] = field(default_factory=tuple)
    compare_change_field: bool = True
    cache_counts: bool = True

    def __post_init__(self) -> None:
        columns = tuple(_identifier(column, "check column") for column in self.compare_columns)
        if len(set(columns)) != len(columns):
            raise ValueError("compare_columns must be distinct")
        object.__setattr__(self, "compare_columns", columns)
