# VM–VO SFC test guide

Run these tests in order on the test environment. Fixtures were inspected read-only on 2026-10-23; if someone has changed them, check the starting state before proceeding.

This guide follows the pasted FE ticket and newer historical-join rules: historical → historical creates an editable VM copy and joins that copy. The older local BE ticket contradicts that rule.

Action names below are from the ticket. The deployed SFC field captions and final submit-button text were not available locally. “Submit” means the SFC's execution/confirmation button. Select fields by their source/target role, not their visual order.

## Before starting

1. Open **MD Območja verzije**.
2. Find rows by **verzija_obmocja** (VO number), not table position or gid.
3. Open the SFC from the specified VO row. These actions are attached to VO rows; choose the VM inside the SFC.
4. For each executed operation, record VM UUID, model/version, VO, cona/LAO/TAO counts and area links before and after. Record source and target for copying.
5. Wait for the workflow to finish, then refresh the table/map before checking results. A start/success notification is insufficient by itself.
6. For steps saying **cancel**, do not submit. Part 1 deliberately preserves fixtures for later tests.

After every successful mutation, verify that VO areas and unrelated VMs/hierarchies remain unchanged. Counts alone are insufficient: inspect area IDs and parent references when possible.

## How to read the instructions

**The VO row where you open the SFC is the starting/source VO. It is not the destination.**

For **Pridruži na VO**, there are three separate choices:

1. **Starting row:** open the action menu on the specified row in MD Območja verzije.
2. **VM to move:** inside the SFC, select the specified VM belonging to that starting row.
3. **Destination VO:** inside the SFC, select where that VM should go, only when the test specifies a destination.

Example: “starting row VO 118; VM to move STA v227; destination VO 4” means open the action on row 118 and move STA v227 out of it into VO 4.

For **Ponastavi hierarhijo**, select the VM whose hierarchy will be deleted and rebuilt. There is no destination VO.

For **Prekopiraj hierarhijo iz VM**, both VMs belong to the row where you open the action. **Source VM** supplies the hierarchy and stays unchanged. **Target VM** loses its existing hierarchy and receives the copy.

## 1. Eligibility, selectors and form restrictions

### 1A. Two VMs of the same type block a front join

**Purpose:** try to move HIS v291 OUT OF VO 113. Then try to move HIS v292 OUT OF VO 113. This does not test moving another HIS version into VO 113.

First attempt:

1. In **MD Območja verzije**, find the row whose VO number is **113**.
2. Open the action menu **on that row** and click **Pridruži na VO**.
3. In the SFC's **VM to move** selector, choose **HIS v291**. This is the source VM, not a VM already present at a destination you are selecting.
4. **Do not select a destination VO for this check.** Inspect whether the SFC prevents proceeding with HIS v291 and displays the reason.
5. Expected: it cannot execute because its starting VO 113 contains both HIS v291 and HIS v292.
6. Cancel/close the SFC without executing.

Second attempt:

1. Again open **Pridruži na VO on row VO 113**.
2. This time select **HIS v292 as the VM to move**.
3. Again check blocking and the explanation, without choosing a destination.
4. Cancel/close without executing.

Expected for both attempts:

- The UI prevents execution and explains that the starting VO contains multiple VMs of the same model type.
- Both VMs are editable, so the reason must be multiplicity, not protection.
- No record or hierarchy changes.
- If invalid VMs are excluded from the selector, record that behavior and whether the reason is visible. If they are selectable, execution must remain blocked.
- If your UI requires a destination before displaying validation, choose **VO 116 as destination**. It is a front VO. The operation must still be blocked; do not execute it if the expected restriction is missing.

Actually, we correctly fail with:
  

  "message": "JOIN_SAME_GEO_VERSION: Verzija modela je že pridružena izbrani verziji območij.\n





**HIS v288 is not used in this test.** Selecting HIS v288 and VO 113 as destination tests a different direction and branch. If you already submitted that attempt, verify the result before continuing; the fixtures may have changed. At the inspected starting state, HIS v288 belonged to historical VO 1, so joining it to front VO 113 should have been disallowed

  Here we fail with:

"message": "JOIN_NOT_ALLOWED: Pridružitev ni dovoljena glede na stanje izvorne in ciljne verzije območij.

Should be more specific on why not.




### 1B. A pripisna VM cannot be modified

1. Find **VO 8**.
2. Open **Pridruži na VO** and select **PPP v225**. Check blocking and reason; cancel.
3. Open **Ponastavi hierarhijo** and select **PPP v225**. Check blocking and reason; cancel.
4. On the same **VO 8 row**, open **Prekopiraj hierarhijo iz VM**.
5. Set **source = PPP_MN v21** (the hierarchy to read) and **target = PPP v225** (the protected VM you are trying to overwrite).
6. Check blocking and reason; cancel. If PPP v225 cannot be selected as target, record that it is excluded; do not substitute another target.

For this copy test, both VMs belong to VO 8. PPP_MN v21 is editable, so the expected rejection is caused by the target PPP v225 being pripisna, not by the source.

{
  "message": "JOIN_SAME_GEO_VERSION: Verzija modela je že pridružena izbrani verziji območij.\n
  "message": "MODEL_VERSION_NOT_EDITABLE: Verzije modela ni mogoče urejati, ker je zaklenjena ali pripisna.\n

Expected: all three modifications are blocked because PPP v225 is `pripisna=true`. It must not become executable by selecting another source or destination.

### 1C. A historical VM can be reset despite a locked VO

1. Find **VO 105** (`delovna_geo_coniranje=false`, `zaklenjena=true`).
2. Open **Ponastavi hierarhijo**.
3. Select **INP v50**.
4. Confirm submission is available, then **cancel**.

Expected: allowed because INP v50 is editable and has a VO. Neither historical status nor VO locking blocks it. The SFC needs no additional VO selection.

### 1D. A pripisna source can be read for copying

**SFC settings: open on row VO 105 → Prekopiraj hierarhijo iz VM → source INP v36 → target INP v50. Inspect and cancel; do not submit.**

1. On **VO 105**, open **Prekopiraj hierarhijo iz VM**.
2. Set **target = INP v50**.
3. Open the source selector.
4. Confirm **INP v36** appears; choose it.
5. Confirm submission is available, then **cancel**.

Expected:

- Protected INP v36 is an allowed source.
- Current target INP v50 is excluded from source choices.
- Source choices contain only other VMs belonging to VO 105.
- Choices identify model type, version and name where available.
- No global latest filter hides INP v36.

### 1E. Existing copy-VO button follows frontness, not locking

1. Find **VO 4**: front, locked.
2. Inspect its existing **copy VO** action. It must be visible. Do not execute.
3. Find **VO 105**: historical, locked.
4. Inspect the same action. It must be hidden.

Expected: `delovna_geo_coniranje=true` controls visibility. A locked front VO remains copyable. The exact deployed label of this pre-existing action was not verified locally.

### 1F. Manual relationship/frontness editing is unavailable

1. Open the normal edit form for VO 4. Inspect `delovna_geo_coniranje`; cancel.
2. Open its administrative edit form. Inspect the same field; cancel.
3. Open normal and administrative edit forms for INP v50. Inspect `id_rel_geo_verzija`; cancel.
4. Begin creating a VM from scratch. Inspect the VO field; cancel unless creating the valid fixture for section 7.

Expected:

- Neither normal nor admin forms permit ordinary manual editing of VO frontness.
- Neither permits ordinary manual editing of VM → VO.
- Existing VM's VO is displayed as information.
- A new VM starts without a VO and cannot manually select one during creation.
- Existing copy-VM and copy-VO actions still exist where applicable.

## 2. Historical hierarchy copy, then reset

### 2A. Execute a copy from a protected source

**SFC settings: open on row VO 105 → Prekopiraj hierarhijo iz VM → source INP v36 → target INP v50 → submit. INP v50 is overwritten; INP v36 is only read.**

1. On **VO 105**, open **Prekopiraj hierarhijo iz VM**.
2. Set **source = INP v36**, **target = INP v50**.
3. Submit, wait for completion, refresh.

Expected:

- INP v50 remains the same VM on VO 105.
- Target hierarchy is replaced with **116 cone, 3 LAO, 3 TAO**.
- Source has three supported levels; target also has three. Cona levels are preserved.
- Copied records have new IDs; cona → LAO and LAO → TAO references point to copied target records. Check both cona LAO-reference fields if populated.
- Area assignments match the source using the same VO areas.
- Target's old hierarchy is gone, rather than retained alongside the copy.
- INP v36 and its hierarchy remain unchanged.
- Copied target records are editable. Try a harmless editable text field, save, and restore it.

### 2B. Reset that target

1. On **VO 105**, open **Ponastavi hierarhijo**.
2. Select **INP v50**. Submit, wait, refresh.
3. Repeat the same reset once more.

Expected after each reset:

- Exactly **one cona**, `st_ravni=1`.
- Exactly **116 links**, one to each current area of VO 105.
- **Zero LAO and zero TAO**, including no stale parent references.
- Geometry represents all linked VO areas after recalculation completes.
- Previous cona IDs and their links are removed.
- Repeating does not accumulate cone or duplicate links.
- INP v36 is unchanged.

## 3. Copy hierarchy with different supported level counts

Use **VO 117**. Initially STA v228 supports 20 levels and has 868 cone, 17 LAO, 17 TAO; TUR v43 supports 21 levels and has one base cona.

### 3A. Target supports more levels

**SFC settings: open on row VO 117 → Prekopiraj hierarhijo iz VM → source STA v228 → target TUR v43 → submit. TUR v43 is overwritten; STA v228 is only read.**

1. On VO 117 open **Prekopiraj hierarhijo iz VM**.
2. Set **source = STA v228**, **target = TUR v43**.
3. Submit, wait, refresh.

Expected: TUR gets 868 cone, 17 LAO, 17 TAO with the source cona levels preserved, new hierarchy IDs and correct copied parent references. Old TUR base cona is removed. STA is unchanged. Area links match STA's assignments; do not assume every one of VO 117's 907 areas was assigned in the source.

### 3B. Target supports fewer levels

**SFC settings: open on row VO 117 → Prekopiraj hierarhijo iz VM → source TUR v43 → target STA v228 → submit. STA v228 is overwritten; TUR v43 is only read. Run after 3A.**

1. On **VO 117**, open **Prekopiraj hierarhijo iz VM**.
2. Set **source = TUR v43**, **target = STA v228**.
3. Submit, wait, refresh.

Expected: STA gets a complete replacement copy, but **every copied cona has level 1** because STA supports 20 levels and TUR supports 21. This comparison uses supported levels, even though TUR's current copied cone only use levels up to 20. TUR stays unchanged, including its varied levels.

### 3C. Equal supported level counts

**SFC settings: open on row VO 101 → Prekopiraj hierarhijo iz VM → source STA v225 → target STA v226 → submit. STA v226 is overwritten; STA v225 is only read.**

1. On **VO 101**, open **Prekopiraj hierarhijo iz VM**.
2. Set **source = STA v225**, **target = STA v226**.
3. Submit, wait, refresh.

Expected: 868 cone, 17 LAO, 17 TAO; levels preserved because both support 20. Historical target is allowed. Source v225 remains unchanged. Verify old target IDs disappear and new IDs are created, since the initial counts already match.

Do not use HIS v292 as a clean capacity fixture: it currently has no `md_tvr` level definitions.

## 4. Front join into a locked VO, then same-VO join

### 4A. Move the same VM and reset using target areas

1. Find **VO 118** and record **STA v227 UUID = 9ea37aa0-b810-11f1-a360-0e6a76f7d08a**.
2. Open **Pridruži na VO**.
3. Select **VM = STA v227**.
4. Inspect destinations: historical VO 105 must not be available; front locked VO 4 must be available.
5. Select **target VO = 4** and submit.
6. Wait, refresh source and destination rows, then inspect hierarchy.

Expected:

- Same STA v227 UUID and version now belongs to VO 4; no VM copy is created.
- Its previous 868 cone, 17 LAO, 17 TAO are removed.
- New hierarchy: **one level-1 cona, 132 area links, zero LAO/TAO**.
- Links use VO 4 areas, with no links to old VO 118 areas.
- VO 118's 908 areas remain unchanged; VO 4's areas and IND models remain unchanged.
- Both front flags remain unchanged. Target VO locking does not block the join.

### 4B. Join to the same front VO

1. On **VO 4**, open **Pridruži na VO**.
2. Select **STA v227**, **target VO = 4**.
3. Submit, wait, refresh.

Expected: allowed. Same VM remains on VO 4; hierarchy is freshly reset to one level-1 cona and 132 links, zero LAO/TAO. No extra VM or accumulated cona is created.

## 5. Historical join creates an editable copy

### 5A. Historical → different historical VO

1. On **VO 105**, open **Pridruži na VO**.
2. Select **VM = INP v36** (`pripisna=true`).
3. Inspect destinations: only historical VOs should be offered; front VO 4 must be absent.
4. Select **target VO = 104** (historical and locked).
5. Submit, wait, refresh.

Expected:

- Original INP v36 remains on VO 105, protected and with unchanged hierarchy.
- A **new INP VM with a new UUID** appears on VO 104.
- New version is the global maximum INP version before execution + 1; do not hardcode it if others are testing.
- New VM is editable: `zaklenjena_verzija=false`, `pripisna=false`, and hierarchy records permit editing.
- New hierarchy: **one level-1 cona, 116 links to VO 104 areas, zero LAO/TAO**.
- VO 104's IND v51 is unchanged. Neither VO's front flag or areas change.

### 5B. Historical → same historical VO

1. On **VO 105**, open **Pridruži na VO** again.
2. Select original **INP v36**, **target VO = 105**.
3. Submit, wait, refresh.

Expected: another new editable INP copy is created on VO 105, with one level-1 cona and 116 area links. Original v36 remains unchanged. Same-VO selection must not skip copying in the historical branch.

## 6. Existing VO copy makes a blocked front VM movable

1. On **VO 6**, open **Pridruži na VO**, select **KME v101**.
2. Confirm blocked because both KME v100 and v101 belong to VO 6. Cancel.
3. Run the existing **copy VO** action on **VO 6**. If the SFC asks for a source, choose VO 6. Do not manually change frontness.
4. Wait and identify the new VO number; call it **VO N**.
5. Check old VO 6 is historical and VO N is front.
6. Check **KME v100 stays on VO 6**, while **KME v101 moves to VO N**. The copy selects highest version within the source VO.
7. Check VO N has 227 copied areas and v101 links reference the copied areas. Existing v101 hierarchy should be preserved by VO copying.
8. On **VO N**, open **Pridruži na VO**.
9. Select **KME v101**, **target VO = 116**.
10. Submit, wait, refresh.

Expected: same KME v101 moves to front VO 116 and resets to **one level-1 cona, 238 area links, zero LAO/TAO**. VO N's copied areas remain. KME v100 and its historical hierarchy remain unchanged. VO N and VO 116 stay front.

## 7. Additional fixtures for uncovered branches

These cases need valid fixtures; the inspected DB had no empty VO and no VM with `zaklenjena_verzija=true`. Do not use the existing unnamed/model-less VM rows as valid fixtures.

### 7A. Editable VM without a VO

1. Create a valid editable **STA VM from scratch** using normal application creation. Leave VO empty as required; record new version and UUID.
2. Open **Pridruži na VO** through the application's entry point that exposes unattached VMs.
3. Select the new STA VM.
4. Inspect targets: historical VO 105 is allowed; front VO 117 is allowed because it contains STA; front VO 114 is excluded because it contains only GOZ.
5. Choose **VO 117**, submit, wait, refresh.

Expected: same UUID is joined, with one level-1 cona linked to all 907 areas of VO 117, zero LAO/TAO. Existing STA/TUR VMs remain unchanged. The “target already contains this type” restriction is specific to the no-VO → front branch.

Repeat with another valid unattached STA and target historical VO 105: same VM is joined directly, without creating a copy.

**UI reachability check:** the ticket attaches SFCs to VO rows but also specifies VMs without VO. If every source selector only lists VMs on its row, this branch cannot be reached. Record this as a UI/spec gap rather than choosing an unrelated attached VM.

### 7B. Empty VO

1. Obtain a valid historical VO with zero areas through supported setup.
2. Join a valid editable unattached VM to it; record the VM.
3. Run **Ponastavi hierarhijo** on that VM, then repeat once.

Expected after join and each reset: exactly one level-1 cona, zero area links, no geometry, zero LAO/TAO. No duplicates or failure during geometry recalculation.

### 7C. Locked VM independently of pripisna

1. Use **VO 117**, with **STA v228 as the VM to lock** and **TUR v43 as its editable peer**. Run this after section 3. Through a supported application action or approved fixture setup, set STA v228 to `zaklenjena_verzija=true`, `pripisna=false`. Confirm TUR v43 remains editable and both still belong to VO 117. Record the original lock state so you can restore it afterward. If you cannot prepare this state, mark this test as needing a fixture; do not treat the existing editable STA as locked.
2. In **Pridruži na VO**, choose the locked VM: blocked with locking reason.
3. In **Ponastavi hierarhijo**, choose it: blocked.
4. On **VO 117**, open **Prekopiraj hierarhijo iz VM**. Set **source = TUR v43**, **target = locked STA v228**. Expected: blocked because the target is locked. Cancel.
5. On **VO 117**, open **Prekopiraj hierarhijo iz VM** again. Set **source = locked STA v228**, **target = editable TUR v43**. Expected: allowed. Submit, wait, refresh, and verify the copied TUR hierarchy is editable while source STA remains unchanged.
6. Restore STA v228's original lock state using the supported setup mechanism.

Expected: protection applies to the VM being changed, while protected sources can be read.

## Optional BE rejection checks

If you can replay SFC requests, submit deliberately invalid combinations using the same request structure. Verify a rejection and no partial mutations:

- Front → historical and historical → front join.
- Front join with multiple same-type source VMs.
- Reset a protected target, or replay hierarchy copy with **source PPP_MN v21 → target PPP v225**, from **VO 8**: reject protected target.
- Replay hierarchy copy with **source INP v36 (VO 105) → target STA v226 (VO 101)**: reject different VOs.
- Replay hierarchy copy with **source INP v50 → target INP v50**, from **VO 105**: reject identical source and target.
- No-VO VM → front VO without that model type.

UI filtering and disabled buttons alone do not verify BE validation.

## Evidence to retain

For each test, save selected VO/VM identifiers, source/target roles, expected vs actual result, workflow completion/failure, before/after hierarchy counts, and any relevant screenshot. For copying, include new IDs and parent/area reference checks. For rejection, confirm no state changed.

If time is limited, run sections **1–5** first. Sections 6–7 cover VO-copy regression and the remaining fixture-dependent branches.
