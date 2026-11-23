// "At a glance" for the Brain page's luck check: one row per check, each with a plain pass / mixed / fail / too-early
// mark, all about the SAME version of the #1 pick. Reporting only: nothing here feeds a gate or today's #1.
//
// Which version: the retrained ranker's out-of-sample result when it is live; otherwise our #1 rebuilt without the
// look-ahead peek (ranker.old_pit) when the stored version looks better than it (d856c72); otherwise the #1 as stored.
// The paragraphs under the glance still describe each check in full, including the stored version.

const pts = (v) => `${v >= 0 ? '+' : ''}${(Number(v) * 100).toFixed(1)}`;
const num = (v) => (v == null || !Number.isFinite(Number(v)) ? null : Number(v));

export function luckSubject(sk) {
  const r = sk?.ranker || {};
  if (r.active && r.oos?.n > 0) return { who: 'the retrained ranker', m: r.oos };
  const pit = r.old_pit, stored = r.old;
  if (pit?.n > 0 && stored && (stored.lift || 0) > (pit.lift || 0) + 0.002) return { who: 'our #1 rebuilt without the peek', m: pit };
  if (stored?.n > 0) return { who: 'our #1 pick', m: stored };
  const L = sk?.luck || {};
  if (L.app_lift == null) return null;
  // Older research output without ranker.old: rebuild what we can from the luck block.
  return {
    who: 'our #1 pick',
    m: { n: L.n, lift: L.app_lift, lift_t: L.app_t, lift_t_nw: L.app_t_nw, lift_w: L.app_lift_w, top10_share: L.app_top10_share,
      pos_blocks: L.app_blocks?.pos_blocks, n_blocks: L.app_blocks?.n_blocks, last_block_lift: L.app_blocks?.last_block_lift },
  };
}

/** Rows: {key, mark: 'pass'|'mixed'|'fail'|'early', label, value}. `forward` is /v4/brain's forward block (optional). */
export function luckGlance(sk, forward) {
  const L = sk?.luck;
  const S = luckSubject(sk);
  if (!L || !S) return { who: null, rows: [], verdict: null };
  const m = S.m, bar = num(L.bar_ever) ?? 3.3, tries = L.tries_ever;
  const rows = [];
  const lift = num(m.lift) ?? 0;
  rows.push({
    key: 'lead', mark: lift > 0.002 ? 'pass' : 'fail', label: 'Ahead of our other ideas',
    value: `${pts(lift)} pts${m.n ? ` on ${Number(m.n).toLocaleString()} test calls` : ''}`,
  });
  const t = num(m.lift_t);
  if (t != null) {
    rows.push({
      key: 'plain', mark: t >= bar ? 'pass' : 'fail', label: 'Clear of luck, each call counted alone',
      value: `t ${t.toFixed(1)} (needs ${bar.toFixed(1)}, since we tried ${tries} ways)`,
    });
  }
  const tn = num(m.lift_t_nw);
  if (tn != null) {
    const k = (L.clear_nw || []).length;
    rows.push({
      key: 'overlap', mark: tn >= bar ? 'pass' : 'fail', label: 'Clear of luck, overlapping calls counted honestly',
      value: `t ${tn.toFixed(1)} (needs ${bar.toFixed(1)}); ${k} of ${tries} ways clear it`,
    });
  }
  const w = num(m.lift_w), sh = num(m.top10_share);
  if (w != null && lift > 0.002) {
    const heavy = sh != null && sh > 0.5;
    const mark = w < 0.5 * lift ? 'fail' : (w >= 0.7 * lift && !heavy ? 'pass' : 'mixed');
    rows.push({
      key: 'extremes', mark, label: 'Not carried by a few huge calls',
      value: `${pts(w)} pts with the extremes capped${sh != null ? `; its 10 best calls are ${Math.round(sh * 100)}% of the lead` : ''}`,
    });
  }
  const pb = num(m.pos_blocks), nb = num(m.n_blocks), lb = num(m.last_block_lift);
  if (pb != null && nb > 1) {
    const need = Number(L.steady_min || 3);
    const mark = pb >= need ? (lb == null || lb > 0 ? 'pass' : 'mixed') : 'fail';
    rows.push({
      key: 'time', mark, label: 'Holds through time',
      value: `ahead in ${pb} of ${nb} stretches${lb != null ? `, latest ${pts(lb)} pts` : ''}`,
    });
  }
  const pbo = num(L.pbo?.pbo);
  if (pbo != null) {
    rows.push({
      key: 'pbo', mark: pbo <= 0.1 ? 'pass' : pbo < 0.35 ? 'mixed' : 'fail', label: 'Best-looking way still good on unseen data',
      value: `bottom half ${Math.round(pbo * 100)}% of the time (passes at 10% or less; pure luck would be 50%)`,
    });
  }
  const fd = forward?.by_days ? Object.keys(forward.by_days).map(Number).sort((a, b) => b - a)[0] : null;
  if (fd) {
    const f = forward.by_days[String(fd)];
    const ft = num(f.lift_t_nw ?? f.lift_t) ?? 0;
    const mark = fd < 90 ? 'early' : (ft >= 2 && f.lift > 0 ? 'pass' : 'fail');
    rows.push({
      key: 'live', mark, label: 'Real-time calls (no hindsight)',
      value: `after ${fd} days: ${pts(f.lift)} pts, t ${ft.toFixed(1)}${fd < 90 ? '; the 90-day test is what counts' : ''}`,
    });
  }
  const strict = rows.find((r) => r.key === 'overlap') || rows.find((r) => r.key === 'plain');
  const verdict = lift <= 0.002
    ? `${cap(S.who)} isn't ahead of our other ideas on these test calls.`
    : strict && strict.mark === 'pass'
      ? `${cap(S.who)} leads our other ideas by ${pts(lift)} pts and clears the luck bar.`
      : `${cap(S.who)} leads our other ideas by ${pts(lift)} pts, but that isn't clear of luck yet.`;
  return { who: S.who, rows, verdict };
}

const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
