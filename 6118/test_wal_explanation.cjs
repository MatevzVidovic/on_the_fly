// Run with jsdom available on NODE_PATH, or installed locally. No DB access.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM, VirtualConsole } = require('jsdom');
const filename = path.join(__dirname, 'wal-transactions-explained.html');
const errors = [];
const console = new VirtualConsole();
console.on('jsdomError', error => errors.push(error.message));
const dom = new JSDOM(fs.readFileSync(filename, 'utf8'), {
  runScripts: 'dangerously', url: `file://${filename}`, virtualConsole: console
});
const doc = dom.window.document;
const root = doc.getElementById('wal-transactions');
const text = id => doc.getElementById(id).textContent;
const choose = mode => doc.querySelector(`[data-ending="${mode}"]`).click();
function jump(label) {
  const button = [...doc.querySelectorAll('[data-step]')].find(button => button.textContent === label);
  assert.ok(button, `Missing step: ${label}`);
  button.click();
}
function reader(isolation) {
  const select = doc.getElementById('reader-isolation');
  select.value = isolation;
  select.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
}
const tuples = id => [...doc.querySelectorAll(`#${id} .row-version`)].map(row => ({
  version: row.querySelector('.version-id').textContent,
  value: row.querySelector('strong').textContent,
  header: row.querySelector('.tuple-meta').textContent
}));

jump('Flush page');
assert.equal(text('writer-value'), '60');
assert.equal(text('reader-value'), '100');
assert.equal(text('transaction-status'), 'in progress');
assert.equal(tuples('disk-versions').length, 3);
assert.equal(doc.querySelectorAll('#wal-disk .wal-record').length, 2);
const beforeCommit = tuples('disk-versions');
jump('COMMIT');
assert.equal(text('reader-value'), '60');
assert.deepEqual(tuples('disk-versions'), beforeCommit, 'Commit must not rewrite tuple values/headers in this model');
assert.match(text('wal-disk'), /COMMIT/);
reader('rr');
assert.equal(text('reader-value'), '100', 'An established RR snapshot must survive another connection committing');
jump('Checkpoint');
assert.equal(text('reader-value'), '100');
jump('Vacuum');
assert.equal(text('reader-value'), '60', 'The illustration explicitly ends the old snapshot before vacuum');
assert.equal(tuples('disk-versions').length, 1);

choose('rollback');
jump('ROLLBACK');
assert.equal(text('transaction-status'), 'ABORTED');
assert.equal(text('reader-value'), '100');
assert.equal(text('writer-value'), '100');
assert.equal(tuples('disk-versions').length, 3, 'Rollback must not instantly remove physical tuples');
assert.match(tuples('disk-versions')[0].header, /xmax=42/);
assert.doesNotMatch(text('wal-disk'), /ABORT/, 'Abort is generated but not depicted as synchronously flushed');
jump('Checkpoint');
assert.match(text('wal-disk'), /ABORT/);
jump('Vacuum');
assert.deepEqual(tuples('disk-versions').map(r => r.value), ['100']);

choose('crash-before');
jump('Crash');
assert.equal(text('reader-value'), '—');
assert.equal(text('writer-value'), '—');
assert.match(text('memory-versions'), /Lost on crash/);
assert.equal(tuples('disk-versions').length, 3);
assert.doesNotMatch(text('wal-disk'), /COMMIT/);
jump('Recover');
assert.equal(text('transaction-status'), 'ABORTED');
assert.equal(text('reader-value'), '100');
assert.equal(text('writer-value'), '—', 'Recovery does not reconnect the original writer');
assert.match(text('wal-memory'), /old buffers were lost/);

choose('crash-after');
jump('COMMIT');
assert.equal(text('reader-value'), '100', 'Existing RR snapshot still sees old state before crash');
jump('Crash');
assert.equal(text('reader-value'), '—');
assert.match(text('wal-disk'), /COMMIT/);
jump('Recover');
assert.equal(text('transaction-status'), 'COMMITTED');
assert.equal(text('reader-value'), '60', 'New connection after recovery must see the durable commit');
assert.match(text('reader-note'), /new snapshot/);

let visited = 0;
for (const mode of ['commit', 'rollback', 'crash-before', 'crash-after']) {
  for (const level of ['rc', 'rr']) {
    choose(mode); reader(level);
    const slider = doc.getElementById('timeline');
    for (let step = 0; step <= Number(slider.max); step++) {
      slider.value = step;
      slider.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
      assert.equal(Number(root.dataset.step), step);
      assert.ok(text('step-title'));
      assert.doesNotMatch(text('live-note'), /undefined/);
      assert.equal(doc.getElementById('back').disabled, step === 0);
      assert.equal(doc.getElementById('next').disabled, step === Number(slider.max));
      visited++;
    }
  }
}
assert.equal(errors.length, 0, errors.join('\n'));
for (const label of doc.querySelectorAll('label[for]')) {
  assert.ok(doc.getElementById(label.htmlFor), `Missing labeled control: ${label.htmlFor}`);
}
assert.equal(doc.querySelectorAll('script[src], link[rel=stylesheet], iframe').length, 0);
process.stdout.write(`Passed: ${visited} scenario/isolation states, commit/rollback/recovery semantics, controls and labels.\n`);
dom.window.close();
