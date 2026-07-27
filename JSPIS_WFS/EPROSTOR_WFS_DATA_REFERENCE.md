# eProstor WFS administrative acts — data reference

This document records the verified behavior of the public eProstor WFS layers
for administrative acts related to construction. It covers the source,
published schemas, identifiers, timestamps, observed data anomalies, and the
rules used by the synchronization implementation.

Operational commands and deployment instructions remain in [README.md](README.md).

## Source

### Catalogue record

- Metadata:
  `https://eprostor.gov.si/imps/srv/api/records/ff907852-18ca-426f-a100-5631ca5fa95c`
- Public WFS:
  `https://storitve.eprostor.gov.si/ows-pub-wfs/wfs`
- Service implementation: GeoServer WFS
- Working feature protocol: WFS 2.0.0
- Schema fallback used by the client: individual WFS 1.1.0
  `DescribeFeatureType` requests
- Source/output CRS: `EPSG:3794` — Slovenia 1996 / Slovene National Grid

The catalogue URL describes the dataset. Feature data is downloaded from the
WFS URL.

### Useful WFS requests

Get the service and layer description:

```text
https://storitve.eprostor.gov.si/ows-pub-wfs/wfs?service=WFS&version=2.0.0&request=GetCapabilities
```

Get the schema of the point layer:

```text
https://storitve.eprostor.gov.si/ows-pub-wfs/wfs?service=WFS&version=1.1.0&request=DescribeFeatureType&typeName=SI.MOP.GRAD:UPRAVNI_AKTI
```

Get the current row count without transferring features:

```text
https://storitve.eprostor.gov.si/ows-pub-wfs/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=SI.MOP.GRAD:UPRAVNI_AKTI&resultType=hits
```

Get a geometry-free delta inventory:

```text
https://storitve.eprostor.gov.si/ows-pub-wfs/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=SI.MOP.GRAD:UPRAVNI_AKTI_PARCELE&outputFormat=csv&propertyName=ID_UA,ZAD_SPR&sortBy=ID_UA
```

GeoServer includes `FID` and several mandatory display attributes in the CSV
even when `propertyName` requests only `ID_UA,ZAD_SPR`. The synchronization
client reads only `FID`, `ID_UA`, and `ZAD_SPR`.

Fetch complete current features by WFS identity:

```text
https://storitve.eprostor.gov.si/ows-pub-wfs/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=SI.MOP.GRAD:UPRAVNI_AKTI_PARCELE&outputFormat=application/json&srsName=EPSG:3794&resourceId=UPRAVNI_AKTI_PARCELE.519563
```

The production client also supplies bounded counts, keyset CQL filters, retry
timeouts, and exact response validation.

## Published layers

| WFS type name | Local name | Meaning | Geometry |
|---|---|---|---|
| `SI.MOP.GRAD:UPRAVNI_AKTI` | `upravni_akti_tocke` | Locations of administrative acts | `Point` |
| `SI.MOP.GRAD:UPRAVNI_AKTI_PARCELE` | `upravni_akti_parcele` | Administrative-act/parcel associations | `Polygon`, stored as `MultiPolygon` |

The parcel layer is **not a canonical parcel register**. A row means that one
administrative act is associated with one cadastral parcel. One act can
therefore produce many parcel rows.

### Snapshot measured on 2026-07-24

| Layer | Raw WFS rows | Unique WFS IDs | `ZAD_SPR IS NULL` |
|---|---:|---:|---:|
| Points | 234,486 | 234,475 | 1 |
| Act/parcel associations | 630,026 | 630,012 | 14 |

The raw counts include identical duplicate WFS IDs. The downloaded GeoPackage
preserves every published row. The PostGIS mirror stores one canonical row per
WFS ID.

### GeoPackage size

The completed file is 538,370,048 bytes, or 513.43 MiB.

| Layer | Feature table | Spatial indexes | Total |
|---|---:|---:|---:|
| Act/parcel associations | 397.34 MiB | 32.47 MiB | 429.81 MiB |
| Points | 71.40 MiB | 12.14 MiB | 83.54 MiB |
| GeoPackage metadata |  |  | approximately 0.08 MiB |

- Parcels: approximately 83.7% of the file
- Points: approximately 16.3% of the file

## Field reference

`DescribeFeatureType` publishes field names, XML types, and nullability, but
not a complete business glossary. Meanings marked **name-derived** should be
confirmed with the eProstor data owner before being used for legal or business
decisions.

### Point layer

| Field | Stored type | Role or likely meaning |
|---|---|---|
| `ID_UA` | integer | Administrative-act identifier; verified integration attribute, but not used as the mirror primary key |
| `SIF_PU` | integer | Published code; exact business definition not present in the WFS schema |
| `NAZ_UPR_ORG` | text | Name of the administrative organisation, name-derived |
| `STEV_ZAD` | text | Case/reference number, name-derived |
| `OB_ID` | integer | Municipality identifier, name-derived |
| `SIF_VRS_UA_KRA_SIF` | text | Published administrative-act classification code |
| `VRS_AKT_2` | text | Published secondary act-type code/label |
| `NAZ_UPR_POS` | text | Published administrative-procedure/act name |
| `OBJ` | text | Object/subject description, name-derived |
| `DAT_IZD` | timestamp | Published date field; likely issue date |
| `DAT_POP` | timestamp | Published date field; exact business definition not present in the schema |
| `MAX_DAT_PRA` | timestamp | Published date field; exact business definition not present in the schema |
| `DAT_RAZ` | timestamp | Published date field; exact business definition not present in the schema |
| `ZAD_SPR` | timestamp | Last source change; used for delta comparison |
| `VRS_AKT` | integer | Administrative-act type code |
| `DAT_ZAC_GRA` | timestamp | Published construction-start date, name-derived |
| `GEOMETRY` | geometry | Point location; GeoServer may duplicate it inside properties and top-level GeoJSON |

### Act/parcel layer

| Field | Stored type | Role or likely meaning |
|---|---|---|
| `ID_UA` | integer | Administrative act associated with the parcel |
| `OB_ID` | integer | Municipality identifier, name-derived |
| `SIFKO` | integer | Cadastral municipality code |
| `PARCELA` | text | Parcel number; kept as text because values include `/` and `*` |
| `ZAD_SPR` | timestamp | Last source change; used for delta comparison |
| `VRS_AKT` | integer | Administrative-act type code |
| `BARVA_POLIGONA` | text | Hex display colour, for example `#cc2a12` |
| `GEOMETRY` | geometry | Parcel polygon, normalized to `MultiPolygon` in PostGIS |

Older exports can expose `BARVA_POLIGONA` under a shortened physical name such
as `barva_poli`. This is a format/loader naming limitation, not a different
business field.

## Identity and primary keys

### Identifier mapping

| Location | Identifier |
|---|---|
| WFS CSV inventory | `FID` |
| WFS GeoJSON | top-level feature `id` |
| Raw GeoPackage | `_wfs_id` |
| PostGIS mirror | `wfs_id TEXT PRIMARY KEY` |
| GeoPackage internals | `fid`, a local GeoPackage row ID |
| Older imported table | `ogc_fid`, a technical row/export ID |

Use the current WFS feature ID as the canonical identity during synchronization:

```text
FID → _wfs_id → wfs_id
```

Do **not** use these as the delta primary key:

- `ID_UA`: one act can have many parcel rows.
- `SIFKO + PARCELA`: the same parcel can be associated with multiple acts.
- GeoPackage `fid`: generated by the local file.
- Old `ogc_fid`: generated or assigned by the previous export/table and not
  stable across snapshots.

Current distinct-value evidence:

| Layer | Raw rows | Distinct `ID_UA` | Distinct WFS IDs |
|---|---:|---:|---:|
| Points | 234,486 | 234,475 | 234,475 |
| Parcels | 630,026 | 233,806 | 630,012 |

### Duplicate WFS IDs

The live service currently publishes:

- 11 additional point rows sharing an existing WFS ID
- 14 additional parcel rows sharing an existing WFS ID

The observed duplicates are byte-for-byte identical for the same identity.
Rules:

1. Preserve all raw rows in the archival GeoPackage.
2. Canonicalize identical WFS-ID duplicates to one PostGIS row.
3. Abort if two rows with the same WFS ID contain conflicting data.

### WFS-ID stability

The service does not formally document long-term stability of feature IDs.
Observed historical data proves that old technical IDs cannot be matched
directly to current WFS IDs.

Example from the older 491,885-row table:

| Attribute | Old snapshot | Current snapshot |
|---|---|---|
| Technical ID | `ogc_fid=491885` | `_wfs_id=UPRAVNI_AKTI_PARCELE.519563` |
| `ID_UA` | 314428 | 314428 |
| `OB_ID` | 106 | 106 |
| `SIFKO` | 2635 | 2635 |
| `PARCELA` | `138/4` | `138/4` |
| `VRS_AKT` | 3 | 3 |
| Colour | `#cc2a12` | `#cc2a12` |

The business row is the same while its technical identifier changed. A WFS-ID
change still converges safely in the current reconciliation algorithm: insert
the new ID and delete the old absent ID. It can, however, cause unnecessary
row churn.

## Change timestamps

### Source timestamp

`ZAD_SPR` is the only published field used to decide whether an existing
feature changed.

PostGIS stores:

| Column | Meaning |
|---|---|
| `zad_spr` | Original source attribute |
| `source_updated_at` | UTC-normalized copy of `ZAD_SPR`, used by reconciliation |
| `synced_at` | Time our process last wrote the row; not a source modification time |

Delta comparison:

```text
target row missing
OR source.source_updated_at IS NULL
OR source.source_updated_at IS DISTINCT FROM target.source_updated_at
```

Rows with `ZAD_SPR IS NULL` are fetched and upserted on every run because the
source provides no timestamp with which to prove unchangedness.

### Time zones

GeoJSON includes a UTC offset, typically `Z`. GeoServer CSV returns the same
timestamp as local civil time without an offset.

Verified example:

```text
CSV:     2023-07-28T00:00:00
GeoJSON: 2023-07-27T22:00:00Z
```

The CSV value is interpreted in `Europe/Ljubljana`, including daylight-saving
rules, and converted to UTC before comparison or storage.

An old UI can therefore display `01.12.2023` while the GeoPackage contains
`2023-11-30T23:00:00Z`; these represent the same Ljubljana local date/time.

### Unusual date values

The live point layer contains syntactically valid XSD dates outside pandas'
nanosecond timestamp range, including observed years `0002`, `0021`, `0202`,
and `2919`. They are retained as valid dates rather than silently converted to
null. PostgreSQL `timestamptz` accepts these observed values.

This issue was observed in date fields such as `DAT_ZAC_GRA`, not in the
normal recent `ZAD_SPR` inventory used for delta comparison.

## Delta reconciliation

The synchronization does not rely on a timestamp watermark alone. A watermark
cannot detect source deletions.

For each layer:

1. Read the initial raw WFS `numberMatched`.
2. Stream the complete geometry-free CSV inventory:
   `FID + ID_UA + ZAD_SPR`.
3. Canonicalize identical FID duplicates and reject conflicting duplicates.
4. Compare the inventory with PostGIS by `wfs_id`.
5. Select:
   - IDs absent from PostGIS
   - IDs with a different `source_updated_at`
   - IDs whose source timestamp is null
6. Fetch complete selected features in bounded WFS `resourceId` batches.
7. If GeoServer omits one member of a multi-ID response, retry that ID alone.
8. Require the final response ID set to match the requested set exactly.
9. Calculate target IDs absent from the complete current inventory.
10. Recheck both raw WFS counts.
11. In one database transaction:
    - upsert changed/new rows
    - delete absent IDs
    - verify canonical target counts
    - update `sync_state` for both layers

The most recent live convergence test after bootstrap produced:

| Layer | Canonical rows | Features downloaded | Inserted | Updated | Deleted |
|---|---:|---:|---:|---:|---:|
| Points | 234,475 | 1 | 0 | 1 | 0 |
| Parcels | 630,012 | 14 | 0 | 14 | 0 |

Only null-timestamp rows required refresh.

### Source snapshot limitation

WFS does not provide a transactional snapshot across requests. The client
checks counts before and after staging, but a rare concurrent replacement that
keeps the same total count may only converge on the following run.

No target mutation occurs until both layers have been staged and the final
database transaction begins.

## Older 491,885-row table

The supplied table with fields such as:

```text
ogc_fid, id_ua, ob_id, sifko, parcela, zad_spr, vrs_akt, barva_poli
```

is an older export of the same `UPRAVNI_AKTI_PARCELE` subject. Sample rows were
matched against the current dataset using their business attributes.

| Dataset | Rows |
|---|---:|
| Older table | 491,885 |
| Current raw snapshot | 630,026 |
| Increase | 138,141 |

Migration guidance:

1. Do not continue a delta from old `ogc_fid` values.
2. Replace/bootstrap from the completed current GeoPackage.
3. Start recurring reconciliation using the current `wfs_id`.

Trying to construct a business composite key for all old rows is unnecessary
and can be ambiguous.

## Local and Lift names

Recommended technical names when a dedicated schema is available:

```text
eprostor.upravni_akti_tocke
eprostor.upravni_akti_parcele
```

When Lift requires globally prefixed table names:

```text
eprostor_upravni_akti_tocke
eprostor_upravni_akti_parcele
```

Recommended display names:

```text
eProstor – Upravni akti – točke
eProstor – Upravni akti – parcele
```

The parcel display name must not imply that this is the authoritative cadastral
parcel register.

## Downloaded artifact

Files:

```text
data/upravni_akti.gpkg
data/upravni_akti.gpkg.manifest.json
data/upravni_akti.gpkg.sha256
```

Verified publication:

- GeoPackage integrity: `ok`
- SHA-256:
  `d55cfd30540824cd0d8f2d92237b13603ec2ce2127a78d68548092021dcefaaf`
- Manifest version: 1
- CRS: `EPSG:3794`
- Point schema fingerprint:
  `fc67fb01fb74b6e8de8a9b144f6148962978651979d272ece572ce52f115a4ce`
- Parcel schema fingerprint:
  `ec0870681202d9fdf7d7b98a5c35fe69f291898f2ed98623835f1639f48d0be1`

The GeoPackage is the raw archival snapshot. PostGIS is the canonical,
deduplicated operational mirror.

## Known facts versus assumptions

Verified directly:

- endpoints, WFS request behavior, fields, types, geometry, CRS
- current raw and unique counts
- duplicate-ID behavior
- old/current sample-row correspondence
- `ZAD_SPR` timezone equivalence between CSV and GeoJSON
- unusual source date years
- checkpoint, bootstrap, and live delta convergence

Not formally guaranteed by the inspected WFS metadata:

- long-term WFS feature-ID stability
- complete business definitions of abbreviated fields
- transactional consistency across multiple WFS requests

Consumers requiring legally authoritative meanings must obtain the official
business glossary from the eProstor data owner.
