# KN delta drift investigation — task prompt

This is the original broad request. The accepted first implementation is narrower:
one Oracle-only dataset, manual snapshots of matching key and `DATUM_SYS`, a
configurable lower date bound with no end bound, and a fixed baseline comparison.
Creation-date filters, target UUIDs, target comparisons and EV grouping are deferred.
See [design_session.md](design_session.md) and [README.md](README.md).

We are pivoting from the EV import work to investigating KN delta synchronization.

The primary focus is the KN tables. Also include the EV tables we just imported, but keep them in a separate group so their counts, exports and findings do not get mixed with the primary KN investigation.

We need counts, UUID `id` exports, integration matching-key exports, and last-changed column exports so we can diagnose drift over time.

Limit the records under investigation to a fixed time frame, preferably using a static column such as the source record's creation date. Identify which column is actually immutable and available for each integration before using it. Repeat observations of the same scope over time.

Use the integration SQL saved in our own database as the source query. We want to test the exact dataset our integration reads, including its joins, filters and derived fields. Only consider SQL delta integrations using the `KN ORACLE` connection.

Keep everything as simple as possible. Consider a small export script that streams results into a local SQLite file, or DuckDB if there is a concrete reason to use it. No elaborate framework is needed.

Our hypothesis is that GURS adds records on date X while assigning a `zad_spr` value earlier than X. If that value is already behind the integration watermark, ordinary delta synchronization may never pick up those records. Treat this as a hypothesis to test, not an established cause.

Start by discovering the integrations and their saved SQL, identifying the actual matching key, static cohort field and delta field for each, then designing the smallest repeatable export that can distinguish missing records, changed records and late-appearing records with old change timestamps.
