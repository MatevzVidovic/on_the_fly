# Repair only missing and outdated records

Repair compares each source page directly with LIFT and stores only planned inserts and updates. Full inventory storage and row-removal work are outside this tool's scope, keeping preparation small and the code local; any future cleanup belongs in a separate solution. Scoped counts and the signed `expected_needed_deletions` metric provide visibility without identifying or changing surplus records. The simpler two-table SQLite format starts fresh rather than carrying the old schema forward.
