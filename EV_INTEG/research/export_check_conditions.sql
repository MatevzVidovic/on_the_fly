-- Run in PyCharm while connected as the EV schema, then export the result grid
-- as check_conditions.csv.

with target_tables (table_name) as (
    select 'DST_PRIPIS_PODATKI' from dual union all select 'JN_DEL_STAVBE' from dual union all
    select 'JN_DEL_STAVB_ENOTA' from dual union all select 'JN_PARC_DEL' from dual union all
    select 'JN_PARC_ENOTA' from dual union all select 'JN_PARCELA' from dual union all
    select 'JN_PE_DST' from dual union all select 'JN_PE_PARC' from dual union all
    select 'JN_POSEBNA_ENOTA' from dual union all select 'JN_PROSTOR' from dual union all
    select 'JN_STAVBA' from dual union all select 'PARC_PRIPIS_PODATKI' from dual
)
select ac.table_name, ac.constraint_name, ac.status, ac.validated, ac.search_condition_vc as search_condition
from user_constraints ac
join target_tables tt on tt.table_name = ac.table_name
where ac.constraint_type = 'C'
order by ac.table_name, ac.constraint_name;
