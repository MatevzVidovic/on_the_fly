"""Destination-managed LIFT fields and the portable insert/update policy."""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_CREATED_BY = "00000000-0000-0000-0000-000000000000"


@dataclass(frozen=True, slots=True)
class ManagedFields:
    id: str = "id"
    created_at: str = "created_at"
    created_by: str = "created_by"
    updated_at: str = "updated_at"
    updated_by: str = "updated_by"
    default_created_by: str = DEFAULT_CREATED_BY

    @property
    def creation_fields(self) -> frozenset[str]:
        return frozenset((self.id, self.created_at, self.created_by))

    @property
    def update_fields(self) -> frozenset[str]:
        return frozenset((self.updated_at, self.updated_by))

    @property
    def all_fields(self) -> frozenset[str]:
        return self.creation_fields | self.update_fields


DEFAULT_MANAGED_FIELDS = ManagedFields()


@dataclass(frozen=True, slots=True)
class InsertPolicy:
    """Column decisions made by adapters before producing SQL.

    Source selects normally omit all managed fields.  An adapter may opt into
    copying them (the staging-to-production adapter does); update columns are
    still kept distinct from creation columns so conflict updates cannot
    overwrite creation metadata accidentally.
    """

    managed: ManagedFields = DEFAULT_MANAGED_FIELDS
    copy_managed_fields: bool = False

    @staticmethod
    def _unique_source_columns(source_columns: tuple[str, ...]) -> tuple[str, ...]:
        columns = tuple(source_columns)
        if any(not isinstance(column, str) or not column for column in columns):
            raise ValueError("source columns must be non-empty strings")
        duplicates = {column for column in columns if columns.count(column) > 1}
        if duplicates:
            raise ValueError(f"source columns contain duplicates: {', '.join(sorted(duplicates))}")
        return columns

    def insert_columns(self, source_columns: tuple[str, ...]) -> tuple[str, ...]:
        columns = self._unique_source_columns(source_columns)
        return tuple(column for column in columns if self.copy_managed_fields or column not in self.managed.all_fields)

    def generated_insert_values(self) -> dict[str, str]:
        """SQL expressions required when a source deliberately omits LIFT fields."""
        if self.copy_managed_fields:
            return {}
        return {
            self.managed.id: "uuid_generate_v4()",
            self.managed.created_at: "CURRENT_TIMESTAMP",
            self.managed.created_by: f"'{self.managed.default_created_by}'::uuid",
            self.managed.updated_at: "CURRENT_TIMESTAMP",
        }

    def destination_insert_columns(self, source_columns: tuple[str, ...]) -> tuple[str, ...]:
        columns = (*self.generated_insert_values().keys(), *self.insert_columns(source_columns))
        if len(set(columns)) != len(columns):  # Defensive if ManagedFields is customized incorrectly.
            raise ValueError("destination insert columns contain duplicates")
        return tuple(columns)

    def update_columns(self, inserted_columns: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(column for column in inserted_columns if column not in self.managed.creation_fields)
