# EV tables: row estimates and sizes

Recorded 2026-10-26 from user-supplied query results. Original migration order;
GURS ORACLE integrations excluded. Row counts are PostgreSQL estimates, not exact
counts. Sizes include current allocated space, including reusable/dead-row space.
PostgreSQL's displayed MB/kB use binary units. These measurements do not establish
backfill or integration-configuration completion.

| # | Table | Estimated rows | Table + TOAST | Indexes | Total | Total bytes |
|---:|---|---:|---:|---:|---:|---:|
| 1 | `ev_del_stavbe_enota_h_2025_danes` | 4,894,832 | 1794 MB | 1218 MB | 3012 MB | 3,158,777,856 |
| 2 | `ev_del_stavbe_h` | 11,060,290 | 2901 MB | 1008 MB | 3909 MB | 4,099,252,224 |
| 3 | `ev_dst_pripis_podatki_h` | 1,949,304 | 482 MB | 118 MB | 601 MB | 629,743,616 |
| 4 | `ev_parc_del_h` | 16,970,546 | 3001 MB | 1078 MB | 4080 MB | 4,277,731,328 |
| 5 | `ev_parcela_h` | 26,522,398 | 5479 MB | 3725 MB | 9204 MB | 9,650,937,856 |
| 6 | `ev_parc_enota_h_2025_danes` | 26,499,532 | 5344 MB | 3762 MB | 9106 MB | 9,548,038,144 |
| 7 | `ev_parc_pripis_podatki_h` | 8,826,980 | 1776 MB | 535 MB | 2311 MB | 2,423,750,656 |
| 8 | `ev_pe_dst_h` | 210,842 | 45 MB | 18 MB | 64 MB | 66,674,688 |
| 9 | `ev_posebna_enota_h` | 45,222 | 48 MB | 2816 kB | 50 MB | 52,830,208 |
| 10 | `ev_prostor_h` | 4,658,110 | 726 MB | 280 MB | 1006 MB | 1,054,367,744 |
| 11 | `ev_stavba_h` | 3,188,498 | 1234 MB | 502 MB | 1735 MB | 1,819,680,768 |

Thursday's backfill crash occurred at #5, `ev_parcela_h`. #9,
`ev_posebna_enota_h`, was used for the subsequent small-table WAL experiments.
The sizes above do not include cluster-wide WAL or Barman backup storage.
