# WFS sync — implementation plan

## Scope and decisions

- Source: `https://storitve.eprostor.gov.si/ows-pub-wfs/wfs`
- Expected feature types; verify, never silently substitute:
  - points: `SI.MOP.GRAD:UPRAVNI_AKTI`
  - parcels: `SI.MOP.GRAD:UPRAVNI_AKTI_PARCELE`
- Output: one GeoPackage containing exactly two published layers:
  - `upravni_akti_tocke`
  - `upravni_akti_parcele`
- Requested CRS: `EPSG:3794`
- Default sync mode: **full, paged, atomic replacement**
  - A modification timestamp alone is insufficient: it does not report source deletions.
  - Delta is safe only if discovery proves all three: stable unique key, reliable last-modified value, and a deletion/tombstone feed (or another authoritative way to reconcile missing IDs).
  - Until all three are demonstrated, keep full sync. This is the simplest correct weekly process.
- No dependence on GeoServer-only CQL for the baseline. Use standard WFS 2.0 paging.

## Repository shape and dependency direction

```text
pyproject.toml
src/wfs_sync/
  model.py       # dependency-free dataclasses/constants
  wfs.py         # HTTP + XML/GeoJSON protocol, imports model
  storage.py     # GeoPackage staging/publish, imports model
  discovery.py   # schema/capability analysis, imports model+wfs
  sync.py        # application orchestration, imports model+wfs+storage
  cli.py         # argument/env parsing, imports discovery+sync
tests/           # fast developer tests
Agents/AgentTests/wfs-sync/main-tests/  # fuller black-box/edge-case suite
.github/workflows/wfs-sync.yml
README.md
```

No module imports `cli.py` or `sync.py`; protocol and storage remain independent.

## Public interfaces

`model.py`

```python
@dataclass(frozen=True)
class LayerSpec:
    type_name: str
    output_name: str
    expected_geometry: Literal["Point", "MultiPoint", "Polygon", "MultiPolygon"]

@dataclass(frozen=True)
class WfsConfig:
    base_url: str
    page_size: int = 5_000
    timeout_seconds: float = 120
    retries: int = 4
    crs: str = "EPSG:3794"

@dataclass(frozen=True)
class LayerResult:
    type_name: str
    output_name: str
    expected_count: int
    written_count: int
    source_ids_unique: bool
    bounds: tuple[float, float, float, float] | None

LAYERS: tuple[LayerSpec, ...]
```

`wfs.py`

```python
class WfsClient:
    def __init__(self, config: WfsConfig, session: requests.Session | None = None): ...
    def capabilities(self) -> bytes: ...
    def describe_feature_type(self, type_name: str) -> bytes: ...
    def feature_count(self, type_name: str) -> int: ...
    def iter_pages(self, layer: LayerSpec) -> Iterator[geopandas.GeoDataFrame]: ...

def parse_feature_types(capabilities_xml: bytes) -> set[str]: ...
def parse_schema(describe_xml: bytes) -> list[FieldDefinition]: ...
def parse_number_matched(response_xml: bytes) -> int: ...
```

- Every request supplies `service=WFS`, `version=2.0.0`, explicit `request`.
- `GetFeature`: `typeNames`, `outputFormat=application/json`, `srsName`, `count`, `startIndex`.
- Prefer deterministic `sortBy=<discovered stable key>` only after verifying the field. Without one, page using the server order and detect duplicate feature IDs/count drift; abort rather than publish suspect data.
- Session retry adapter: status 429/500/502/503/504, exponential backoff, descriptive error including operation/type/page; bounded timeout.
- Reject non-2xx, OGC XML exception reports returned with HTTP 200, malformed JSON, missing `features`, and non-progressing pages.
- Stop when accumulated rows equals the initial `resultType=hits` count; accept a short last page only at that boundary. Re-check hits after download and abort if count changed.
- Preserve WFS feature IDs in a `_wfs_id` column; require non-null and unique before publication when supplied by the service.

`storage.py`

```python
class GeoPackagePublisher:
    def __init__(self, destination: Path): ...
    def create_staging_path(self) -> Path: ...
    def write_page(self, staging: Path, layer: LayerSpec,
                   frame: geopandas.GeoDataFrame, first: bool) -> int: ...
    def inspect(self, staging: Path, layer: LayerSpec) -> StoredLayerInfo: ...
    def publish(self, staging: Path) -> None: ...

def validate_frame(frame: GeoDataFrame, layer: LayerSpec, crs: str) -> None: ...
```

- Create staging file beside destination (`.<name>.<uuid>.tmp.gpkg`) for same-filesystem atomic rename.
- First page creates layer; later pages append via `pyogrio.write_dataframe(..., append=True)`.
- Empty source still creates an empty layer with the schema obtained from `DescribeFeatureType`; never leave a stale old layer.
- Validate CRS, geometry family (allow single/multi counterpart), finite coordinates, row count, both layer names, and `_wfs_id` uniqueness before `os.replace`.
- On any error delete only the known staging file; leave last successful destination untouched.

`discovery.py`

```python
def discover(client: WfsClient, layers: Sequence[LayerSpec]) -> DiscoveryReport: ...
def recommend_sync_mode(report: DiscoveryReport) -> Literal["full", "delta"]: ...
def write_report(report: DiscoveryReport, path: Path) -> None: ...
```

- Verify WFS 2.0/GetFeature, both exact type names, GeoJSON output, paging constraints, advertised/default CRS, schemas, geometry fields, counts.
- Classify candidate keys and date fields by schema plus a bounded sample, but do not infer reliability from names alone.
- Report delta prerequisites independently: stable unique key, modification semantics, deletion semantics.
- Recommendation returns `delta` only when all prerequisites are explicitly configured and verified; otherwise `full` with reasons.
- Store a human-readable JSON report; discovery is a separate command and does not alter the published GeoPackage.

`sync.py`

```python
def sync_all(client: WfsClient, publisher: GeoPackagePublisher,
             layers: Sequence[LayerSpec] = LAYERS) -> list[LayerResult]: ...
def sync_layer(client: WfsClient, publisher: GeoPackagePublisher,
               staging: Path, layer: LayerSpec) -> LayerResult: ...
```

- One run stages both layers, validates both, then publishes once.
- Fail the whole run if either layer fails.
- Structured logging: run/layer/page, expected/downloaded/written counts, elapsed time; no response bodies or secrets.
- Process lock adjacent to output prevents overlapping scheduled/manual runs.

`cli.py`

```text
python -m wfs_sync discover --report build/wfs-discovery.json
python -m wfs_sync sync --output data/upravni_akti.gpkg
```

- Options/env: endpoint, output/report path, page size, timeout, log level.
- Non-zero exit on all incomplete/invalid runs.
- `--dry-run` performs discovery/count/schema checks only.

## Implementation stages

1. Package skeleton, typed models, CLI/config, logging.
2. WFS client and XML/exception/count/schema parsers.
3. Discovery command and explicit full-vs-delta report.
4. GeoPackage page writer, validation, atomic publication, lock.
5. Two-layer orchestration and concise README/runbook.
6. Scheduled workflow and tests; run format/lint/type/test checks.

## Test architecture

All automated tests use local fixtures or a local fake HTTP server; no live eProstor dependency in CI.

### Developer tests (`tests/`)

- `test_sync_happy_path.py`
  - fake WFS serves both layers over multiple pages
  - CLI creates one GeoPackage
  - exact two layers, row counts, IDs, attributes, geometries, CRS
- `test_atomic_failure.py`
  - pre-existing destination plus second-layer failure
  - destination checksum/content unchanged; staging cleaned
- `test_discovery.py`
  - schema has update date but no tombstones → recommends full
  - all explicit prerequisites → recommends delta
- focused parser tests:
  - namespace variants, `numberMatched="unknown"`, OGC exception with HTTP 200

### Main agent tests (`Agents/AgentTests/wfs-sync/main-tests/`)

- Paging boundaries: 0, 1, exact page size, page size + 1; no duplicates/omissions.
- Transient retry then success; permanent timeout/429/5xx fails without publish.
- Source count changes between initial/final hits; reordered/duplicate/non-progressing page.
- Empty layer creation, missing/mixed/wrong geometry, missing CRS, invalid coordinates.
- Attribute types/nulls/non-ASCII Slovenian text survive GeoPackage round trip.
- Existing output replacement is atomic; concurrent run lock rejects second process.
- CLI env/argument precedence, dry run, useful exit codes/log summaries.
- Test-unchangedness review: implementation repairs must not modify assertions/fixtures to pass.

Optional manual integration test, opt-in only:

```text
EPROSTOR_LIVE_TEST=1 pytest -m live
```

- Fetch capabilities/descriptions/hits and at most one tiny sample page.
- Never part of scheduled CI; records no personal/source payloads in repository.

## Weekly automation

`.github/workflows/wfs-sync.yml`:

- `schedule: cron: "17 3 * * 1"` (Monday 03:17 UTC), plus `workflow_dispatch`.
- `concurrency` group with no overlapping runs.
- install pinned Python/dependencies; run `discover --dry-run` then `sync`.
- upload GeoPackage, discovery report, and checksum as a named artifact with documented retention.
- persist the final dataset to the actual consumer-controlled durable location when credentials/target are supplied; artifact-only delivery is a safe initial default, not a permanent database.
- secrets only through workflow secret store; least privilege; no pull-request execution with production credentials.
- failure leaves prior durable object/database version in place and workflow alerts via native failure notification.

For an on-prem runner, provide the same CLI through a documented cron/systemd example rather than a second implementation.

## Acceptance criteria

- A single command produces a valid GeoPackage with both expected layers in EPSG:3794.
- Counts equal stable WFS `numberMatched`; no duplicate source IDs; geometry/schema validations pass.
- Partial or suspect downloads never replace the previous successful file.
- Discovery report states evidence and recommends full sync unless deletion-safe delta is proven.
- Weekly/manual workflow executes the identical CLI and retains a verifiable artifact/checksum.
- Unit and black-box suites pass without network access; optional live smoke test is bounded.

