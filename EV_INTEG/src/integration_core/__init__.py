"""Small shared runtime for resumable EV integrations.

Adapters own database-specific reads and writes.  This package owns the
repeated operational rules: table declarations, checkpoint identity, locks,
signals, page commits, and optional page-size selection.
"""

from .managed import DEFAULT_CREATED_BY, DEFAULT_MANAGED_FIELDS, InsertPolicy, ManagedFields
from .errors import is_size_related_error
from .locks import LocalStateLock, LockUnavailable, PostgresWriterLock, WriterRunContext
from .page_size import PageSizer
from .runner import Page, PageRunResult, PageRunner
from .signals import InterruptController
from .specs import CheckSpec, TableSpec
from .staging_production import StagingProductionRun
from .state import Checkpoint, CheckpointFormatError, CheckpointMismatch, RunIdentity, atomic_json_write, read_checkpoint

__all__ = [
    "DEFAULT_CREATED_BY",
    "DEFAULT_MANAGED_FIELDS",
    "CheckSpec",
    "Checkpoint",
    "CheckpointFormatError",
    "CheckpointMismatch",
    "InsertPolicy",
    "InterruptController",
    "LocalStateLock",
    "LockUnavailable",
    "ManagedFields",
    "Page",
    "PageRunResult",
    "PageRunner",
    "PageSizer",
    "PostgresWriterLock",
    "RunIdentity",
    "TableSpec",
    "StagingProductionRun",
    "WriterRunContext",
    "atomic_json_write",
    "is_size_related_error",
    "read_checkpoint",
]
