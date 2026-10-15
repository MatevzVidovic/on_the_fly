# Exported EV → ISAM version identities

Exported 2026-10-15T11:06:06.404143+00:00.

All staging model-version rows are listed. Oracle metadata was filtered to their model codes, including older definitions. No full model XML or property export was performed.

`VERSION_IDENTITY_MATCH` requires one candidate, agreeing original/runtime XML version markers, and matching model dates. It does not prove formula/input equivalence. Other statuses require review; no fallback mappings are invented.

[JSON with source headers and dates](mapping.json) · [CSV](mapping.csv)

| Model | ISAM version | EV candidates | Status |
|---|---:|---|---|
| DRZ | 16 | 1169 | MODEL_DATE_MISMATCH |
| GAR | 90 | 1170 | VERSION_IDENTITY_MATCH |
| GOZ | 36 | — | NO_EXPLICIT_MATCH |
| GOZ | 96 | 1171 | VERSION_IDENTITY_MATCH |
| HIS | 161 | 1149 | VERSION_IDENTITY_MATCH |
| HIS | 286 | — | NO_EXPLICIT_MATCH |
| HIS | 287 | — | NO_EXPLICIT_MATCH |
| HIS | 288 | — | NO_EXPLICIT_MATCH |
| HIS | 289 | — | NO_EXPLICIT_MATCH |
| HIS | 290 | — | NO_EXPLICIT_MATCH |
| IND | 51 | 1150 | VERSION_IDENTITY_MATCH |
| IND | 66 | 1173 | VERSION_IDENTITY_MATCH |
| IND | 67 | — | NO_EXPLICIT_MATCH |
| IND | 68 | — | NO_EXPLICIT_MATCH |
| INP | 36 | 1151 | VERSION_IDENTITY_MATCH |
| INP | 49 | 1174 | VERSION_IDENTITY_MATCH |
| KDS | 26 | 1157, 1165 | AMBIGUOUS |
| KDS | 46 | 1175 | VERSION_IDENTITY_MATCH |
| KME | 81 | 1161 | VERSION_IDENTITY_MATCH |
| KME | 100 | 1176 | VERSION_IDENTITY_MATCH |
| KME | 101 | — | NO_EXPLICIT_MATCH |
| PPL | 151 | 1152 | VERSION_IDENTITY_MATCH |
| PPL | 192 | 1177 | VERSION_IDENTITY_MATCH |
| PPL_MN | 24 | — | NO_EXPLICIT_MATCH |
| PPL_NAJ | 47 | — | NO_EXPLICIT_MATCH |
| PPP | 185 | 1153 | VERSION_IDENTITY_MATCH |
| PPP | 225 | 1178 | VERSION_IDENTITY_MATCH |
| PPP_MN | 21 | — | NO_EXPLICIT_MATCH |
| PPP_NAJ | 41 | — | NO_EXPLICIT_MATCH |
| SDP | 18 | 1154 | VERSION_IDENTITY_MATCH |
| SDP | 33 | 1179 | VERSION_IDENTITY_MATCH |
| STA | 150 | 1148 | VERSION_IDENTITY_MATCH |
| STA | 223 | 1180 | VERSION_IDENTITY_MATCH |
| STA | 224 | — | NO_EXPLICIT_MATCH |
| STZ | 13 | 1164 | VERSION_IDENTITY_MATCH |
| STZ | 44 | 1181 | VERSION_IDENTITY_MATCH |
| TUR | 26 | — | NO_EXPLICIT_MATCH |
| TUR | 42 | 1182 | VERSION_IDENTITY_MATCH |
| None | None | — | NO_EXPLICIT_MATCH |
| None | None | — | NO_EXPLICIT_MATCH |

Regenerate from the workspace root:

```bash
uv --cache-dir /tmp/5757-uv-cache run --no-project --with oracledb --with python-dotenv python 5757/model-mapping/export_mapping.py
```

Credentials are read programmatically from `5757/.env`. Both databases are queried read-only and rolled back. The Oracle call timeout is eight seconds. Read the [date research](../reference/ev-isam-model-version-research.md) before choosing a property cutoff.
