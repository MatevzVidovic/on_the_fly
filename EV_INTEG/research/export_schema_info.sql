-- Run in PyCharm while connected as the EV schema, then export the result grid
-- as schema_info.csv. This query covers every source table listed in spec.md.

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
      left join user_objects o on o.object_name = tt.table_name and o.object_type = 'TABLE'
    union all
    select '02_TABLE', t.table_name, null, null, null, null, null, null, null,
           to_char(t.num_rows), to_char(t.avg_row_len), to_char(t.last_analyzed, 'YYYY-MM-DD HH24:MI:SS'), null
      from user_tables t join target_tables tt on tt.table_name = t.table_name
    union all
    select '03_COLUMN', c.table_name, null, c.column_id, c.column_name,
           case when c.data_type in ('VARCHAR2', 'CHAR', 'NVARCHAR2', 'NCHAR')
                then c.data_type || '(' || c.char_length || case when c.char_used = 'C' then ' CHAR)' else ' BYTE)' end
                when c.data_type = 'NUMBER' and c.data_precision is not null
                then 'NUMBER(' || c.data_precision || case when c.data_scale is not null then ',' || c.data_scale end || ')'
                else c.data_type end,
           null, null, null, c.nullable, to_char(c.data_length),
           case when c.data_default is not null then 'DEFAULT EXISTS' end, cc.comments
      from user_tab_columns c
      join target_tables tt on tt.table_name = c.table_name
      left join user_col_comments cc on cc.table_name = c.table_name and cc.column_name = c.column_name
    union all
    select '04_CONSTRAINT', ac.table_name, ac.constraint_name, acc.position, acc.column_name,
           ac.constraint_type, ac.constraint_type, rc.table_name, rcc.column_name,
           ac.status, ac.validated, null, 'DEFERRABLE=' || ac.deferrable || '; DEFERRED=' || ac.deferred
      from user_constraints ac
      join target_tables tt on tt.table_name = ac.table_name
      left join user_cons_columns acc on acc.constraint_name = ac.constraint_name
      left join user_constraints rc on rc.constraint_name = ac.r_constraint_name
      left join user_cons_columns rcc on rcc.constraint_name = rc.constraint_name and rcc.position = acc.position
    union all
    select '05_INDEX', i.table_name, i.index_name, ic.column_position, ic.column_name,
           ic.column_name, null, null, null, i.uniqueness, i.index_type, ic.descend,
           'STATUS=' || i.status || '; PARTITIONED=' || i.partitioned || '; COMPRESSION=' || i.compression
      from user_indexes i
      join target_tables tt on tt.table_name = i.table_name
      join user_ind_columns ic on ic.index_name = i.index_name
    union all
    select '06_LOB', l.table_name, l.segment_name, null, l.column_name, l.segment_name,
           null, null, null, l.securefile, l.in_row, l.cache, 'TABLESPACE=' || l.tablespace_name
      from user_lobs l join target_tables tt on tt.table_name = l.table_name
)
order by table_name, section, object_name, position;
