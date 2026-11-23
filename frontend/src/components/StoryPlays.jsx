// Ways to play a custom story: the idea engine's top picks for the story's hunch (stocks, ETFs or options),
// found once per story on the server and shared. Practice money only.
import React, { useEffect, useState } from 'react';
import { getCustomPlays } from '../lib/api';

const _plays = new Map(); // q -> ready response, for this page load

export function playLabel(structure) {
  if (structure === 'Buy Stock') return 'Buy the shares';
  if (structure === 'Sell / Avoid') return 'Stay out or sell';
  return `${structure} (options)`;
}

export function useStoryPlays(q) {
  const [d, setD] = useState(() => _plays.get(q) || null);
  useEffect(() => {
    if (!q || _plays.has(q)) return undefined;
    let alive = true, tries = 0, t = null;
    const poll = () => {
      getCustomPlays(q)
        .then((r) => {
          if (!alive) return;
          if (r?.status === 'working' && tries++ < 60) { setD(r); t = setTimeout(poll, 4000); return; }
          if (r?.status === 'ready') _plays.set(q, r);
          setD(r?.status === 'working' ? { status: 'none' } : r);
        })
        .catch(() => alive && setD({ status: 'none' }));
    };
    poll();
    return () => { alive = false; clearTimeout(t); };
  }, [q]);
  return d;
}

export default function StoryPlays({ q, dark = false, compact = false }) {
  const d = useStoryPlays(q);
  if (!d || d.status === 'working') {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-400" role="status">
        <div className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
        Finding ways to play it (can take a minute or two)…
      </div>
    );
  }
  if (d.status !== 'ready' || !d.plays?.length) return null;
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Ways to play it · practice money</div>
      <ul className={`mt-1.5 divide-y divide-slate-800 rounded-xl border border-slate-800 ${dark ? 'bg-slate-900/80' : 'bg-slate-950/50'}`}>
        {d.plays.map((p) => {
          // shares can't bet on a big move either way or on a quiet stock: then the options version is the play
          const sideways = p.direction !== 'bullish' && p.direction !== 'bearish';
          const main = sideways && p.structure === 'Sell / Avoid' && p.alt ? p.alt : p.structure;
          const alt = main === p.structure ? p.alt : null;
          const side = p.direction === 'bearish' ? ['▼ bets it falls', 'text-red-300'] : p.direction === 'bullish' ? ['▲ bets it rises', 'text-green-300']
            : p.direction === 'volatile' ? ['◆ bets on a big move', 'text-amber-300'] : ['● bets it stays put', 'text-slate-300'];
          return (
            <li key={p.ticker} className="px-3 py-2">
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-bold text-white">{p.ticker} <span className="text-xs font-medium text-slate-400">{playLabel(main)}</span></span>
                <span className={`shrink-0 text-[11px] font-bold ${side[1]}`}>{side[0]}</span>
              </div>
              {p.rationale && <div className={`text-xs text-slate-400 ${compact ? 'line-clamp-1' : 'line-clamp-2'}`}>{p.rationale}</div>}
              {alt && <div className="text-[11px] text-slate-500">or {playLabel(alt).replace(' (options)', ' with options').replace('Buy the shares', 'simply buy the shares')}</div>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
