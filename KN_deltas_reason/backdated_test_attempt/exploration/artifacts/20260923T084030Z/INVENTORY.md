# Live integrations and source tables

Includes full-sync configurations, not just delta integrations. Legacy GURS ORCL queries are tested on the migrated current KN endpoint; see query_validation.json for actual access failures.

| Target | Connection | Full sync | Source tables |
|---|---|---|---|
| etn3_address | GURS ORCL | True | ETN3.ADDRESS |
| etn3_building_part | GURS ORCL | True | ETN3.BUILDING_PART |
| etn3_building_part_h | GURS ORCL | False | ETN3.BUILDING_PART |
| etn3_building_part_prchs_det | GURS ORCL | True | ETN3.BUILDING_PART_PRCHS_DET |
| etn3_building_part_rntl_det | GURS ORCL | True | ETN3.BUILDING_PART_RNTL_DET |
| etn3_codelist | GURS ORCL | True | ETN3.CODELIST |
| etn3_contract | GURS ORCL | True | ETN3.CONTRACT |
| etn3_contract_location | GURS ORCL | True | ETN3.CONTRACT_LOCATION |
| etn3_contractor | GURS ORCL | True | ETN3.CONTRACTOR |
| etn3_contract_purchase_details | GURS ORCL | True | ETN3.CONTRACT_PURCHASE_DETAILS |
| etn3_contract_rental_details | GURS ORCL | True | ETN3.CONTRACT_RENTAL_DETAILS |
| etn3_parcel | GURS ORCL | True | ETN3.PARCEL |
| ev_del_stavbe | GURS ORCL | True | EV.DEL_STAVBE |
| ev_del_stavbe_cona_h | GURS ORCL | False | EV.JN_DEL_STAVBE_CONA, EV.REVISION |
| ev_del_stavbe_enota | GURS ORCL | True | EV.DEL_STAVBE_ENOTA |
| ev_g_ceste_l_h | GURS ORCL | False | EV.JN_G_CESTE_L, EV.REVISION |
| ev_g_el_energija_l_h | GURS ORCL | False | EV.JN_G_EL_ENERGIJA_L, EV.REVISION |
| ev_gurs_oseba_h | GURS ORCL | False | EV.JN_GURS_OSEBA, EV.REVISION |
| ev_g_zeleznice_l_h | GURS ORCL | False | EV.JN_G_ZELEZNICE_L, EV.REVISION |
| ev_nrp_parc_h | GURS ORCL | True | EV.JN_NRP_PARC, EV.REVISION |
| ev_obcina_h | GURS ORCL | False | EV.JN_OBCINA, EV.REVISION |
| ev_oseba_h | GURS ORCL | False | EV.JN_OSEBA, EV.REVISION |
| ev_oseba_pe_h | GURS ORCL | False | EV.JN_OSEBA_PE, EV.REVISION |
| ev_parc_del_cona_h | GURS ORCL | False | EV.JN_PARC_DEL_CONA, EV.REVISION |
| ev_parc_del_enota | GURS ORCL | True | EV.JN_PARC_DEL_ENOTA, EV.REVISION |
| ev_parc_enota | GURS ORCL | True | EV.PARC_ENOTA |
| ev_posebna_enota_pod_h | GURS ORCL | False | EV.JN_POSEBNA_ENOTA_POD, EV.REVISION |
| ev_sif_dr_dst_h | GURS ORCL | True | EV.JN_SIF_DR_DST, EV.REVISION |
| ev_sif_dr_parc_h | GURS ORCL | True | EV.JN_SIF_DR_PARC, EV.REVISION |
| ev_sif_dr_pros_h | GURS ORCL | True | EV.JN_SIF_DR_PROS, EV.REVISION |
| ev_sif_kontrukcija_h | GURS ORCL | True | EV.JN_SIF_KONSTRUKCIJA, EV.REVISION |
| ev_sif_lega_h | GURS ORCL | True | EV.JN_SIF_LEGA, EV.REVISION |
| ev_sif_model_h | GURS ORCL | True | EV.JN_SIF_MODEL, EV.REVISION |
| ev_sif_vpliv_h | GURS ORCL | True | EV.JN_SIF_VPLIV, EV.REVISION |
| ev_sif_vpliv_model_h | GURS ORCL | True | EV.JN_SIF_VPLIV_MODEL, EV.REVISION |
| ev_sta_par_h | GURS ORCL | False | EV.JN_STA_PAR, EV.REVISION |
| ev_stavba | GURS ORCL | True | EV.STAVBA |
| ev_upravljalec_dst_h | GURS ORCL | False | EV.JN_UPRAVLJAVEC_DST, EV.REVISION |
| ev_upravljalec_parc_h | GURS ORCL | False | EV.JN_UPRAVLJAVEC_PARC, EV.REVISION |
| prs | GURS ORCL | True | NEP_ETL.PRS$ENOTE@PRIPIS_PROXY_KN |
| ev_del_stavbe_enota_h_2025_danes | KN ORACLE | False | EV.JN_DEL_STAVBE_ENOTA, EV.REVISION |
| ev_del_stavbe_h | KN ORACLE | False | EV.JN_DEL_STAVBE, EV.REVISION |
| ev_dst_pripis_podatki_h | KN ORACLE | False | EV.DST_PRIPIS_PODATKI, EV.REVISION |
| ev_parc_del_h | KN ORACLE | False | EV.JN_PARC_DEL, EV.REVISION |
| ev_parcela_h | KN ORACLE | False | EV.JN_PARCELA, EV.REVISION |
| ev_parc_enota_h_2025_danes | KN ORACLE | False | EV.JN_PARC_ENOTA, EV.REVISION |
| ev_parc_pripis_podatki_h | KN ORACLE | False | EV.PARC_PRIPIS_PODATKI, EV.REVISION |
| ev_pe_dst_h | KN ORACLE | False | EV.JN_PE_DST, EV.REVISION |
| ev_pe_parc_h | KN ORACLE | False | EV.JN_PE_PARC, EV.REVISION |
| ev_posebna_enota | KN ORACLE | True | EV.POSEBNA_ENOTA |
| ev_posebna_enota_h | KN ORACLE | False | EV.JN_POSEBNA_ENOTA, EV.REVISION |
| ev_prostor_h | KN ORACLE | False | EV.JN_PROSTOR, EV.REVISION |
| ev_stavba_h | KN ORACLE | False | EV.JN_STAVBA, EV.REVISION |
| gji_ceste_l | KN ORACLE | True | GJI.LINIJE, SIF.GJI_ATR1, SIF.GJI_VRSTE_OBJEKTOV |
| gji_daljnovodi_l | KN ORACLE | True | GJI.LINIJE, SIF.GJI_ATR2, SIF.GJI_VRSTE_OBJEKTOV |
| gji_zeleznice_l | KN ORACLE | True | GJI.LINIJE, SIF.GJI_VRSTE_OBJEKTOV |
| kn_nep_deli_stavb_h | KN ORACLE | False | NEP.DELI_STAVB_H |
| kn_nep_etaze_h | KN ORACLE | False | NEP.ETAZE_H |
| kn_nep_etaze_x_deli_stavb_h | KN ORACLE | False | NEP.ETAZE_X_DELI_STAVB_H |
| kn_nep_hisne_stevilke_h | KN ORACLE | False | NEP.HISNE_STEVILKE_H |
| kn_nep_katastrske_obcine_h | KN ORACLE | False | NEP.KATASTRSKE_OBCINE_H |
| kn_nep_ostalo_dejanske_rabe_parcel_h | KN ORACLE | False | NEP_OSTALO.DEJANSKE_RABE_H |
| kn_nep_ostalo_gozdno_gosp_obm | KN ORACLE | False | NEP_OSTALO.GOZDNO_GOSP_OBM |
| kn_nep_ostalo_namenske_rabe | KN ORACLE | False | NEP_OSTALO.NAMENSKE_RABE |
| kn_nep_ostalo_parcele_x_dejanske_rabe_h | KN ORACLE | False | NEP_OSTALO.PARCELE_X_DEJANSKE_RABE_H |
| kn_nep_ostalo_parcele_x_gozdno_gosp_obm_h | KN ORACLE | False | NEP_OSTALO.PARCELE_X_GOZDNO_GOSP_OBM_H |
| kn_nep_ostalo_parcele_x_namenske_rabe_h | KN ORACLE | False | NEP_OSTALO.PARCELE_X_NAMENSKE_RABE_H |
| kn_nep_parcele_h | KN ORACLE | False | NEP.PARCELE_H |
| kn_nep_prostori_h | KN ORACLE | False | NEP.PROSTORI_H |
| kn_nep_rpe_naselja_h | KN ORACLE | False | NEP.RPE_NASELJA_H |
| kn_nep_rpe_obcine_h | KN ORACLE | False | NEP.RPE_OBCINE_H |
| kn_nep_rpe_ulice_h | KN ORACLE | False | NEP.RPE_ULICE_H |
| kn_nep_sestavine_delov_stavb_h | KN ORACLE | True | NEP.SESTAVINE_DELOV_STAVB_H |
| kn_nep_sifranti | KN ORACLE | True | .DUAL, SIF.DA_NE, SIF.DRZAVE, SIF.GJI, SIF.GJI_AKTIVNOSTI_VODOV, SIF.GJI_ATR1, SIF.GJI_ATR2, SIF.GJI_ATR3, SIF.GJI_ATR4, SIF.GJI_TEMATIKE, SIF.GJI_VIRI, SIF.METADATA_SIFRANTI, SIF.NACINI_DOLOCITVE_POVRSIN_DELA_STAVBE, SIF.NOSILNE_KONSTRUKCIJE, SIF.PODROBNE_NAMENSKE_RABE, SIF.POD_NAM_RABE, SIF.TIPI_LASTNIKOV, SIF.TIPI_LASTNISTVA, SIF.TIPI_NEPREMICNIN, SIF.TIPI_POSLOVNIH_ENOT, SIF.TIPI_STAVB, SIF.UPRAVNI_STATUSI, SIF.VIRI_DEJANSKIH_RAB, SIF.VIRI_NAMENSKE_RABE, SIF.VIRI_POSEBNIH_REZIMOV, SIF.VRSTE_DEJANSKE_RABE, SIF.VRSTE_DEJANSKIH_RAB_DEL_ST, SIF.VRSTE_DRABA, SIF.VRSTE_GRADBENIH_PARCEL, SIF.VRSTE_LASTNIKOV, SIF.VRSTE_NAMENSKE_RABE, SIF.VRSTE_PLOMB, SIF.VRSTE_PODROBNE_DEJANSKE_RABE, SIF.VRSTE_POSTOPKOV_RPE, SIF.VRSTE_SESTAVIN_DELOV_STAVB, SIF.VRSTE_STANOVANJ, SIF.VRSTE_STAVBA_PARCELA, SIF.VRSTE_STREH, SIF.VRSTE_UPRAVLJAVCEV |
| kn_nep_stanovanja_h | KN ORACLE | False | NEP.STANOVANJA_H |
| kn_nep_stavbe_centroidi_h | KN ORACLE | False | NEP.STAVBE_H |
| kn_nep_stavbe_obrisi_h | KN ORACLE | False | NEP.STAVBE_H |
| kn_nep_stavbe_parcele_h | KN ORACLE | False | NEP.STAVBE_PARCELE_H |
| kn_nep_stavbe_zps_h | KN ORACLE | False | NEP.STAVBE_H |
| test_primoz1234 | KN ORACLE | True | NEP.DRZAVE |

# Export-plan blockers

```json
{
  "No accessible metadata through KN credentials": 16,
  "ready for probe": 143,
  "Saved query fails on current KN: ORA-00942": 16,
  "Need exactly one configured matching key and change field for this prototype": 19,
  "Saved query fails on current KN: ORA-02019": 1
}
```
