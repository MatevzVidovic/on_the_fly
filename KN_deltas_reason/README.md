# KN delta drift investigation

General problem description and supplied evidence remain here:

- [Jira problem description](jira.md)
- [Original task prompt](task_prompt.md)
- [Initial thinking and integration-discovery SQL](initial_thinking.md)
- [Supplied integration query and field evidence](source_query_evidence.md)

The source-only backdating experiment, including its code, SQLs, design notes,
exports and SQLite observations, is in [backdated_test_attempt/](backdated_test_attempt/README.md).
The existing `.venv/` remains here to preserve its installed paths. The experiment's
`.env` moved with the experiment. The older `old_KN_deltas_reason/` directory is unchanged.

The new one-table source/target comparison is in [reconciliation/](reconciliation/README.md).
It is separate from the archived source-only experiment; complete its preflight before exporting.
