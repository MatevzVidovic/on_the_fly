# Teaching notes

- User asks to learn slowly, starting with tables and the work required.
- Previous roles visual and ten-question quiz are available, but no quiz responses have been supplied. Do not assume understanding from exposure.
- Lesson 0001 teaches existing date → model selection → calculated unit value relationships only.
- Lesson 0002 clarifies property snapshots. Next, after learner feedback, introduce EV dated inputs and a new final-comparison row.
- Mission clarification asked: implement, review/plan, or explain. Working mission remains provisional.
- Learning record 0001 captures recognition of the model/date chain. Transaction vs property-snapshot misconception is pending retrieval feedback.

- User explicitly requests ongoing DB verification. test_njihov_access was reachable on 2026-10-14; test_nas_access timed out. Use read-only, bounded queries with statement timeouts and rollback, never display .env credentials.

- Lesson 0003 answers the learner’s question about the ISAM result and EV versions. Current EV rows have id_model_ver; sampled STZ=1164 versus ISAM configured STZ version 44. No authoritative EV→ISAM version correspondence found. Do not present those numbers as equivalent. Some sampled ZPS versions are NULL; building-part history lacks the field.

- 2026-10-15: user requests more depth on solution contents. Lesson 0004 covers saved final/detail/rule records, conditional explanation, workflow and Lift, with interactive scenarios and a printable delivery reference. Resume from their explanation of those three record types, not a new broad quiz.
- New read-only DB check confirms integer vrednost_izr. No public tables matched pripis%primerjav%; do not interpret a name search as proof that no differently named comparison exists.

- User now wants runnable development milestones. development-roadmap.md sequences decimal storage; building-part dated/version-compatible source proof; final comparison; persistence/Lift/SFC; intermediate extraction/translation/drill-down; parcel totals then semantic details; final coverage checks. No implementation or migrations executed.
