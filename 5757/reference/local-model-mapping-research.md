# Local model migration evidence

Inspected 2026-10-15. Scope: local `/Users/matevzvidovic/isam` source only. No database connections or credentials were used for this note.

## What the migration proves

The import reads GV model definitions, including `gv_verzije`, and writes temporary source copies named `primoz_*`. It selects the requested versions by the pair `(model, verzija)`; it does not use an EV numeric model-version ID to select them. See [source validation](/Users/matevzvidovic/isam/modeliranje/migracija/prenos_gv_podatkov.py:206) and [source table list](/Users/matevzvidovic/isam/modeliranje/migracija/prenos_gv_podatkov.py:63).

The import copies every reflected source column, with special treatment for geometry and documented column renames. Therefore additional source version metadata can survive in `primoz_gv_verzije` even if the model-population SQL does not use it. This is a reason to inspect those source columns in the database, not proof that a particular mapping field is populated. See [column copying](/Users/matevzvidovic/isam/modeliranje/migracija/prenos_gv_podatkov.py:246).

For IND 51, the population SQL creates a new UUID but copies `model` and `verzija` directly from the source row. It sets ISAM `datum_modela` from `to_date(datum_na::text, 'YYYYMMDD')` and `leto_akt` from that date's year. It filters `primoz_gv_verzije` to IND 51. Thus **GV IND 51 becomes ISAM IND 51**, with a different technical UUID. See [IND 51 insertion](/Users/matevzvidovic/isam/modeliranje/migracija/migracija_modelov/zgodovinske_verzije_2020/polnitev_gradnikov_isam2_ind_v51.sql:238).

IND 66 follows the same identity/date transfer, selecting GV IND 66. Its `leto_akt` is the literal 2025. See [IND 66 insertion](/Users/matevzvidovic/isam/modeliranje/migracija/migracija_modelov/verzije_2025/polnitev_gradnikov_isam2_ind.sql:48).

## Versions represented by the local scripts

The current-set scripts target DRZ 16, GAR 90, GOZ 96, HIS 286, IND 66, INP 49, KDS 46, KME 100, PPL 192, PPP 225, SDP 33, STA 223, STZ 44, TUR 42, plus PPL_MN 24, PPL_NAJ 47, PPP_MN 21 and PPP_NAJ 41. These are script targets, not a claim that every version has been successfully imported into staging. Each script's opening `md_verzije_modeli` selection states its target; see the [script directory](/Users/matevzvidovic/isam/modeliranje/migracija/migracija_modelov/verzije_2025).

The importer default selection includes DRZ 16, GAR 90, GOZ 36, HIS 161, IND 51, INP 36, KDS 26, KME 81, PPL 151, PPP 185, SDP 18, STA 150, STZ 13, TUR 26 and ZGS 80/129. See [default versions](/Users/matevzvidovic/isam/modeliranje/migracija/prenos_gv_podatkov.py:42).

**Do not use directory names to infer the valuation date.** The historical-set documentation explicitly notes that GAR 90 is a 2025 model and DRZ 16 uses 2024 for `leto_akt`. See [historical migration notes](/Users/matevzvidovic/isam/modeliranje/migracija/migracija_modelov/zgodovinske_verzije_2020/README.md:112).

## What this does not establish

Searches of local source did not find literal references to `rmodel_oid`, `verzija_pripis` or EV `id_model_ver`. No inspected local code establishes `EV 1150 → IND 51` or `EV 1150 → IND 66`. These are still database research questions.

The migration establishes **model date**, not a compulsory property-state cutoff. The IND 51 transaction filter is 2015-01-01 through 2020-01-31; that is the selection of sales used for modeling, not an instruction to calculate every property on either endpoint. See [filter](/Users/matevzvidovic/isam/modeliranje/migracija/migracija_modelov/zgodovinske_verzije_2020/polnitev_gradnikov_isam2_ind_v51.sql:267).

## Implication for the EV/KN investigation

Look for a source metadata bridge that identifies the same model definition in the GV numbering and EV numbering: model code, GV version, EV model-version ID, source model date and any assignment/effective-date fields. Establish that bridge using actual rows or foreign keys before hardcoding it. Then independently establish the date represented by EV values and KN property inputs. A model's `datum_na` alone does not prove the property-state snapshot date.
