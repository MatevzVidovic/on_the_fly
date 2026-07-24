# WFS sync — implementation

## Install

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install .
```

- Python: `3.12+`
- GeoPackage: GeoPandas + pyogrio / GDAL
- Database: PostgreSQL `14+`, PostGIS `3+`, psycopg `3`

## Commands

```bash
# Inspect source contract
python -m wfs_sync discover --report build/wfs-discovery.json

# Full file download: start or automatic resume
python -m wfs_sync sync --output data/upravni_akti.gpkg
python -m wfs_sync status --output data/upravni_akti.gpkg
python -m wfs_sync sync --output data/upravni_akti.gpkg --restart

# Dedicated PostGIS schema
export DATABASE_URL='postgresql://user:password@host/database'
python -m wfs_sync db-init
python -m wfs_sync db-bootstrap --input data/upravni_akti.gpkg
python -m wfs_sync db-sync
python -m wfs_sync db-sync --full-refresh
```

- Global options before subcommand
  - `--endpoint`
  - `--page-size`
  - `--timeout`
  - `--retries`
  - `--log-level`
- Database fetch sizing
  - `db-sync --fetch-batch-size N`
  - default: `100`

## Configuration

| Environment | Default / purpose |
|---|---|
| `DATABASE_URL` | required for `db-*`; never logged |
| `WFS_ENDPOINT` | public eProstor WFS |
| `WFS_PAGE_SIZE` | `5000` |
| `WFS_RESOURCE_BATCH_SIZE` | `100` |
| `WFS_TIMEOUT` | `120` seconds |
| `WFS_RETRIES` | `4` |
| `WFS_LOG_LEVEL` | `INFO` |
| `WFS_OUTPUT` | `data/upravni_akti.gpkg` |
| `WFS_REPORT` | `build/wfs-discovery.json` |

- Retry status
  - `429`
  - `500`, `502`, `503`, `504`
- CRS
  - `EPSG:3794`

## Disk state and recovery

- In-progress
  - `.upravni_akti.partial.gpkg`
  - `.upravni_akti.gpkg.checkpoint.json`
  - `<output>.lock`: advisory `flock`; harmless file retained
- Checkpoint
  - atomic JSON write + file and directory `fsync`
  - source endpoint, CRS, layer definitions, schema fingerprints
  - expected and written counts
  - null-key completion and last completed `ID_UA`
- Resume
  - partial GeoPackage inspected as source of truth
  - raw source duplicates preserved
  - complete layers skipped
  - count / contract drift → `--restart`
- Publication
  - exact two-layer set and counts
  - `PRAGMA integrity_check = ok`
  - GeoPackage: atomic `os.replace`
  - metadata: `<output>.manifest.json`, `<output>.sha256`
  - metadata interruption: completed checkpoint recovery
  - previous complete output preserved until replace

## PostGIS contract

- Schema: `eprostor`
- Tables
  - `upravni_akti_tocke`
  - `upravni_akti_parcele`
  - `sync_state`
- Per-layer row
  - `wfs_id`: primary key
  - source attributes
  - `source_updated_at`
  - `geom`
  - `synced_at`
- Initialization
  - PostGIS extension
  - idempotent schema, table, and index creation
  - existing columns and geometry type / SRID validation
- Delta staging
  - session temporary inventory, wanted-ID, and feature tables
  - inventory transport: geometry-free CSV
  - naive CSV timestamps: `Europe/Ljubljana` → UTC
  - streamed `COPY`
  - bounded feature batches
  - identical WFS-ID duplicates canonicalized
  - conflicting WFS-ID duplicates rejected
- Final transaction
  - upsert staged features
  - delete target IDs absent from complete inventory
  - verify stored count equals unique inventory count
  - raw WFS count may include identical duplicate IDs
  - update `sync_state`
  - both layers commit or roll back together
- Safety
  - PostgreSQL advisory lock
  - initial / final WFS counts
  - non-empty target protected from unexpected zero source
  - exact `resourceId` response validation
  - omitted batch member: one individual retry
  - live source schema fingerprint validation
  - bootstrap manifest, counts, and SHA-256 validation

## On-prem schedule

```cron
17 4 * * 1 cd /opt/jspis-wfs && . /etc/jspis-wfs.env && /opt/jspis-wfs/.venv/bin/python -m wfs_sync db-sync >> /var/log/jspis-wfs-sync.log 2>&1
```

- Secret handling
  - `/etc/jspis-wfs.env`: `export DATABASE_URL='postgresql://...'`
  - owner-only permissions
  - alternative: protected wrapper or systemd `EnvironmentFile`
  - not directly in crontab
- Scheduler
  - own cron / systemd
  - GitHub Actions workflow removed

## Tests

```bash
python -m pip install -e '.[dev]'
pytest

WFS_SYNC_TEST_DATABASE_URL='postgresql://...' pytest \
  Agents/AgentTests/wfs-sync/implementers-tests/test_postgis.py
```

- Offline
  - WFS parsing, inventory paging, `resourceId`
  - checkpoint interruption, resume, restart, atomic publication
  - database SQL and failure behavior
- Optional real PostGIS
  - initialize and bootstrap
  - insert, update, null-timestamp refresh, deletion
  - two-run convergence
