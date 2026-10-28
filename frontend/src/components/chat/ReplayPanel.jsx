// "If you'd believed this a year ago": the picks' real past year vs the S&P 500.
import React, { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { getReplay } from '../../lib/api';

const pct = (v) => `${v >= 0 ? '+' : ''}${(v * 100).toFixed(1)}%`;

function Lines({ r }) {
  const W = 320, H = 150, L = 34, R = 8, T = 10, B = 22;
  const all = [...r.basket, ...r.spy, 0];
  const lo = Math.min(...all), hi = Math.max(...all);
  const pad = (hi - lo) * 0.1 || 0.05;
  const y = (v) => T + (H - T - B) * (1 - (v - (lo - pad)) / (hi - lo + 2 * pad));
  const x = (i) => L + (W - L - R) * (i / Math.max(1, r.dates.length - 1));
  const path = (arr) => arr.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join('');
  const ticks = [lo, 0, hi].filter((v, i, a) => a.findIndex((w) => Math.abs(w - v) < (hi - lo) * 0.15) === i);
  const month = (d) => new Date(d + 'T12:00:00Z').toLocaleDateString('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' });
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Your picks versus the S&P 500 over the past year">
      {ticks.map((v) => (
        <g key={v}>
          <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke={Math.abs(v) < 1e-9 ? '#475569' : '#1e293b'} strokeDasharray={Math.abs(v) < 1e-9 ? '3 3' : ''} />
          <text x={L - 4} y={y(v) + 3} textAnchor="end" fontSize="9" fill="#64748b">{pct(v)}</text>
        </g>
      ))}
      <motion.path d={path(r.spy)} fill="none" stroke="#94a3b8" strokeWidth="1.5" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1 }} />
      <motion.path d={path(r.basket)} fill="none" stroke="#4DA3FF" strokeWidth="2.5" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1.2 }} />
      <text x={L} y={H - 6} fontSize="9" fill="#64748b">{month(r.start)}</text>
      <text x={W - R} y={H - 6} fontSize="9" fill="#64748b" textAnchor="end">{month(r.end)}</text>
    </svg>
  );
}

export default function ReplayPanel({ picks, onResult }) {
  const [s, setS] = useState({ idle: true });
  const key = useMemo(() => picks.map((p) => p.ticker).join(','), [picks]);

  const run = async () => {
    setS({ loading: true });
    try {
      const r = await getReplay(picks);
      setS({ data: r });
      onResult?.(r);
    } catch (e) {
      setS({ error: e.message });
    }
  };

  if (s.idle) {
    return (
      <button onClick={run} className="w-full rounded-2xl border border-blue-400/30 bg-blue-500/10 hover:border-blue-300 px-4 py-3 text-left">
        <div className="font-bold text-white">⏪ What if you'd believed this a year ago?</div>
        <div className="text-xs text-slate-300">See how these picks really did over the past 12 months.</div>
      </button>
    );
  }
  if (s.loading) return <div className="h-40 rounded-2xl bg-slate-800/60 animate-pulse" aria-label="Loading replay" />;
  if (s.error) return <p className="text-xs text-slate-400">Couldn't replay these picks: {s.error}</p>;

  const r = s.data;
  const bull = r.picks.filter((p) => p.direction !== 'bearish').length >= r.picks.length / 2;
  return (
    <motion.div key={key} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="rounded-2xl border border-slate-700 bg-slate-950/60 p-3.5">
      <div className="text-[11px] uppercase tracking-wider text-blue-300 font-semibold">If you'd believed this a year ago</div>
      <p className="mt-1 text-sm text-white leading-snug">
        These picks {r.basket_return >= 0 ? 'rose' : 'fell'} <b className={r.belief_right ? 'text-green-300' : 'text-red-300'}>{pct(Math.abs(r.basket_return)).replace('+', '')}</b> on average,
        vs {pct(r.spy_return)} for the S&amp;P 500.{' '}
        {r.belief_right ? (r.beat_spy ? 'The belief would have paid off, and beaten the market.' : 'Right direction, but the market did even better.')
          : bull ? "The belief wouldn't have paid off over that year." : "They didn't fall, so the belief wouldn't have paid off."}
      </p>
      <div className="mt-2"><Lines r={r} /></div>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-slate-400 mt-1">
        <span><span className="inline-block w-3 h-0.5 bg-[#4DA3FF] align-middle mr-1" />Your picks (equal amounts)</span>
        <span><span className="inline-block w-3 h-0.5 bg-slate-400 align-middle mr-1" />S&amp;P 500</span>
      </div>
      <div className="mt-2 grid grid-cols-3 gap-2">
        {r.picks.map((p) => (
          <div key={p.ticker} className={`rounded-xl border px-2.5 py-2 ${p.right ? 'border-green-500/30 bg-green-500/10' : 'border-red-500/30 bg-red-500/10'}`}>
            <div className="text-sm font-bold">{p.ticker}</div>
            <div className={`text-sm font-extrabold ${p.return >= 0 ? 'text-green-300' : 'text-red-300'}`}>{pct(p.return)}</div>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[10px] text-slate-500">Share prices only, from {r.start} to {r.end}. The past doesn't predict what happens next.</p>
    </motion.div>
  );
}
