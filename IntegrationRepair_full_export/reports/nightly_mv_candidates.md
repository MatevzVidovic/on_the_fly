# Nightly spike: MV candidates and schedule verification

Live schedule verification was blocked by a database connection timeout. The 22 October saved integration audit has `sync_schedule=none` for all 49 captured SQL delta integrations; that is historical evidence, not the current schedule. Therefore these candidates are not a confirmed nightly cron list.

The saved MV/routing snapshot was captured on 2026-10-29T08:01:08.759948+00:00. Sizes include indexes and are not measured WAL per execution.

| MV | GiB | Random UUID | Configured integration sources |
|---|---:|:---:|---|
| `kn_nep_parcele_a` | 6.104 | Yes | `kn_nep_parcele_h` |
| `pp_kn_parcele_mv` | 3.822 | Yes | `kn_nep_ostalo_parcele_x_dejanske_rabe_h`, `kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h`, `kn_nep_ostalo_parcele_x_namenske_rabe_h`, `kn_nep_parcele_h` |
| `kn_nep_deli_stavb_stavbe` | 3.081 | Yes | `ev_del_stavbe_enota_h_2025_danes`, `kn_nep_deli_stavb_h`, `kn_nep_stavbe_centroidi_h`, `kn_nep_stavbe_obrisi_h`, `kn_nep_stavbe_zps_h` |
| `kn_nep_parcele` | 2.750 | No | `ev_parc_enota_h_2025_danes`, `kn_nep_parcele_h` |
| `pp_kn_deli_stavb_mv` | 2.262 | Yes | `ev_del_stavbe_enota_h_2025_danes`, `kn_nep_deli_stavb_h`, `kn_nep_etaze_h`, `kn_nep_etaze_x_deli_stavb_h`, `kn_nep_prostori_h`, `kn_nep_stanovanja_h`, `kn_nep_stavbe_centroidi_h`, `kn_nep_stavbe_obrisi_h`, `kn_nep_stavbe_parcele_h`, `kn_nep_stavbe_zps_h` |
| `kn_nep_stavbe_parcele_a` | 1.434 | Yes | `kn_nep_stavbe_parcele_h` |
| `kn_nep_stavbe_obrisi_a` | 1.307 | Yes | `kn_nep_stavbe_centroidi_h`, `kn_nep_stavbe_obrisi_h` |
| `kn_nep_deli_stavb_a` | 0.843 | Yes | `kn_nep_deli_stavb_h` |
| `kn_nep_naslovi_view` | 0.187 | No | `kn_nep_hisne_stevilke_h`, `kn_nep_rpe_naselja_h`, `kn_nep_rpe_ulice_h` |
| `kn_nep_katastrske_obcine_a` | 0.038 | Yes | `kn_nep_katastrske_obcine_h` |

Shared MVs can be requested by multiple source workflows. A per-source debounce does not globally deduplicate shared MV work. The integration Temporal refresh activity uses CONCURRENTLY; random UUIDs can therefore turn unchanged business rows into persistent delete/insert churn. Actual nightly causation needs workflow/SQL execution timestamps matched to WAL LSN deltas.

Run from the project directory when production connectivity is available:

```bash
.venv/bin/python diagnostics/audit_scheduled_mv_refreshes.py
```

This query includes all currently configured scheduled integrations, not only EV/KN. It makes no changes. Check the actual Temporal schedule enabled state/timezone separately; cron configuration alone does not prove an execution occurred.
