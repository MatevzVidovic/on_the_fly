



We first need to identify the tables that are connecting themselves to KN.
We will make a list of them.

Then we will choose a subset of them to test the deltas on.

We will do the matching on:  PK composite columns / DATE_CHANGED
We will identify what rows are the deltas. Then if the 2 delta sets (extra in each direction) are not too big, we will also download them locally so we know everything about them and can identify the reasons.


look at EV_INTEG to see how kn connection works and other conections work and all that


We have to perform the checks with the integration sql select
BUT
We need to do comparisons with sth like DATE_CHANGED < some_timestamp_we_choose
Because the data can be changing all the time on KN and we need a stable delta check.

Also, when we get the deltas and export them and such, we should have that export have a datetime attached to it, so we know both when we ran that and what we chose as that condition for the where.

Also, we should have a --limit flag for how many of the deltas we actually take as examples. By default it should be 20.








This is from another task but might help with discovery:

The metadata tables are in fmp db on the db.


we get data about the tables and integrations by:
fmp database, attribute_tables where name is (snakecase name)
And attribute_table_integrations where attribute_table_id is that id
And for check of using KN we get attribute_table_sql_connection_id on attribute_table_integrations, and we join it with attribute_table_sql_connections where we check that name is KN ORACLE.

You can also get the sql of the integrations for some field.

I will give you TEST_ creds on the so you work with that, but later I will be running the things on STAG_