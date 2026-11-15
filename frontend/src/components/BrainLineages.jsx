// "Survival of the smartest": AI strategists compete on the same graded beliefs. The weakest retire, the strongest
// evolve into new versions. Scoreboard + family tree + births and retirements, all from the live brain snapshot.
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';

export const STYLE = {
  Momentum: { color: '#60a5fa', blurb: 'buys what is already moving the right way' },
  Value: { color: '#fbbf24', blurb: 'buys what has been beaten down' },
  Steady: { color: '#4ade80', blurb: 'buys the calmest companies' },
  'Follow-the-AI': { color: '#a78bfa', blurb: "trusts the AI's first choice" },
  'Big-picture': { color: '#f472b6', blurb: 'prefers broad funds' },
  'Trend-rider': { color: '#22d3ee', blurb: 'rides the trend line when it points your way and skips choppy names' },
};
const col = (s) => STYLE[s]?.color || '#94a3b8';
const pct = (v) => `${v >= 0 ? '+' : ''}${(v * 100).toFixed(1)}`;

// Fits every generation into the card's width (a phone shows the newest ones, where the leaders are, not just
// Gen 1-5); only when there are too many to fit does it scroll, and then it opens at the newest end.
function Tree({ tree }) {
  const box = useRef(null);
  const [cw, setCw] = useState(0);
  useEffect(() => {
    const el = box.current;
    if (!el) return undefined;
    const set = () => setCw(el.clientWidth);
    set();
    if (typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(set);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const { nodes, edges, labels, w, h } = useMemo(() => {
    const gens = [...new Set(tree.map((t) => t.gen))].sort((a, b) => a - b);
    const byGen = Object.fromEntries(gens.map((g) => [g, tree.filter((t) => t.gen === g)]));
    const rows = Math.max(...gens.map((g) => byGen[g].length), 1);
    const H = Math.max(150, rows * 26 + 30), PAD = 18;
    const span = Math.max(gens.length - 1, 1);
    const GAP = cw ? Math.min(64, Math.max(24, (cw - 2 * PAD) / span)) : 64;
    const pos = {};
    gens.forEach((g, gi) => byGen[g].forEach((t, i) => {
      pos[t.id] = { ...t, x: PAD + gi * GAP, y: (H / (byGen[g].length + 1)) * (i + 1) };
    }));
    const ns = Object.values(pos);
    // "Gen 10" is ~28px at 9px type: when columns are tighter than that, label every other one (always the newest)
    const every = GAP >= 34 ? 1 : 2;
    const last = gens.length - 1;
    return {
      nodes: ns, w: 2 * PAD + (gens.length - 1) * GAP, h: H,
      labels: gens.map((g, gi) => ({ g, x: PAD + gi * GAP, show: gi === last || ((last - gi) % every === 0) })),
      edges: ns.filter((n) => n.parent && pos[n.parent]).map((n) => [pos[n.parent], n]),
    };
  }, [tree, cw]);
  useEffect(() => {
    const el = box.current;
    if (el && w > el.clientWidth) el.scrollLeft = el.scrollWidth;
  }, [w]);
  return (
    <div ref={box} className="overflow-x-auto">
      <svg width={Math.max(w, cw || 0)} height={h} className="block" role="img"
        aria-label={`Family tree of ${tree.length} strategists over ${labels.length} generations`}>
        {edges.map(([a, b], i) => (
          <path key={i} d={`M${a.x},${a.y} C${(a.x + b.x) / 2},${a.y} ${(a.x + b.x) / 2},${b.y} ${b.x},${b.y}`}
            fill="none" stroke={col(b.style)} strokeOpacity={b.status === 'alive' ? 0.6 : 0.18} strokeWidth="1.5" />
        ))}
        {nodes.map((n) => (
          <g key={n.id}>
            {n.status === 'alive' && <circle cx={n.x} cy={n.y} r="9" fill={col(n.style)} opacity="0.18" />}
            <circle cx={n.x} cy={n.y} r="5" fill={n.status === 'alive' ? col(n.style) : '#0f172a'} stroke={col(n.style)}
              strokeOpacity={n.status === 'alive' ? 1 : 0.35} strokeWidth="1.5" />
          </g>
        ))}
        {labels.filter((l) => l.show).map((l) => (
          <text key={l.g} x={l.x} y={h - 4} textAnchor="middle" fontSize="9" fill="#64748b">Gen {l.g}</text>
        ))}
      </svg>
    </div>
  );
}

export default function BrainLineages({ data, ago, now }) {
  if (!data || !data.alive?.length) return null;
  const top = data.alive[0];
  // Yardsticks on the very calls the strategists are scored on (stored by the daily evolve; absent on old snapshots)
  const win = data.window?.n && data.window.app?.n ? data.window : null;
  const gap = win ? top.fitness - win.app.fitness : 0;
  const vsApp = !win ? '' : Math.abs(gap) < 0.001 ? 'about the same as' : gap > 0 ? `${(gap * 100).toFixed(1)} pts ahead of` : `${(-gap * 100).toFixed(1)} pts behind`;
  const rows = win
    ? [...data.alive, { ref: true, fitness: win.app.fitness, beat_rate: win.app.beat_rate }].sort((a, b) => b.fitness - a.fitness)
    : data.alive;
  return (
    <section>
      <h2 className="mt-8 text-xl font-extrabold">Survival of the smartest</h2>
      <p className="mt-1 text-sm text-slate-400">
        AI strategists compete on the same calls. Each one picks its favorite company; the market grades it 90 days later.
        Every trading day the weakest retire and the strongest evolve into new versions.
      </p>

      <div className="mt-3 grid grid-cols-3 gap-2">
        {[['Generation', data.generation], ['Alive', data.alive.length], ['Retired', data.retired]].map(([k, v]) => (
          <div key={k} className="rounded-2xl border border-slate-700/70 bg-slate-900/70 p-3 text-center">
            <div className="text-2xl font-extrabold tabular-nums">{v}</div>
            <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">{k}</div>
          </div>
        ))}
      </div>

      <div className="mt-2.5 rounded-2xl border p-4" style={{ borderColor: `${col(top.style)}66`, background: `${col(top.style)}14` }}>
        <div className="text-[11px] uppercase tracking-wider font-bold" style={{ color: col(top.style) }}>Leading right now</div>
        <div className="mt-0.5 text-lg font-extrabold">{top.name}</div>
        <div className="text-xs text-slate-300">
          {STYLE[top.style]?.blurb ? `It ${STYLE[top.style].blurb}. ` : ''}
          On the last {top.n} graded calls its picks beat the S&P 500 {Math.round(top.beat_rate * 100)}% of the time ({pct(top.fitness)} pts on average).
        </div>
        {win && (
          <div className="mt-2 rounded-xl bg-slate-950/40 px-3 py-2 text-xs text-slate-300">
            <div className="flex justify-between gap-2"><span>App's own #1, same calls</span><span className="font-bold tabular-nums whitespace-nowrap">{pct(win.app.fitness)} pts</span></div>
            <div className="flex justify-between gap-2"><span>A random idea, same calls</span><span className="font-bold tabular-nums whitespace-nowrap">{pct(win.avg_idea)} pts</span></div>
            <div className="mt-1 text-[11px] text-slate-400">
              So the leader is {vsApp} the app's own pick.
              {' '}Each strategist was chosen on these same calls, which flatters it{win.practice >= 0.5 ? `, and ${win.practice >= 0.995 ? 'all' : `${Math.round(win.practice * 100)}%`} of them are practice calls made on past dates` : ''}.
              {' '}The live record below is the fair test.
            </div>
          </div>
        )}
        <div className="mt-2 text-[11px] text-slate-400">
          {data.champion
            ? <><span className="font-bold text-green-300">{data.champion.name}</span> proved itself on calls it never saw and now helps rank real picks.</>
            : `None has earned a say in real picks yet. A strategist needs ${data.live_min} live calls (graded after it was born) that beat the app's own #1 pick.`}
        </div>
      </div>

      <div className="mt-2.5 rounded-2xl border border-slate-700/70 bg-slate-900/70 p-3">
        <div className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold mb-1">Family tree</div>
        <Tree tree={data.tree} />
        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
          {Object.entries(STYLE).map(([k, v]) => (
            <span key={k} className="flex items-center gap-1 text-[10px] text-slate-400"><span className="h-2 w-2 rounded-full" style={{ background: v.color }} />{k}</span>
          ))}
          <span className="text-[10px] text-slate-500">· faded = retired</span>
        </div>
      </div>

      <div className="mt-2.5 rounded-2xl border border-slate-700/70 bg-slate-900/70 divide-y divide-slate-800">
        {rows.map((s) => s.ref ? (
          <div key="app-ref" className="flex items-center gap-3 px-3.5 py-2 bg-slate-800/30">
            <div className="w-5 text-sm font-extrabold text-slate-600">–</div>
            <span className="h-2.5 w-2.5 shrink-0 rounded-full border border-dashed border-slate-400" />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold text-slate-300 truncate">The app's own #1</div>
              <div className="text-[11px] text-slate-500 truncate">for comparison, same calls</div>
            </div>
            <div className="text-right leading-tight">
              <div className="text-sm font-bold tabular-nums text-slate-300">{pct(s.fitness)} pts</div>
              <div className="text-[10px] text-slate-500">beats S&P {Math.round(s.beat_rate * 100)}%</div>
            </div>
          </div>
        ) : (
          <motion.div key={s.id} layout className="flex items-center gap-3 px-3.5 py-2.5">
            <div className="w-5 text-sm font-extrabold text-slate-500 tabular-nums">{data.alive.indexOf(s) + 1}</div>
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: col(s.style) }} />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold truncate">{s.name}{data.champion?.id === s.id && <span className="ml-1.5 rounded bg-green-500/20 px-1.5 py-0.5 text-[10px] font-bold text-green-300">CHAMPION</span>}</div>
              <div className="text-[11px] text-slate-500 truncate">{s.parent_name ? `evolved from ${s.parent_name}` : 'founder'}</div>
            </div>
            <div className="text-right leading-tight">
              <div className={`text-sm font-bold tabular-nums ${s.fitness >= 0 ? 'text-green-400' : 'text-red-400'}`}>{pct(s.fitness)} pts</div>
              <div className="text-[10px] text-slate-500">beats S&P {Math.round(s.beat_rate * 100)}%</div>
              <div className="text-[10px] text-slate-500 whitespace-nowrap">{s.live?.n ? <>live: {pct(s.live.fitness)} pts<br />over {s.live.n.toLocaleString()} calls{s.live_app?.n ? <><br />app's #1: {pct(s.live_app.fitness)} pts</> : null}</> : 'live: none yet'}</div>
            </div>
          </motion.div>
        ))}
      </div>

      {data.events?.length > 0 && (
        <div className="mt-2.5 space-y-1.5">
          {data.events.slice(0, 4).map((e, i) => (
            <div key={i} className="flex items-center justify-between gap-3 text-xs">
              <span className={`flex items-center gap-2 ${e.kind === 'born' ? 'text-slate-300' : 'text-slate-500'}`}><span className={`h-1.5 w-1.5 shrink-0 rounded-full ${e.kind === 'born' ? 'bg-green-400' : 'bg-slate-600'}`} />{e.detail}</span>
              <span className="shrink-0 text-slate-600">{ago(e.at, now)}</span>
            </div>
          ))}
        </div>
      )}
      <p className="mt-2 text-[11px] text-slate-500">Practice only: scored on picks the brain already made and the market already graded. Past results don't predict future ones.</p>
    </section>
  );
}
