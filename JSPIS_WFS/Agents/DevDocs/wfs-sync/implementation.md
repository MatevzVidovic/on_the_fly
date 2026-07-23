# WFS sync — implementation

## Commands

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install .

python -m wfs_sync discover --report build/wfs-discovery.json
python -m wfs_sync sync --output data/upravni_akti.gpkg
```

- Python: `3.12+`
- Native dependency: GDAL stack used by GeoPandas / pyogrio
- CLI alias after install: `wfs-sync`
- Global options before subcommand
  - `--endpoint`
  - `--page-size`
  - `--timeout`
  - `--retries`
  - `--log-level`

## Configuration

| Setting | Environment | Default |
|---|---|---|
| Endpoint | `WFS_ENDPOINT` | eProstor public WFS |
| Page size | `WFS_PAGE_SIZE` | `5000` |
| Timeout | `WFS_TIMEOUT` | `120` seconds |
| Retries | `WFS_RETRIES` | `4` |
| Log level | `WFS_LOG_LEVEL` | `INFO` |
| Output | `WFS_OUTPUT` | `data/upravni_akti.gpkg` |
| Report | `WFS_REPORT` | `build/wfs-discovery.json` |

- CLI values override environment values
- CRS fixed: `EPSG:3794`
- Retry statuses
  - `429`
  - `500`, `502`, `503`, `504`

## Data contract

- Source → output
  - `SI.MOP.GRAD:UPRAVNI_AKTI` → `upravni_akti_tocke`
  - `SI.MOP.GRAD:UPRAVNI_AKTI_PARCELE` → `upravni_akti_parcele`
- Required
  - exact attributes and source types
  - `_wfs_id`: non-empty, globally unique per layer
  - stable total `numberMatched`
- Geometry
  - point layer when present: `Point`
  - parcel layer when present: promoted to `MultiPolygon`
  - parcel `NULL`: valid
  - empty / non-finite / wrong family: invalid

## Storage and failure behavior

- Staging
  - hidden UUID file beside destination
  - same filesystem as destination
  - page-wise append
- Pre-publication checks
  - both expected layer names only
  - stored counts equal downloaded counts
  - final source recounts
  - `PRAGMA integrity_check = ok`
- Publication
  - atomic `os.replace`
  - old output preserved until success
- Failure
  - exit code `1`
  - known staging file removed
  - old output unchanged
- Concurrency
  - adjacent `.lock` file
  - overlapping run rejected
  - stale lock requires operator review/removal

## Tests

```bash
python -m pip install -e '.[dev]'
pytest
```

- Offline suites
  - `Agents/DevTests/wfs-sync`
  - `Agents/AgentTests/wfs-sync/implementers-tests`
  - `Agents/AgentTests/wfs-sync/main-tests`
- Coverage focus
  - protocol / schema parsing
  - tied-key keyset paging
  - nullable geometry
  - atomic publication / cleanup
  - final recount
  - CLI / lock / workflow

## Operations

- GitHub Actions
  - Monday `03:17 UTC`
  - manual dispatch
  - single concurrency group
  - `180` minute job timeout
  - offline tests → discovery → full sync → SHA-256
  - artifact retention: `14` days
- Produced artifact
  - `upravni_akti.gpkg`
  - `upravni_akti.gpkg.sha256`
  - `wfs-discovery.json`
- Capacity
  - room for old and staged GeoPackages simultaneously
  - WFS ID set grows with feature count
- Delivery
  - workflow artifact: temporary distribution
  - durable object storage / database: downstream extension
