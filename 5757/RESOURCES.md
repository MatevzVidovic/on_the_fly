# 5757 Resources

## Knowledge

- [Task requirements](5757.md)
  Primary source for the actual requested changes: decimals, final/intermediate comparisons, parcel aggregation, translation, Lift tables, workflow and SFC.
- [Database access pointers](README.md)
  Identifies access instructions under the available VPN. Not a schema specification; lesson 0001 used code; lesson 0002 adds read-only checks against reachable test_njihov_access.
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

- [Database column metadata](reference/db-columns-test_njihov_access.json)
  Read-only information_schema evidence captured 2026-10-14. Use for confirmed ISAM/EV column names and types.
- [Date/model relationship check](reference/db-relationship-check.json)
  Bounded joins confirm actual date/model selections; catalog queries capture indexes.

- [EV version field check](reference/db-ev-version-check.json)
  Bounded current-value samples and metadata confirm id_model_ver exists; examples do not establish semantic mappings or historical date equivalence.
- [ISAM version candidates](reference/db-version-candidates.json)
  Bounded STA/STZ model-version rows and candidate metadata. No authoritative EV correspondence was established.
- [EV integration source SQL](../EV_INTEG/src/kn_to_stag_delta_with_delete/ev_del_stavbe_enota_h_2025_danes_kn.sql)
  Copies upstream ID_MODEL_VER. The corresponding Lift historical projection omits it; the current inspected building-part history table also lacks it. A query definition is not proof of deployed integration configuration.

- [Solution prerequisite recheck](reference/db-solution-prerequisites.json)
  Read-only check dated 2026-10-15: calculated-value column remains integer; bounded catalog search for proposed comparison naming found no matches. Does not inspect live Lift metadata or rule out other names.

- [EV parcel table check](reference/db-ev-parcel-tables.json)
  Read-only metadata on 2026-10-15 distinguishes parcel master ev_parcela, valuation rows ev_parc_enota, historical structure ev_parc_del_h and the currently audit-only ev_parc_del_enota. No row-level structure mapping was inferred.

## Wisdom (Communities)

No community research needed for this first lesson. The task calls for agreement with GURS on uncertain parcel representation and rounding business rules.

## Gaps

- Live Lift field metadata has not been verified. PostgreSQL vrednost_izr was confirmed integer on 2026-10-14.
- EV final and intermediate candidate tables are now identified by database metadata. Historical date semantics, model-version correspondence and canonical translations still require analysis.
- Tolerance, parcel rounding policy and per-model semantic component keys need confirmation.
