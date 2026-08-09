
Requirements for each table:

- change pretty name so it starts with EV H
- change integ source to KN (not GURS) / make integ / fix up integ so it has JN_STATUS (and other possible problems violating the spec)
- have no diff compared to running the SQL on KN (we just do the PK and DATE_CHANGED diff and count diff) (first do count diff, then do the data diff in pages - as soon as we fail, we stop. We have a data_correct.json where we remember: count on KN table, last_check_passed. If we already have the count on KN table, we don't count again but just use that value. If last check passed, we dont check anything more.)
- have last_changed_datetime on the integration equal our high-water mark on DATE_CHANGED
- in the end, we run the integration in LIFT and no records should be transfered

Notes:

we get data about the tables and integrations by:
fmp database, attribute_tables where name is (snakecase name)
And attribute_table_integrations where attribute_table_id is that id
And for check of using KN we get attribute_table_sql_connection_id on attribute_table_integrations, and we join it with attribute_table_sql_connections where we check that name is KN ORACLE.

For ev_del_stavbe_enota_h and ev_parc_enota_h we actually have checks on:
ev_parc_enota_h_2025_danes
and ev_del_stavbe_enota_h_2025_danes
Where we have the integration only get the data with:
WHERE rf.created >= TIMESTAMP '2025-01-01 00:00:00'



Process:

We first check this on staging.
Then we apply the changes on prod and transfer data there.
And then we also check the diff and last_changed_datetime on prod.

We need to perform all of these checks on all tables (we define the stag/prod table name and the KN table name pairs in some file).
We get a nice .md table report for the state of things.

.env has data for stag, prod, kn.
We need 2 modes - check with stag and check with prod. Stag is the default.
Also, we should be able to pass which tables we want to check right now and we get a report for just those.

