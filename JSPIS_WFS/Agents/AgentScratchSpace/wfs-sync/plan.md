# WFS sync — implemented plan

## Outcomes

- Disk snapshot
  - full two-layer GeoPackage
  - persistent partial file + atomic JSON checkpoint
  - resume by completed `ID_UA` boundary
  - final manifest + SHA-256 + atomic publish
- PostGIS mirror
  - dedicated `eprostor` schema
  - complete geometry-free ID/update inventory
  - `resourceId` fetch of new, changed, and null-timestamp rows
  - delete target IDs absent from inventory
  - one final transaction for both layers and state
- Operations
  - own-server cron calls Python CLI
  - advisory file / PostgreSQL locks
  - GitHub Actions workflow removed

## Implementation stages

1. WFS protocol
   - live schema fingerprint
   - boundary-safe keyset paging
   - lightweight inventory
   - exact `resourceId` batching
2. Durable snapshot
   - page append
   - checkpoint recovery and `--restart`
   - count / layer / integrity validation
   - atomic publication
3. Database reconciliation
   - streamed temporary tables via `COPY`
   - SQL-derived wanted and deleted sets
   - bounded geometry batches
   - atomic upsert / delete / state commit
4. Bootstrap and safety
   - manifest / SHA-256 required
   - chunked GeoPackage read
   - schema / CRS / geometry validation
   - identical source duplicate canonicalization
5. Operations and tests
   - cron documentation
   - offline protocol, recovery, and SQL tests
   - disposable real PostGIS tests
   - live full snapshot and bootstrap validation

## Authoritative documentation

- `Agents/DevDocs/wfs-sync/general_idea.md`
- `Agents/DevDocs/wfs-sync/architecture.md`
- `Agents/DevDocs/wfs-sync/implementation.md`
- `README.md`
