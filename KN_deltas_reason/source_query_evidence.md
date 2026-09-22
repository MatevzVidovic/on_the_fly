# First integration: supplied source query

Captured from the user's metadata export on 2026-09-22. Target: `kn_nep_deli_stavb_h`. Integration: `bfe62b52-9aaf-11ef-9c54-0242ac120008`. Changed-datetime delta is enabled; the exported LIFT watermark was `2026-09-18 15:29:40.000000`. That watermark is evidence only, not the experimental baseline boundary.

```sql
SELECT
DEL_STAVBE_H_ID,
DEL_STAVBE_ID,
STAVBA_ID,
HISNA_STEVILKA_ID,
UPRAVNIK_ID,
VRSTA_DEJANSKE_RABE_DEL_ST_ID,
DVIGALO,
LETO_OBNOVE_INSTALACIJ,
LETO_OBNOVE_OKEN,
POVRSINA,
STATUS,
ST_DELA_STAVBE,
STANOVANJE_ID,
UPORABNA_POVRSINA,
PROSTORNINA_CISTERN_SILOSOV,
POSTOPEK_ID_OD,
POSTOPEK_ID_DO,
FROM_TZ(CAST(DATUM_OD AS TIMESTAMP), 'Europe/Ljubljana') DATUM_OD,
FROM_TZ(CAST(DATUM_DO AS TIMESTAMP), 'Europe/Ljubljana') DATUM_DO,
FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') DATUM_SYS,
EID,
NACIN_DOLOCITVE_POVRSINE_DELA_STAVBE_ID,
UPRAVNIK_STATUS,
OMEJITEV_VPOGLEDA,
ETAZNA_LASTNINA,
SKUPNI_DEL_ETAZNA_LASTNINA
FROM nep.DELI_STAVB_H
```

The query exposes no separate row-creation audit field. `DATUM_OD` and `DATUM_DO` describe validity according to the existing task evidence; neither is established as creation time. `DATUM_SYS` is the change timestamp under investigation. The matching key documented in the task is `DEL_STAVBE_H_ID`; uniqueness/null checks remain a runtime prerequisite for interpreting snapshots.

The user also supplied an IDE-generated DDL listing the same columns. It contains `unknown` types and empty primary-key/index column lists. It reveals no additional creation/update timestamp field and cannot establish the key's actual constraint columns, source data types, or whether a useful timestamp index exists. Do not infer that an empty index definition means the real index has no columns.
