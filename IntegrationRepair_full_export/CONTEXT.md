# Integration Repair

Integration Repair reconciles records provided by a LIFT integration with the records held in LIFT.

## Language

**Integration**:
A configured LIFT data feed that defines the source query and the mapping of source fields to a target table.

**Delta integration**:
A LIFT integration that processes source changes incrementally. This is the kind of integration covered by repair; full-sync integrations are outside its scope.

**Integration UUID**:
The identifier of the integration configuration, distinct from the identifiers of the records it supplies.

**Integration key**:
The record identifier selected by the integration's ID mapping, in its defined value and type. It is distinct from LIFT's target-row UUID.
_Avoid_: UUID, integration UUID, unqualified ID

**Change time**:
The source change timestamp selected by the integration's change-field mapping and its mapped counterpart in LIFT. Its value uses the wall-clock representation supplied by the integration query and stored by FMP; the actual column name depends on the integration.
_Avoid_: Assuming every integration has a column literally named date_changed

**Matching pair**:
An integration key and change time present together in both the source and LIFT. This is the criterion for considering a record correct during repair; its other field values are not compared.

**Repair run**:
A particular reconciliation of one integration, identified by its own UUID and consisting of preparation followed by application.

**Repair cutoff**:
The integration's high-water mark captured when a repair run is initialized. A cutoff is a time boundary, not a historical snapshot of the source.

**Repair membership**:
The integration keys returned by the current source query with change times at or before the repair cutoff. LIFT's comparison population uses the same cutoff; a source or target row with a later change time is outside repair scope.

**Ahead record**:
A record whose LIFT change time is newer than its Oracle counterpart's change time. This is an unexpected condition, distinct from a source record newer than the repair cutoff.

**Dependent materialized view**:
A stored LIFT query result whose source configuration subscribes to changes in a repaired table. Its contents are separate from the repaired base-table records.

**Audit history**:
FMP's separate history of application operations, distinct from creation/update metadata fields stored on a LIFT record.
