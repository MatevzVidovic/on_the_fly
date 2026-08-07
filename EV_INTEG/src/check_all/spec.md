

Requirements for each table:

- change pretty name so it starts with EV H
- change integ source to KN (not GURS) / make integ / fix up integ so it has JN_STATUS (and other possible problems violating the spec)
- have no diff compared to running the SQL on KN (we just do the PK and DATE_CHANGED diff and count diff) (first do count diff, then do the data diff in pages - as soon as we fail, we stop. We have a data_correct.json where we remember: count on KN table, last_check_passed. If we already have the count on KN table, we don't count again but just use that value. If last check passed, we dont check anything more.)
- have last_changed_datetime on the integration equal our high-water mark on DATE_CHANGED

We first check this on staging.
Then we apply the changes on prod and transfer data there.
And then we also check the diff and last_changed_datetime on prod.

We need to perform all of these checks on all tables (we define the stag/prod table name and the KN table name pairs in some file).
We get a nice .md table report for the state of things.

.env has data for stag, prod, kn.
We need 2 modes - check with stag and check with prod. Stag is the default.
Also, we should be able to pass which tables we want to check right now and we get a report for just those.

