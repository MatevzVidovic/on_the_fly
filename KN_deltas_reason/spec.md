



We first need to identify the tables that are connecting themselves to KN.
We will make a list of them.

Then we will choose a subset of them to test the deltas on.

We will do the matching on:  PK composite columns / DATE_CHANGED
We will identify what rows are the deltas. Then if the 2 delta sets (extra in each direction) are not too big, we will also download them locally so we know everything about them and can identify the reasons.








This is from another task but might help with discovery:

The metadata tables are in fmp db on the db.


we get data about the tables and integrations by:
fmp database, attribute_tables where name is (snakecase name)
And attribute_table_integrations where attribute_table_id is that id
And for check of using KN we get attribute_table_sql_connection_id on attribute_table_integrations, and we join it with attribute_table_sql_connections where we check that name is KN ORACLE.

You can also get the sql of the integrations for some field.

I will give you TEST_ creds on the so you work with that, but later I will be running the things on STAG_