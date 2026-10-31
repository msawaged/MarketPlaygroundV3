// "Survival of the smartest": AI strategists compete on the same graded beliefs. The weakest retire, the strongest
// have children. Scoreboard + family tree + births and retirements, all from the live brain snapshot.
import React, { useMemo } from 'react';
import { motion } from 'framer-motion';

export const STYLE = {
  Momentum: { color: '#60a5fa', blurb: 'buys what is already moving the right way' },
  Value: { color: '#fbbf24', blurb: 'buys what has been beaten down' },
  Steady: { color: '#4ade80', blurb: 'buys the calmest companies' },
  'Follow-the-AI': { color: '#a78bfa', blurb: "trusts the AI's first choice" },
  'Big-picture': { color: '#f472b6', blurb: 'prefers broad funds' },
};
const col = (s) => STYLE[s]?.color || '#94a3b8';
const pct = (v) => `${v >= 0 ? '+' : ''}${(v * 100).toFixed(1)}`;

function Tree({ tree }) {
  const { nodes, edges, w, h } = useMemo(() => {
    const gens = [...new Set(tree.map((t) => t.gen))].sort((a, b) => a - b);
    const byGen = Object.fromEntries(gens.map((g) => [g, tree.filter((t) => t.gen === g)]));
    const rows = Math.max(...gens.map((g) => byGen[g].length), 1);
    const H = Math.max(150, rows * 26 + 30), GAP = 64;
    const pos = {};
    gens.forEach((g, gi) => byGen[g].forEach((t, i) => {
      pos[t.id] = { ...t, x: 24 + gi * GAP, y: (H / (byGen[g].length + 1)) * (i + 1) };
    }));
    const ns = Object.values(pos);
    return {
      nodes: ns, w: 48 + (gens.length - 1) * GAP, h: H,
      edges: ns.filter((n) => n.parent && pos[n.parent]).map((n) => [pos[n.parent], n]),
    };
  }, [tree]);
  return (
    <div className="overflow-x-auto -mx-1 px-1">
      <svg width={Math.max(w, 300)} height={h} className="block">
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
        {[...new Set(nodes.map((n) => n.gen))].map((g) => {
          const n = nodes.find((x) => x.gen === g);
          return <text key={g} x={n.x} y={h - 4} textAnchor="middle" fontSize="9" fill="#64748b">Gen {g}</text>;
        })}
      </svg>
    </div>
  );
}

export default function BrainLineages({ data, ago, now }) {
  if (!data || !data.alive?.length) return null;
  const top = data.alive[0];
  return (
    <section>
      <h2 className="mt-8 text-xl font-extrabold">Survival of the smartest</h2>
      <p className="mt-1 text-sm text-slate-400">
        AI strategists compete on the same calls. Each one picks its favorite company; the market grades it 90 days later.
        Every trading day the weakest retire and the strongest have children.
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
        {data.alive.map((s, i) => (
          <motion.div key={s.id} layout className="flex items-center gap-3 px-3.5 py-2.5">
            <div className="w-5 text-sm font-extrabold text-slate-500 tabular-nums">{i + 1}</div>
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: col(s.style) }} />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold truncate">{s.name}{data.champion?.id === s.id && <span className="ml-1.5 rounded bg-green-500/20 px-1.5 py-0.5 text-[10px] font-bold text-green-300">CHAMPION</span>}</div>
              <div className="text-[11px] text-slate-500 truncate">{s.parent_name ? `child of ${s.parent_name}` : 'founder'}</div>
            </div>
            <div className="text-right leading-tight">
              <div className={`text-sm font-bold tabular-nums ${s.fitness >= 0 ? 'text-green-400' : 'text-red-400'}`}>{pct(s.fitness)} pts</div>
              <div className="text-[10px] text-slate-500">beats S&P {Math.round(s.beat_rate * 100)}%</div>
              <div className="text-[10px] text-slate-500">{s.live?.n ? `live: ${pct(s.live.fitness)} pts on ${s.live.n}` : 'live: none yet'}</div>
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
