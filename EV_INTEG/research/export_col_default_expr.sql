-- Run in PyCharm while connected as the EV schema, then export the result grid
-- as col_default_expr.csv.

with target_tables (table_name) as (
    select 'DST_PRIPIS_PODATKI' from dual union all select 'JN_DEL_STAVBE' from dual union all
    select 'JN_DEL_STAVB_ENOTA' from dual union all select 'JN_PARC_DEL' from dual union all
    select 'JN_PARC_ENOTA' from dual union all select 'JN_PARCELA' from dual union all
    select 'JN_PE_DST' from dual union all select 'JN_PE_PARC' from dual union all
    select 'JN_POSEBNA_ENOTA' from dual union all select 'JN_PROSTOR' from dual union all
    select 'JN_STAVBA' from dual union all select 'PARC_PRIPIS_PODATKI' from dual
)
select c.table_name, c.column_id, c.column_name, c.data_default
from user_tab_columns c
join target_tables tt on tt.table_name = c.table_name
where c.data_default is not null
order by c.table_name, c.column_id;
