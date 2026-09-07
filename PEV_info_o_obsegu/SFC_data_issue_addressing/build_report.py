"""Build the standalone handoff report from the current plan and captured evidence."""
from pathlib import Path
from html import escape

root = Path(__file__).resolve().parent
plan = (root / 'README.md').read_text()
# The handoff has a fixed numbered installation section; render those steps directly.
install_section = plan.split('## Install later\n', 1)[1].split('## FO and downstream caveats', 1)[0]
install_steps = ''.join(
    '<li>' + escape(line.split('. ', 1)[1]) + '</li>'
    for line in install_section.splitlines() if line[:1].isdigit()
)
evidence = ''.join(
    f'<details><summary>{escape(path.name)}</summary><pre>{escape(path.read_text())}</pre></details>'
    for path in sorted((root / 'evidence').glob('*.txt'))
)
(root / 'analysis.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PEV — FO copies: verified analysis and plan</title>
<style>body{max-width:1100px;margin:40px auto;padding:0 24px;font:17px/1.6 system-ui;color:#183040;background:#f7fafb}h1,h2{line-height:1.2}article{background:white;border:1px solid #d5e0e5;padding:24px;border-radius:10px;margin:20px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.55 ui-monospace,monospace}summary{cursor:pointer;font-weight:600}a{color:#066d91}.note{border-left:5px solid #168176}table{border-collapse:collapse}td,th{padding:12px;border:1px solid #ccd9df;text-align:left}</style>
<h1>PEV copies for independent FO editing</h1><p>Verified against test DB catalog and trigger definitions · 7 September 2026</p>
<article class="note"><h2>Copy the building parts too</h2><p>The deployed FO trigger joins parts to their parent building. A building with no parts supplies no FO geometry and is copied with zero parts. This preserves its existing lack of FO contribution. Read-only counts found 9,817 such records among 41,478 enabled buildings linked to an FO (see live_building_part_counts.txt). Copy every part and change its parent ID to the new building. The original keeps its parts but its <code>fo_geom_upost=false</code> excludes their contribution.</p></article>
<article><h2>Geometry and attribute area are separate</h2>
<table><tr><th>Value</th><th>Generated FO calculation</th><th>Effect of cutting geometry</th></tr>
<tr><td>geom_povr</td><td>Area of cleaned union of eligible parcel/building geometry</td><td>Changes when the resulting union changes</td></tr>
<tr><td>atr_povr</td><td>Sum of parcel povrsina + building-part povrsina</td><td>No automatic scaling</td></tr></table>
<p>FO eligibility is <code>fo_geom_upost=true</code>. The formula ignores part <code>dst_upost</code>, component <code>upostevan</code>, and share fields. When <code>generiraj_nov_geom</code> is not true, the trigger can prefer archive or existing FO geometry/area. An identical copy therefore preserves the inputs but does not switch FO mode.</p></article>
<article><h2>Verified trigger implications</h2><p><code>prikazan_na_sloju</code> already exists as <code>boolean NOT NULL DEFAULT true</code> on both tables. Read-only verification confirms true on all 41,478 buildings and 107,885 parcels (see live_display_field.txt). No migration or backfill is needed; application layer filters must use this field. Copies set it to false; originals keep it unchanged. The live parcel BEFORE INSERT trigger recalculates <code>delez_bzps</code> only for an enabled FO input, so this implementation inserts the copy disabled and enables it after copying. Synchronization triggers update <code>id_rel_pe</code>; they do not exclude duplicates from reports.</p><p>Existing reports and value distribution can still read both versions. Future parcel-share changes can double-count copied building footprints in the live <code>delez_bzps</code> trigger. These are concrete downstream policy decisions to resolve before enabling broad use; the implementation preserves the requested attributes.</p></article>
<article><h2>Implementation plan and handoff</h2><p>One SFC → existing workflow endpoint → one workflow → one transaction activity. The original is disabled, the copy inserted disabled, all existing parts copied, and the copy enabled in one transaction. Stable source-derived UUIDs make repeat requests return the same copy. Full architecture notes and limits are in <a href="README.md">README.md</a>.</p><h3>Install later</h3><ol>''' + install_steps + '''</ol></article>
<article><h2>Verification boundary</h2><p>Live PostgreSQL inspection succeeded in a read-only transaction. No remote mutation test, deployment, or actual application SFC execution was performed. Local disposable PostgreSQL initialization was blocked by sandbox shared-memory permissions. Seven Python unit tests and Python compilation pass. Both Vue scripts/templates compile using FMP’s installed @vue/compiler-sfc, and the explicit column lists match all business fields in the captured live metadata. Python unit tests exercise transaction control and SQL dispatch with a fake cursor; they do not emulate PostgreSQL triggers.</p></article>
<h2>Evidence</h2><p>Captured local sources include their original source paths and hashes. Live catalog files show deployed definitions; no credentials are included.</p>''' + evidence + '</html>')
