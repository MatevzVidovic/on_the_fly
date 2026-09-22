# KN delta observations

Vocabulary for investigating how records become visible in KN source datasets over time.

## Language

**Source dataset**:
The records returned by an integration's saved Oracle query, including its joins and filters. It is not necessarily the contents of a single Oracle table.

**Matching key**:
The integration's identifier for the same record across observations or source and target. A generated target UUID is not automatically this identifier.

**Change timestamp**:
The source field the integration uses to identify changed records, such as `datum_sys`, `zad_spr`, or a derived `date_change`. It does not by itself establish when a record first became visible.

**Observation**:
A completed capture of a defined source dataset at a recorded time. An incomplete capture cannot establish that an unseen key was absent.

**Late visibility**:
A record is absent from an earlier observation and present in a later one while carrying an older change timestamp. This alone does not establish physical insertion time or distinguish an insert from a change in joined data.
_Avoid_: Proven GURS insertion time

**Integration watermark**:
The persisted cutoff used by a particular integration to select delta records. It is distinct from the observation time or the maximum timestamp found in an arbitrary subset.

**Baseline boundary**:
The maximum change timestamp in the first complete source observation, held fixed for this experiment. It is an experimental reference, not an integration watermark.

**Late-visibility candidate**:
A matching key absent from the baseline observation that appears in a later observation of the same window with a change timestamp strictly earlier than the baseline boundary. It may be newly inserted or an existing record whose timestamp moved into the window; it is not proof of physical insertion time.

**First observed**:
The first complete observation in this experiment containing a matching key. For a key absent in an earlier comparable observation, it bounds when visibility changed; it is not the source creation date.

**Observation window**:
The configured range of source change timestamps included in an observation. Its bounds must remain the same across comparisons with a baseline; changing them defines a new experiment.
