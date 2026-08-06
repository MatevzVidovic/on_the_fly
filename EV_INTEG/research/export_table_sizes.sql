-- Run in PyCharm with access to the EV schema, then export the result grid as
-- table_sizes.csv. Uses Oracle table statistics only: it does not scan table data.
-- ESTIMATED_DATA_* excludes indexes and separately stored LOB data.

with wanted_tables (table_name) as (
    select 'DST_PRIPIS_PODATKI' from dual union all
    select 'JN_DEL_STAVBE' from dual union all
    select 'JN_DEL_STAVB_ENOTA' from dual union all
    select 'JN_PARC_DEL' from dual union all
    select 'JN_PARC_ENOTA' from dual union all
    select 'JN_PARCELA' from dual union all
    select 'JN_PE_DST' from dual union all
    select 'JN_PE_PARC' from dual union all
    select 'JN_POSEBNA_ENOTA' from dual union all
    select 'JN_PROSTOR' from dual union all
    select 'JN_STAVBA' from dual union all
    select 'PARC_PRIPIS_PODATKI' from dual
)
select
    'EV' as owner,
    w.table_name,
    t.num_rows,
    t.avg_row_len,
    round(t.num_rows * t.avg_row_len / power(1024, 2), 2) as estimated_data_mb,
    round(t.num_rows * t.avg_row_len / power(1024, 3), 3) as estimated_data_gb,
    t.last_analyzed,
    case
        when t.table_name is null then 'TABLE NOT FOUND IN ALL_TABLES FOR OWNER EV'
        when t.num_rows is null or t.avg_row_len is null then 'TABLE STATISTICS NOT AVAILABLE'
    end as notes
from wanted_tables w
left join all_tables t
    on t.owner = 'EV'
   and t.table_name = w.table_name
order by
    t.num_rows * t.avg_row_len desc nulls last,
    w.table_name;
