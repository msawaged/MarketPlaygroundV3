// Run: node frontend/src/lib/luck.test.mjs
import assert from 'node:assert/strict';
import { luckGlance, luckSubject } from './luck.js';

// Live numbers from Nov 23: the stored #1 looks better than its no-peek rebuild, so the glance judges the rebuild.
const sk = {
  ranker: {
    active: false,
    old: { n: 2703, lift: 0.0149, lift_t: 4.54, lift_t_nw: 1.91, lift_w: 0.0124, top10_share: 0.27, pos_blocks: 3, n_blocks: 4, last_block_lift: -0.0074 },
    old_pit: { n: 2703, lift: 0.0053, lift_t: 1.71, lift_t_nw: 0.99, lift_w: 0.0042, top10_share: 0.731, pos_blocks: 3, n_blocks: 4, last_block_lift: -0.0165 },
    oos: { n: 2703, lift: 0.0098, lift_t: 2.99, lift_t_nw: 1.83 },
  },
  luck: { bar_ever: 3.3, tries_ever: 51, clear_nw: [], steady_min: 3, pbo: { pbo: 0.343 }, app_lift: 0.0149 },
};
const fwd = { by_days: { 7: { beliefs: 1955, lift: 0.0015, lift_t: 1.04, lift_t_nw: 0.71 } } };

const g = luckGlance(sk, fwd);
assert.equal(g.who, 'our #1 rebuilt without the peek');
const by = Object.fromEntries(g.rows.map((r) => [r.key, r]));
assert.equal(by.lead.mark, 'pass');
assert.equal(by.lead.value, '+0.5 pts on 2,703 test calls');
assert.equal(by.plain.mark, 'fail');            // t 1.7 < 3.3: the stored version's t 4.5 must not leak in
assert.match(by.plain.value, /^t 1\.7 /);
assert.equal(by.overlap.mark, 'fail');
assert.match(by.overlap.value, /0 of 51 ways/);
assert.equal(by.extremes.mark, 'mixed');        // capped lead holds (0.42 vs 0.53) but 10 calls are 73% of it
assert.match(by.extremes.value, /73% of the lead/);
assert.equal(by.time.mark, 'mixed');            // 3 of 4, latest stretch behind
assert.equal(by.pbo.mark, 'mixed');
assert.equal(by.live.mark, 'early');
assert.match(g.verdict, /isn't clear of luck yet/);

// The stored version is judged only when it isn't the flattering one.
const sk2 = JSON.parse(JSON.stringify(sk));
sk2.ranker.old_pit.lift = 0.0145;
assert.equal(luckSubject(sk2).who, 'our #1 pick');
// A live ranker is judged on its own out-of-sample numbers.
const sk3 = JSON.parse(JSON.stringify(sk));
sk3.ranker.active = true;
assert.equal(luckSubject(sk3).who, 'the retrained ranker');

// Clears every bar: plain pass and the verdict says so.
const sk4 = { ranker: { active: false, old: { n: 900, lift: 0.02, lift_t: 4, lift_t_nw: 3.5, lift_w: 0.019, top10_share: 0.2, pos_blocks: 4, n_blocks: 4, last_block_lift: 0.01 } },
  luck: { bar_ever: 3.3, tries_ever: 10, clear_nw: ['a'], pbo: { pbo: 0.05 } } };
const g4 = luckGlance(sk4, null);
assert.ok(g4.rows.every((r) => r.mark === 'pass'));
assert.match(g4.verdict, /clears the luck bar/);
assert.equal(g4.rows.find((r) => r.key === 'live'), undefined);

// Not ahead: no extremes row, verdict says so.
const sk5 = { ranker: { old: { n: 500, lift: -0.003, lift_t: -0.5, lift_w: -0.002 } }, luck: { bar_ever: 3, tries_ever: 5 } };
const g5 = luckGlance(sk5);
assert.equal(g5.rows.find((r) => r.key === 'extremes'), undefined);
assert.match(g5.verdict, /isn't ahead/);
assert.deepEqual(luckGlance({}).rows, []);

// Scorecard headline: the no-peek rebuild leads when the stored #1 flatters; the stored numbers become the aside.
{
  const { scoreHeadline } = await import('./luck.js');
  const s = JSON.parse(JSON.stringify(sk));
  s.top = { n: 4398, beat_rate: 0.534, avg_excess: 0.0229 };
  s.rest = { n: 18881, beat_rate: 0.513, avg_excess: 0.011 };
  Object.assign(s.ranker.old_pit, { beat: 0.5224, avg: 0.0147 });
  s.luck.app_t_nw = 1.91; s.luck.app_clears_nw = false;
  const h = scoreHeadline(s);
  assert.equal(h.basis, 'nopeek');
  assert.equal(h.n, 2703);
  assert.equal(h.beat, 0.5224);
  assert.equal(h.edge, 0.0053);
  assert.equal(h.clears, false);                  // t 0.99 counting overlap, bar 3.3
  assert.equal(h.stored.n, 4398);
  assert.ok(Math.abs(h.stored.edge - 0.0119) < 1e-9);
  // No flattering peek: the stored graded picks stay the headline, and they aren't green while the luck check fails.
  const s2 = JSON.parse(JSON.stringify(s));
  s2.ranker.old_pit.lift = 0.0145;
  const h2 = scoreHeadline(s2);
  assert.equal(h2.basis, 'stored');
  assert.equal(h2.n, 4398);
  assert.equal(h2.clears, false);
  s2.luck.app_clears_nw = true;
  assert.equal(scoreHeadline(s2).clears, true);
  // Older output without old_pit.beat falls back to the stored tiles.
  const s3 = JSON.parse(JSON.stringify(s));
  delete s3.ranker.old_pit.beat;
  assert.equal(scoreHeadline(s3).basis, 'stored');
}
console.log('luck tests ok');
