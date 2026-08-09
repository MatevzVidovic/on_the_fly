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
    oracle_owner: str | None = None
    oracle_index: str | None = None
    oracle_index_columns: tuple[str, ...] | None = None
    version: int = 1

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
        if (self.oracle_owner is None) != (self.oracle_index is None):
            raise ValueError("oracle_owner and oracle_index must be supplied together")
        if self.oracle_owner is not None:
            object.__setattr__(self, "oracle_owner", _identifier(self.oracle_owner, "oracle owner"))
            object.__setattr__(self, "oracle_index", _identifier(self.oracle_index or "", "oracle index"))
        if self.oracle_index_columns is not None:
            if self.oracle_index is None:
                raise ValueError("oracle_index_columns requires oracle_index")
            columns = tuple(_identifier(column, "oracle index column") for column in self.oracle_index_columns)
            if not columns:
                raise ValueError("oracle_index_columns must not be empty")
            object.__setattr__(self, "oracle_index_columns", columns)
        if self.version < 1:
            raise ValueError("table spec version must be positive")

    @property
    def target_relation(self) -> str:
        return f"{self.target_schema}.{self.target_table}"


@dataclass(frozen=True, slots=True)
class CheckSpec:
    """Checker-only options; transfer behavior must not depend on these."""

    source_table: str
    requires_jn_status: bool = False
    from_2025: bool = False
    forbid_columns: tuple[str, ...] = field(default_factory=tuple)
    lift_title_prefix: str = "EV H"

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_table", _identifier(self.source_table, "checker source table"))
        if not isinstance(self.requires_jn_status, bool) or not isinstance(self.from_2025, bool):
            raise ValueError("checker boolean options must be bool")
        forbidden = tuple(_identifier(column, "forbidden check column") for column in self.forbid_columns)
        if len(set(forbidden)) != len(forbidden):
            raise ValueError("forbid_columns must be distinct")
        object.__setattr__(self, "forbid_columns", forbidden)
        if not isinstance(self.lift_title_prefix, str) or not self.lift_title_prefix:
            raise ValueError("lift_title_prefix must be a non-empty string")
