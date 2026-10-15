# 5757: small, runnable development steps

The main split is **decimal storage → building parts → parcels**. Within each property type, deliver **final-value comparison before intermediate explanation**.

Here “building parts” means **deli stavb**, matched by `del_stavbe_id = dst_sid`, not whole buildings. The sequence below is a proposed implementation plan based on [5757.md](5757.md). It is not implemented code or a list of commands that already exist.

## A. Fix decimal storage

### 1. Preserve the calculated value end to end

**Build:** a migration changing `pripis_vmxpd_x_enote.vrednost_izr` to an agreed numeric precision, and the corresponding Lift Decimal Number metadata change. The task suggests `numeric(20,2)`. Check the writer and reader preserve decimals too.

**Run:** apply in the development/test environment and calculate a controlled example with a fractional result. Read it back through SQL and Lift.

**Done when:** the same fractional value survives calculation, persistence and display. Identify affected old rows that need recalculation/recovery: changing the column type does not recover lost decimals.

**Why separate:** every later comparison depends on valid inputs. No comparison UI or translator is needed to finish this step.

## B. Building parts: final values first

### 2. Prove one property is actually comparable — read-only

**Build:** a small source-inspection query/script scoped to one cutoff date, one model and one building-part ID. Return ISAM and EV source references, values, errors, date evidence and version evidence. Preserve whichever side exists even if the other is missing.

**Run:** inspect one real property manually. Trace its ISAM date/model selection and prepared-unit/result links, then find the correct EV dated value.

**Done when:** you can explain why these records represent the same property, date and corresponding valuation rules. If that is not provable, return an explicit diagnostic rather than a fabricated match.

**Known decisions:** current EV values have `id_model_ver`; inspected building-part history lacks it. EV→ISAM version correspondence and historical selection are not established. Small ISAM samples also failed to resolve their referenced model record. Investigate those references before relying on them.

**Important:** numeric storage work can proceed independently, but real comparison correctness cannot bypass this evidence gate. Synthetic examples can still exercise later comparison logic while source questions are being resolved.

### 3. Compare one building part in memory/query output

**Build:** the final-value SQL calculation for the validated scope. Return both calculated values and delta, both generalized values and delta, and separate statuses. Delta is always ISAM − EV. Retain missing records and source calculation errors; do not turn NULL into zero.

**Run:** print the result without creating persistent comparison tables yet. Check controlled cases: equal; calculated difference; generalized-only difference; missing on either side; calculation failure on either side. Verify duplicate keys produce a diagnostic rather than multiplying rows.

**Done when:** each case has the expected values and independent outcomes. Agree how final equality statuses use tolerance; the ticket explicitly defines tolerance for intermediate eligibility, but does not completely settle its role in final statuses.

### 4. Save that result and show it in Lift

**Build:** the final-comparison table and Lift view. Reuse the same comparison logic from step 3. Introduce a small run identity/state mechanism so results from different attempts do not mix. Exact table names/layout are proposals.

**Run:** explicitly execute the workflow/script for that small scope, save its result, and inspect it in Lift. Rerun the same scope and simulate a failed attempt.

**Done when:** results are linked to their scope/run, retries do not duplicate or mix rows, and incomplete work is visibly incomplete. Filters work for property ID, model, both deltas and statuses.

### 5. Run a useful building-part batch from the date row

**Build:** scope expansion from one property to one model/date batch, with the same logic. Add the SFC start action and workflow progress/failure reporting. Use indexed, date-filtered SQL, bulk writes and paginated result reads.

**Run:** launch a representative bounded batch from Lift, inspect saved results and query plans, and check missing rows and counts against the input scope.

**Done when:** a user can start a building-part final comparison and inspect its results. Required source/version coverage is explicit; unsupported scopes are not silently reported as equal.

**First useful delivery:** building-part final values are now usable, even though intermediate explanation and parcels remain unfinished. The UI should say that detail explanation is not yet available.

## C. Building parts: explain calculated differences

### 6. Decode ISAM ingredients for one eligible result

**Build:** extraction of `spremenljivke_vrednosti` and `faktorji_vrednosti` using the correct model-version key lists. Validate list lengths, NULLs, serialization and referenced model context. Do not simply split arbitrary text on commas or borrow another version’s keys.

**Run:** output named ingredients for one result with valid calculated values on both sides and `abs(delta_izr) > tolerance`.

**Done when:** you can trace each ingredient to its original stored value and correct key. If the old representation cannot be decoded reliably, repair/recalculate it or preserve a keyed snapshot during calculation before proceeding.

### 7. Translate one EV ingredient, then the supported model

**Build:** the common ingredient record format, a simple mapping table and the first approved mapping. Start with a field whose meaning can be proven; `f_bon` is a candidate for KME, not an approved equivalence. A building-part pilot should choose an appropriate verified field/model instead. Put structural transformations in versioned SQL.

**Run:** output the original EV field/value beside its canonical key/value and rule revision. Compare it with the matching ISAM ingredient. Then extend to the pilot model’s relevant ingredients.

**Done when:** translations preserve units, numeric precision, NULL semantics and provenance. Unmapped/invalid fields stay visible. This step does not require every model’s rules to be implemented at once.

### 8. Save and open intermediate evidence

**Build:** linked intermediate-result rows and Lift drill-down. Connect eligibility → dated extraction → translation → comparison → persistence to the existing workflow.

**Run:** open a calculated-difference row and inspect its ingredients. Run generalized-only, missing and failed-source cases to verify they do not trigger normal intermediate work. Exercise a failure during detail writing and retry.

**Done when:** users see both values, source evidence, the rule and issues; incomplete details are not advertised as complete. Distinguish execution completion from translation coverage. Extend and verify model coverage incrementally.

**Second useful delivery:** building-part final comparison plus intermediate explanations for explicitly supported models. Remaining models are listed as unfinished, not silently omitted.

## D. Parcels: reuse the workflow, change the matching logic

### 9. Compare parcel totals without matching individual parts

**Build:** parcel source analysis and final SQL that separately groups each side by cutoff date + parcel + model + corresponding version, then joins the two totals. Retain counts, source part IDs, available total area/share and `PARCELA_MODEL_AGREGAT`. Handle partial source failures explicitly rather than allowing SUM to hide invalid parts.

**Run:** a parcel with several parts of the same model, including a case with different part counts on each side. ISAM 60+40 versus EV 30+30+40 must produce totals 100/100, not a six-row part join.

**Done when:** the independently verified totals and evidence are saved/displayed through the existing final-result flow. Confirm generalized rounding policy; until agreed, display both “sum rounded parts” and “round the total once” where the required rounding implementation is available, clearly labelled. Do not invent that implementation or silently choose a policy.

### 10. Explain parcel differences using business meaning

**Build:** one model’s semantic component key using attributes available in both sources, followed by its translation rules and uniqueness checks. Reuse the detail-result format. Agree any required parcel-ID representation changes with GURS.

**Run:** examples with a unique semantic match, differing partitions and indistinguishable components.

**Done when:** valid matches have traceable evidence; ambiguous cases show `NEENOLICNA_STRUKTURA` and meaningful aggregate evidence. No pairing by part ID, `row_number()` or area alone. Expand model coverage one model at a time.

## E. Finish the full task

### 11. Verify coverage and a complete representative run

Document supported dates/models/versions and resolve the required coverage with the task owner. Run representative building-part and parcel cases at realistic volume. Check decimal preservation, statuses, missing/failed records, strict intermediate tolerance threshold, translation provenance, visible ambiguity, retries and Lift filters/drill-down.

Do not call 5757 complete while required models, historical selection or business rules remain unresolved. Performance checks should use bounded queries and query plans before expanding volume.

## Where to start next

**Two concrete pieces of work:**

1. Prepare the decimal migration and Lift metadata change, with one decimal round-trip check.
2. Create the read-only building-part source inspector and prove one dated, version-compatible pair.

That gives the next comparison step reliable inputs. Do not start by building a translator for every model.

## Rules for keeping the work small

- Keep one workflow and extend it; these milestones do not require separate deployed services.
- Keep date/model/property scope configurable from the start, so each new piece can be run on a small sample.
- Preserve intermediate working outputs during development, but only create permanent tables when a milestone needs them.
- Use synthetic cases for logic checks and real dated evidence for source correctness; neither substitutes for the other.
- Database exploration remains read-only and rolled back. Applying migrations and writing comparison results belongs to explicitly targeted development execution, not the exploration helper.
