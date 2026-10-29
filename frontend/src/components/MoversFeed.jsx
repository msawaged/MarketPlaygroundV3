// "Moving now": today's news as hunches, with the companies each one moves and how they're trading today.
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { getMovers } from '../lib/api';

let _cache = null; // one fetch per page load is plenty; the server refreshes every ~30 min

export function useMovers() {
  const [state, setState] = useState(() => (_cache ? { loading: false, data: _cache } : { loading: true, data: null }));
  useEffect(() => {
    if (_cache) return undefined;
    let alive = true;
    getMovers()
      .then((d) => { _cache = d; if (alive) setState({ loading: false, data: d }); })
      .catch(() => alive && setState({ loading: false, data: null }));
    return () => { alive = false; };
  }, []);
  return state;
}

export function ago(iso) {
  const t = Date.parse(iso || '');
  if (!t) return '';
  const m = Math.max(0, Math.round((Date.now() - t) / 60000));
  if (m < 60) return `${m || 1}m ago`;
  const h = Math.round(m / 60);
  return h < 24 ? `${h}h ago` : `${Math.round(h / 24)}d ago`;
}

const lower = (s) => s.charAt(0).toLowerCase() + s.slice(1);
export const believeUrl = (hunch) => `/chat?b=${encodeURIComponent(hunch)}&go=1`;
export const doubtUrl = (hunch) => `/chat?b=${encodeURIComponent(`I don't think ${lower(hunch).replace(/\.$/, '')}`)}&go=1`;

function Chip({ c }) {
  const ch = c.change;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-lg bg-slate-800 border border-slate-700 px-2.5 py-1 text-sm" title={c.why || undefined}>
      {c.direction && (
        <span className={c.direction === 'up' ? 'text-green-400' : 'text-red-400'} aria-label={c.direction === 'up' ? 'helped if true' : 'hurt if true'}>
          {c.direction === 'up' ? '▲' : '▼'}
        </span>
      )}
      <span className="font-bold">{c.ticker}</span>
      {ch != null && <span className={`text-xs ${ch >= 0 ? 'text-green-400' : 'text-red-400'}`}>{ch >= 0 ? '+' : ''}{(ch * 100).toFixed(1)}%</span>}
    </span>
  );
}

export function MoverCard({ item, i = 0 }) {
  const navigate = useNavigate();
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
      className="rounded-2xl border border-slate-700 bg-slate-900/90 p-4">
      <div className="text-[11px] text-slate-500">{[item.source, ago(item.created_at)].filter(Boolean).join(' · ')}</div>
      <div className="mt-1 text-lg font-bold leading-snug">{item.hunch}</div>
      {item.hunch !== item.headline && (
        <p className="mt-1 text-sm text-slate-400 leading-snug">
          {item.url ? <a href={item.url} target="_blank" rel="noopener noreferrer" className="hover:text-slate-200">📰 {item.headline}</a> : <>📰 {item.headline}</>}
        </p>
      )}
      {item.why && <p className="mt-1.5 text-sm text-slate-300">{item.why}</p>}
      <div className="mt-3 flex flex-wrap gap-2">{item.companies.map((c) => <Chip key={c.ticker} c={c} />)}</div>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <button onClick={() => navigate(believeUrl(item.hunch))} className="rounded-xl bg-blue-600 hover:bg-blue-500 py-2.5 text-sm font-bold">I believe it →</button>
        <button onClick={() => navigate(doubtUrl(item.hunch))} className="rounded-xl bg-slate-800 border border-slate-700 hover:border-slate-500 py-2.5 text-sm font-bold text-slate-200">I don't</button>
      </div>
    </motion.div>
  );
}
