-- SQL*Plus script. Change target_owner/output_file if required, then run:
--   sqlplus user/password@database @export_schema_info.sql
-- Produces schema_info.csv for every table listed in EV_INTEG/spec.md.

define target_owner = EV
define output_file = schema_info.csv

set markup csv on delimiter , quote on
set feedback off
set heading on
set pagesize 50000
set linesize 32767
spool &&output_file

with
target_tables (table_name) as (
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
),
base as (
    select upper('&&target_owner') owner, table_name from target_tables
)
select section, table_name, object_name, position, column_name, definition,
       constraint_type, referenced_table, referenced_column,
       property_1, property_2, property_3, notes
from (
    select '01_OBJECT' section, b.table_name, cast(null as varchar2(128)) object_name,
           cast(null as number) position, cast(null as varchar2(128)) column_name,
           cast(null as varchar2(4000)) definition, cast(null as varchar2(30)) constraint_type,
           cast(null as varchar2(128)) referenced_table, cast(null as varchar2(128)) referenced_column,
           coalesce(o.object_type, 'OBJECT NOT FOUND') property_1, o.status property_2,
           to_char(o.last_ddl_time, 'YYYY-MM-DD HH24:MI:SS') property_3,
           cast(null as varchar2(4000)) notes
      from base b
      left join all_objects o on o.owner = b.owner and o.object_name = b.table_name
                            and o.object_type = 'TABLE'
    union all
    select '02_TABLE', b.table_name, null, null, null, null, null, null, null,
           to_char(t.num_rows), to_char(t.avg_row_len),
           to_char(t.last_analyzed, 'YYYY-MM-DD HH24:MI:SS'), null
      from base b join all_tables t on t.owner = b.owner and t.table_name = b.table_name
    union all
    select '03_COLUMN', c.table_name, null, c.column_id, c.column_name,
           case when c.data_type in ('VARCHAR2', 'CHAR', 'NVARCHAR2', 'NCHAR')
                then c.data_type || '(' || c.char_length || case when c.char_used = 'C' then ' CHAR)' else ' BYTE)' end
                when c.data_type = 'NUMBER' and c.data_precision is not null
                then 'NUMBER(' || c.data_precision || case when c.data_scale is not null then ',' || c.data_scale end || ')'
                else c.data_type end,
           null, null, null, c.nullable, to_char(c.data_length),
           case when c.data_default is not null then 'DEFAULT EXISTS' end, cc.comments
      from all_tab_columns c
      join base b on b.owner = c.owner and b.table_name = c.table_name
      left join all_col_comments cc on cc.owner = c.owner and cc.table_name = c.table_name and cc.column_name = c.column_name
    union all
    select '04_CONSTRAINT', ac.table_name, ac.constraint_name, acc.position, acc.column_name,
           ac.constraint_type, ac.constraint_type, ar.table_name, arc.column_name,
           ac.status, ac.validated, null,
           'DEFERRABLE=' || ac.deferrable || '; DEFERRED=' || ac.deferred
      from all_constraints ac
      join base b on b.owner = ac.owner and b.table_name = ac.table_name
      left join all_cons_columns acc on acc.owner = ac.owner and acc.constraint_name = ac.constraint_name
      left join all_constraints ar on ar.owner = ac.r_owner and ar.constraint_name = ac.r_constraint_name
      left join all_cons_columns arc on arc.owner = ar.owner and arc.constraint_name = ar.constraint_name and arc.position = acc.position
    union all
    select '05_INDEX', ai.table_name, ai.index_name, aic.column_position, aic.column_name,
           aic.column_name, null, null, null, ai.uniqueness, ai.index_type, aic.descend,
           'STATUS=' || ai.status || '; PARTITIONED=' || ai.partitioned || '; COMPRESSION=' || ai.compression
      from all_indexes ai
      join base b on b.owner = ai.table_owner and b.table_name = ai.table_name
      join all_ind_columns aic on aic.index_owner = ai.owner and aic.index_name = ai.index_name
    union all
    select '06_LOB', l.table_name, l.segment_name, null, l.column_name, l.segment_name,
           null, null, null, l.securefile, l.in_row, l.cache,
           'TABLESPACE=' || l.tablespace_name
      from all_lobs l
      join base b on b.owner = l.owner and b.table_name = l.table_name
)
order by table_name, section, object_name, position;

spool off
