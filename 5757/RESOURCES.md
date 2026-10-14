# 5757 Resources

## Knowledge

- [Task requirements](5757.md)
  Primary source for the actual requested changes: decimals, final/intermediate comparisons, parcel aggregation, translation, Lift tables, workflow and SFC.
- [Database access pointers](README.md)
  Identifies access instructions under the available VPN. Not a schema specification; live database not inspected in lesson 0001.
- [ISAM date resolution](../symlinks/lift-temporal-python/src/packages/_gurs/priprava_prepisa/priprava_pripisa.py)
  `resolve_presecni_datum` reads `id, datum` from `pripis_presecni_datum`.
- [Configured models for a date](../symlinks/lift-temporal-python/src/packages/_gurs/modeling/pipeline.py)
  `_build_pripis_model_filters` joins date-scoped units, `pripis_vm_x_pd` and `md_verzije_modeli`.
- [Calculation result writer](../symlinks/lift-temporal-python/src/packages/_gurs/modeling/zapis_md_trans.py)
  `_zapis_pripis` writes `pripis_vmxpd_x_enote` with `id_rel_vm_pd`, `id_rel_prip_enota`, values, intermediate data and calculation errors.
- [Existing unit/result joins](../symlinks/isam/pripis/delitev_pev/izracun_delitve_pev.py)
  Existing code demonstrates joins from parcel/building-part unit tables to calculated values and the model/date selection. Its parcel-only grouping is for another task; it is not the required parcel/model/version comparison for 5757.
- [Proposed role map](5757-roles.html)
  Our design aid; run-storage and retry contracts are proposals, not additional requirements from the ticket.

## Wisdom (Communities)

No community research needed for this first lesson. The task calls for agreement with GURS on uncertain parcel representation and rounding business rules.

## Gaps

- Live Lift field metadata and PostgreSQL types have not been verified.
- Exact EV building-part and intermediate tables, date semantics and model-version correspondence require source-data analysis.
- Tolerance, parcel rounding policy and per-model semantic component keys need confirmation.
