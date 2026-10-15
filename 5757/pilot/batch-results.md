# IND 66: first corrected 10-unit batch

Run: 2026-10-15T11:06:15.459435+00:00. Staging ISAM; Oracle EV history. Property cutoff **2026-01-01**, expected EV version **1173**.

Convenience sample of 10 prepared IND units, not a representative population sample. All 10 had one EV record valid at the cutoff with the expected model. No missing/duplicate/version-mismatch diagnostics occurred in this batch.

| Building-part ID | ISAM calculated | EV calculated | ISAM − EV | ISAM generalized | EV generalized | ISAM − EV | Result |
|---|---:|---:|---:|---:|---:|---:|---|
| 29974237 | 15310.00 | 14824.32 | 485.68 | 15300 | 14800 | 500 | Difference |
| 34797757 | 136122.00 | 155374.8 | -19252.80 | 136100 | 155400 | -19300 | Difference |
| 35484785 | — | 67449.6 | — | — | 67400 | — | ISAM error |
| 29843044 | 15589.00 | 16301.4 | -712.40 | 15600 | 16300 | -700 | Difference |
| 29893278 | 16864.00 | 17676.25 | -812.25 | 16900 | 17700 | -800 | Difference |
| 35811761 | — | 94528 | — | — | 94500 | — | ISAM error |
| 37105777 | — | 242654.4 | — | — | 242700 | — | ISAM error |
| 29348451 | 137221.00 | 150045.58 | -12824.58 | 137200 | 150000 | -12800 | Difference |
| 100000028216 | 243282.00 | 283358.05 | -40076.05 | 243300 | 283400 | -40100 | Difference |
| 37336741 | — | 370818.43 | — | — | 370800 | — | ISAM error |

**Six numeric differences; four ISAM calculation failures.** All four failures report:

```text
pogoji_neustrezeni (id_konstrukcije=0): f_nk; manjka: f_nk
```

Errors remain errors: no difference is calculated from a missing ISAM amount.

For building part **29974237**, the corrected difference is **485.68**, not the old 8077.12 obtained with different model generations. This remains a candidate for input/intermediate investigation, not proof that the ISAM formula is wrong. Existing ISAM values may predate the decimal migration.

[Full source IDs, revision numbers, validity intervals and errors](latest-comparison.json) · [CSV](latest-comparison.csv) · [How to run](README.md) · [Exported model mappings](../model-mapping/README.md)
