# EV integration state check (staging)

| Table | Metadata | Data | High-water | Zero newer rows | Result |
|---|---|---|---|---|---|
| ev_dst_pripis_podatki_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_del_stavbe_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_del_stavbe_enota_h_2025_danes | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_parc_del_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_parc_enota_h_2025_danes | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_parcela_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_pe_dst_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_pe_parc_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_posebna_enota_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_prostor_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_stavba_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |
| ev_parc_pripis_podatki_h | FAIL | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | **FAIL** |

## Details

### ev_dst_pripis_podatki_h

- object of type 'UUID' has no len()
### ev_del_stavbe_h

- object of type 'UUID' has no len()
### ev_del_stavbe_enota_h_2025_danes

- object of type 'UUID' has no len()
### ev_parc_del_h

- object of type 'UUID' has no len()
### ev_parc_enota_h_2025_danes

- object of type 'UUID' has no len()
### ev_parcela_h

- object of type 'UUID' has no len()
### ev_pe_dst_h

- object of type 'UUID' has no len()
### ev_pe_parc_h

- object of type 'UUID' has no len()
### ev_posebna_enota_h

- object of type 'UUID' has no len()
### ev_prostor_h

- object of type 'UUID' has no len()
### ev_stavba_h

- object of type 'UUID' has no len()
### ev_parc_pripis_podatki_h

- object of type 'UUID' has no len()

A passing `Zero newer rows` result is the precondition for manually running LIFT; that LIFT run should transfer zero records.
