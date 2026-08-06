-- Run in PyCharm with the same connection used for the original export, then
-- export the result grid as schema_info.csv. The EV objects are accessed via
-- ALL_* dictionary views; the connection itself does not have to be EV.

with target_tables (table_name) as (
    select 'DST_PRIPIS_PODATKI' from dual union all select 'JN_DEL_STAVBE' from dual union all
    select 'JN_DEL_STAVB_ENOTA' from dual union all select 'JN_PARC_DEL' from dual union all
    select 'JN_PARC_ENOTA' from dual union all select 'JN_PARCELA' from dual union all
    select 'JN_PE_DST' from dual union all select 'JN_PE_PARC' from dual union all
    select 'JN_POSEBNA_ENOTA' from dual union all select 'JN_PROSTOR' from dual union all
    select 'JN_STAVBA' from dual union all select 'PARC_PRIPIS_PODATKI' from dual
)
select section, table_name, object_name, position, column_name, definition,
       constraint_type, referenced_table, referenced_column,
       property_1, property_2, property_3, notes
from (
    select '01_OBJECT' section, tt.table_name, cast(null as varchar2(128)) object_name,
           cast(null as number) position, cast(null as varchar2(128)) column_name,
           cast(null as varchar2(4000)) definition, cast(null as varchar2(30)) constraint_type,
           cast(null as varchar2(128)) referenced_table, cast(null as varchar2(128)) referenced_column,
           coalesce(o.object_type, 'OBJECT NOT FOUND') property_1, o.status property_2,
           to_char(o.last_ddl_time, 'YYYY-MM-DD HH24:MI:SS') property_3, cast(null as varchar2(4000)) notes
      from target_tables tt
      left join all_objects o on o.owner = 'EV' and o.object_name = tt.table_name
                             and o.object_type in ('TABLE', 'VIEW', 'MATERIALIZED VIEW')
    union all
    select '02_TABLE', t.table_name, null, null, null, null, null, null, null,
           to_char(t.num_rows), to_char(t.avg_row_len), to_char(t.last_analyzed, 'YYYY-MM-DD HH24:MI:SS'), null
      from all_tables t join target_tables tt on tt.table_name = t.table_name
     where t.owner = 'EV'
    union all
    select '03_COLUMN', c.table_name, null, c.column_id, c.column_name,
           case when c.data_type in ('VARCHAR2', 'CHAR', 'NVARCHAR2', 'NCHAR')
                then c.data_type || '(' || c.char_length || case when c.char_used = 'C' then ' CHAR)' else ' BYTE)' end
                when c.data_type = 'NUMBER' and c.data_precision is not null
                then 'NUMBER(' || c.data_precision || case when c.data_scale is not null then ',' || c.data_scale end || ')'
                else c.data_type end,
           null, null, null, c.nullable, to_char(c.data_length),
           case when c.default_length is not null then 'DEFAULT EXISTS; LENGTH=' || c.default_length end, cc.comments
      from all_tab_columns c
      join target_tables tt on tt.table_name = c.table_name
      left join all_col_comments cc on cc.owner = c.owner and cc.table_name = c.table_name and cc.column_name = c.column_name
     where c.owner = 'EV'
    union all
    select '04_CONSTRAINT', ac.table_name, ac.constraint_name, acc.position, acc.column_name,
           ac.constraint_type, ac.constraint_type, rc.table_name, rcc.column_name,
           ac.status, ac.validated, null, 'DEFERRABLE=' || ac.deferrable || '; DEFERRED=' || ac.deferred
      from all_constraints ac
      join target_tables tt on tt.table_name = ac.table_name
      left join all_cons_columns acc on acc.owner = ac.owner and acc.constraint_name = ac.constraint_name and acc.table_name = ac.table_name
      left join all_constraints rc on rc.owner = ac.r_owner and rc.constraint_name = ac.r_constraint_name
      left join all_cons_columns rcc on rcc.owner = rc.owner and rcc.constraint_name = rc.constraint_name
                                  and rcc.table_name = rc.table_name and rcc.position = acc.position
     where ac.owner = 'EV'
    union all
    select '05_INDEX', i.table_name, i.index_name, ic.column_position, ic.column_name,
           ic.column_name, null, null, null, i.uniqueness, i.index_type, ic.descend,
           'STATUS=' || i.status || '; PARTITIONED=' || i.partitioned || '; COMPRESSION=' || i.compression
      from all_indexes i
      join target_tables tt on tt.table_name = i.table_name
      join all_ind_columns ic on ic.index_owner = i.owner and ic.index_name = i.index_name
                              and ic.table_owner = i.table_owner and ic.table_name = i.table_name
     where i.table_owner = 'EV'
    union all
    select '06_LOB', l.table_name, l.segment_name, null, l.column_name, l.segment_name,
           null, null, null, l.securefile, l.in_row, l.cache, 'TABLESPACE=' || l.tablespace_name
      from all_lobs l join target_tables tt on tt.table_name = l.table_name
     where l.owner = 'EV'
)
order by table_name, section, object_name, position;
