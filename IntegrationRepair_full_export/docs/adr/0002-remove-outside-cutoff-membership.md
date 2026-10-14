# Allow removal outside cutoff-bounded source membership

**Superseded on 2026-10-14.** The Deli audit found real Oracle keys that moved past the cutoff. The full-export repair now retains complete source membership and leaves these keys alone. Only target keys absent from the complete Oracle query result are removal candidates. See `spec/basic_spec.md` for current rules.


Repair compares source and target rows at or before the captured high-water mark rather than complete current source membership. A target row within the cutoff may therefore be removed when its Oracle row has moved beyond that cutoff; this is accepted because the regular integration is expected to restore that newer row later and normal integration runs immediately before repair, which is expected to make this situation absent in practice. Target rows newer than the cutoff are left alone, and saved removals are applied without rechecking Oracle; the alternative of retaining all currently existing source keys was considered and rejected for this repair's cutoff-based semantics.
