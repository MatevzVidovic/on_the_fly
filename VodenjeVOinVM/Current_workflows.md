# Current workflows for verzije območij and copying VM

## Workflows involving verzije območij

In the current Gurs code behind the symlinks, there are **three workflows directly concerned with VO records or their območje links**, plus the model-copy workflow and related geometry workflows.

| Workflow | What it does with VO / območja | How it starts |
|---|---|---|
| **[GeoObmCopyWorkflow](/Users/matevzvidovic/fmp/app/_Company/Gurs/Services/Workflows/GeoObmCopyWorkflow.php:20)** | Creates a new VO, copies its območja, moves selected VMs to it, updates območje–cona links, and recalculates geometry. | Explicit workflow invocation with the source VO ID. |
| **[LockGeoObmVerzijaWorkflow](/Users/matevzvidovic/fmp/app/_Company/Gurs/Services/Workflows/LockGeoObmVerzijaWorkflow.php:14)** | Locks a VO and its območja if it contains more than one VM of the same model type. | Automatically after a VM is created, including through model copying. |
| **[UpdateObmConaRelationsWorkflow](/Users/matevzvidovic/fmp/app/_Company/Gurs/Services/Workflows/UpdateObmConaRelationsWorkflow.php:17)** | Repoints a VM’s existing območje–cona links to copied območja, using `kopiran_id`, then recalculates geometry. | Standalone workflow exists, but I found no current Gurs event listener invoking it. VO copying uses its activities directly. |

**When a verzija modela is copied**

[CloneModelVersionWorkflow](/Users/matevzvidovic/fmp/app/_Company/Gurs/Services/Workflows/CloneModelVersionWorkflow.php:19):

1. Creates a new VM with `MAX(verzija) + 1` for that model type.
2. **Keeps the same `id_rel_geo_verzija`**, so the copy stays on the original VO.
3. Copies the model data and cone → LAO → TAO hierarchy.
4. Copies `obmxcona` links, pointing them to the new cone but **the same existing območja**.
5. The new VM’s creation event starts `LockGeoObmVerzijaWorkflow`. Because the original and copy share the VO and model type, that VO gets locked asynchronously.

**Model copying does not create a new VO or copy območja.**

**When a verzija območij is copied**

`GeoObmCopyWorkflow`:

1. Creates an unlocked VO with global `MAX(verzija_obmocja) + 1` and `delovna_geo_coniranje=true`.
2. Sets the source VO to `zaklenjena=true` and `delovna_geo_coniranje=false`.
3. Copies all source območja, recording each original ID in `kopiran_id`.
4. Groups VMs **attached to the source VO** by model type:
   - If there is one VM of that type, moves it.
   - If there are several, moves only the one with the highest `verzija`.
5. Repoints moved VMs’ existing `obmxcona` links to the copied območja.
6. Runs `RecalculateGeoHierarchyWorkflow`.

A detail relevant to your spec: this selects the **highest version within the source VO**, not necessarily the globally latest version of that model type. See [GeoObmCopyActivity](/Users/matevzvidovic/fmp/app/_Company/Gurs/Services/Activities/GeoObmCopyActivity.php:127).

These additional workflows touch the associated geometry or locking:

| Workflow | Role |
|---|---|
| **[GeoObmSplitWorkflow](/Users/matevzvidovic/fmp/app/_Company/Gurs/Services/Workflows/GeoObmSplitWorkflow.php:14)** | Handles a newly inserted območje with a `split_group_id`: inherits the original’s VO and copies its cona assignments. Does not create a VO. |
| **[RecalculateGeoHierarchyWorkflow](/Users/matevzvidovic/fmp/app/_Company/Gurs/Services/Workflows/RecalculateGeoHierarchyWorkflow.php:23)** | Recalculates cone → LAO → TAO geometry after območje geometry or območje–cona assignments change. Also called by VO copying and relation remapping. |
| **[LockVerzijaModelaWorkflow](/Users/matevzvidovic/fmp/app/_Company/Gurs/Services/Workflows/LockVerzijaModelaWorkflow.php:14)** | Sets read-only flags on a VM’s related data, including cone, LAO, TAO and `obmxcona`, when `pripisna` or `zaklenjena_verzija` changes. Does not lock the VO itself. |
| **[SyncMdGeoVersionWorkflow](/Users/matevzvidovic/fmp/app/_Company/Gurs/Services/Workflows/SyncMdGeoVersionWorkflow.php:14)** | Synchronizes **VM references** on LAO and TAO from their cone. Despite its name, it does not manage verzije območij. |

`RecalculateGeoHierarchyWorkflow` additionally calls `RecalculateMdGeoConaFromTransWorkflow` and `RecalculateMdGeoConaTransCountsWorkflow` to refresh transaction-derived cona data.

Two relevant mechanisms are **listeners rather than workflows**: `PreventLockedGeoObmVersionMutationEventListener` blocks območje creation/deletion on a locked VO, and `MdGeoObmDeleteEventListener` deletes an območje’s `obmxcona` links.

The main lifecycle is therefore: **copy VM → shared VO locks → copy VO → selected VMs move to a new unlocked VO, while older versions stay behind.**

## What triggers VO locking

It’s a **PHP `after_create` event on `md_verzije_modeli`**, not something specific to the copy workflow.

The chain is:

`md_verzije_modeli` created → `gms.company.gurs.md_verzije_modeli.created` → `LockGeoObmVerzijaEventListener` → starts `LockGeoObmVerzijaWorkflow` asynchronously.

The event is configured in [events.php](/Users/matevzvidovic/fmp/app/_Company/Gurs/Config/events.php:165), and the listener is registered in [GursEventServiceProvider.php](/Users/matevzvidovic/fmp/app/_Company/Gurs/Providers/GursEventServiceProvider.php:53).

So it applies to manual creation through the application and workflow creation through the normal attribute-table service. **A raw SQL insert or creation that skips event listeners would bypass it.**

## How a copied VM stays connected to its VO

**The copied VM stays connected to the original VM’s VO because the copy preserves `id_rel_geo_verzija`.** There isn’t a separate workflow that connects it afterward.

In [CloneModelVersionActivity::archiveModel()](/Users/matevzvidovic/fmp/app/_Company/Gurs/Services/Activities/CloneModelVersionActivity.php:30), the original VM record becomes the new record’s payload. It changes:

- `id` → a new ID
- `verzija` → highest version for that model type + 1
- `kopija_verzije` → the original’s version number
- `pripisna` → `false`

**`id_rel_geo_verzija` stays unchanged.**

The copy workflow then duplicates cone, LAO, TAO and `obmxcona` links. The new links point to the copied cone but retain references to the **original VO’s existing območja**.

Creating that new VM triggers the PHP `after_create` event, which starts VO locking asynchronously. Since both VMs now share the same model type and VO, **that shared VO gets locked**. Copying the VM does not create a new VO.
