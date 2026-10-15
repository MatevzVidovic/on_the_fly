# Deferred investigations for 5757

These findings are saved for later. First implement the ticket's comparison workflow and inspect the wider set of differences. Then return to the individual causes below. Recording a finding here does not mean a correction has been applied.

## IND 66: coefficient precision and size difference

**Status: deferred; investigated on one building part; no correction applied.**

Scope: building part **29974237**, property cutoff **2026-01-01**, staging ISAM **IND 66**, dated Oracle EV model **1173**.

Stored calculated values:

- ISAM: **15310.00**.
- EV: **14824.32**.
- ISAM − EV: **485.68**.

### Evidence to retain

| Ingredient | ISAM | EV |
|---|---:|---:|
| Relational m² coefficient | **0.04** | **0.036** |
| Size | **28.63** | **28.6** |
| Land component | 10500 | 10500 |

The live ISAM coefficient row contains `0.04`. The EV model XML contains `0.036` for the corresponding class. The local IND migration explicitly rounds the coefficient to two decimals, providing a concrete mechanism for this loss of precision.

The captured-data arithmetic accounts for the full difference:

| Contribution | Exact amount |
|---|---:|
| Coefficient precision, holding size at 28.63 | 480.984 |
| Size difference, using coefficient 0.036 | 4.536 |
| Stored ISAM total minus reconstructed formula | 0.160 |
| **Total** | **485.680** |

The final 0.16 is consistent with the former integer storage, but the historical writer was not rerun or independently verified. The size discrepancy remains unresolved; do not assume or introduce a global rounding rule from this example.

### Return to this after the broader comparison

1. Check how widely coefficient precision affects IND and whether other migrations have the same issue.
2. Preserve the required source coefficient precision in the migration and model data.
3. Establish the EV size-processing rule and input alignment before changing ISAM size calculations.
4. Recalculate a bounded scope after correcting model data, then rerun the dated comparison.

Correcting only the coefficient would reconstruct **14828.86**, still **4.54** above EV after rounding to cents. Changing the final result column to decimal does not repair existing model coefficients or recover fractions lost in old stored results.

### Saved investigation and reproduction

- [Full explanation, source row IDs and code locations](pilot/29974237/README.md).
- [Decoded ingredients and exact arithmetic ledger](pilot/29974237/replay-result.json).
- [Original corrected 10-unit batch](pilot/batch-results.md).

Offline replay, requiring no database access:

```bash
python3 5757/pilot/29974237/replay.py
```

This reconstructs the captured amounts; it does not execute the live calculation pipeline. Keep the original evidence when later refreshing the comparison results.
