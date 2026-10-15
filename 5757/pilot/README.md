# IND pilot: a few building parts, with the correct EV model

This script reads existing ISAM results from staging and compares them with **Oracle EV history valid on the selected property cutoff**. It does not run the IND model or modify either database.

## Run

From the workspace root:

```bash
uv --cache-dir /tmp/5757-uv-cache run --no-project --with oracledb --with python-dotenv python 5757/pilot/compare_ind.py
```

Default: **IND 66 ↔ EV 1173**, property cutoff **2026-01-01**, at most **10 building parts**. Connection settings are loaded programmatically from `5757/.env`; `psql` must be installed and VPN/database access available.

Choose specific units:

```bash
uv --cache-dir /tmp/5757-uv-cache run --no-project --with oracledb --with python-dotenv python 5757/pilot/compare_ind.py --units 29974237 34797757 35484785
```

Use `--limit 5` for a smaller convenience sample. Maximum 20. Use `--date YYYY-MM-DD --version 51` for IND 51, but a corresponding prepared/calculated ISAM date/model configuration must exist. The script does not create one.

Each run writes [latest-comparison.json](latest-comparison.json) with full evidence and [latest-comparison.csv](latest-comparison.csv) with the compact values. `--output path.json` changes both output paths. The saved IDs make the convenience sample reproducible with `--units`; the default is not random and must not be interpreted as population error rates.

## What the simple code does

1. Reads the exported [version mapping](../model-mapping/mapping.json). Requires one candidate with agreeing XML version markers and matching model dates, then checks the live ISAM model UUID.
2. Finds exactly one ISAM model/date configuration and reads a bounded list of prepared-unit results. Missing ISAM data remains visible for explicitly requested IDs.
3. For each selected unit, reads Oracle `EV.JN_DEL_STAVBE_ENOTA` joined to `EV.REVISION`, selecting `valid_from <= cutoff < valid_to`, or an open end. The cutoff is midnight in source-local Europe/Ljubljana wall time.
4. Checks the **actual selected EV version** against the exported mapping. A wrong model version is reported rather than filtered away and mistaken for a missing row. Two candidates on either side cause an ambiguity diagnostic.
5. Subtracts calculated and generalized values independently: **ISAM − EV**, using exact `Decimal` arithmetic. Source errors and missing values suppress deltas; NULL never becomes zero. Equality is exact; no final-status tolerance policy is assumed.

There are no permanent tables, SFCs or intermediate translation rules yet. Oracle reads are sequential indexed unit lookups, each in a read-only transaction ending with rollback and an eight-second call timeout. PostgreSQL uses the existing read-only helper with timeouts and rollback.

## First corrected batch

See [batch-results.md](batch-results.md). All 10 units had a dated EV record using the expected version 1173. Six have calculated/generalized differences; four have an ISAM calculation error involving `f_nk` and `id_konstrukcije=0`.

Version identity and record validity are checked. **Input equivalence and the cause of each difference are not established.** The ISAM schema is now decimal, but old values may still require recalculation to recover fractions. These are existing stored results.

The next small investigation can use `29974237`: compare its prepared inputs, variables and factors with the corresponding dated EV intermediate record. The four failed ISAM records provide a separate useful case for investigating input preparation or `f_nk` applicability.

## Earlier exploratory output

[example-result.json](example-result.json) is retained as historical evidence of the original run. That run used the **wrong provisional 66 → 1150 mapping and an undated current EV table**. The updated script no longer uses that approach. See the [date/model research](../reference/ev-isam-model-version-research.md).
