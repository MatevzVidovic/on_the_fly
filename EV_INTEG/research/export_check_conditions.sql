-- SQL*Plus script. Exports check conditions for all required EV tables.

define target_owner = EV
define output_file = check_conditions.csv

set markup csv on delimiter , quote on
set feedback off
set heading on
set pagesize 50000
set linesize 32767
spool &&output_file

with target_tables (table_name) as (
    select 'DST_PRIPIS_PODATKI' from dual union all select 'JN_DEL_STAVBE' from dual union all
    select 'JN_DEL_STAVB_ENOTA' from dual union all select 'JN_PARC_DEL' from dual union all
    select 'JN_PARC_ENOTA' from dual union all select 'JN_PARCELA' from dual union all
    select 'JN_PE_DST' from dual union all select 'JN_PE_PARC' from dual union all
    select 'JN_POSEBNA_ENOTA' from dual union all select 'JN_PROSTOR' from dual union all
    select 'JN_STAVBA' from dual union all select 'PARC_PRIPIS_PODATKI' from dual
)
select ac.table_name, ac.constraint_name, ac.status, ac.validated, ac.search_condition_vc as search_condition
from all_constraints ac
join target_tables tt on tt.table_name = ac.table_name
where ac.owner = upper('&&target_owner')
  and ac.constraint_type = 'C'
order by ac.table_name, ac.constraint_name;

spool off
