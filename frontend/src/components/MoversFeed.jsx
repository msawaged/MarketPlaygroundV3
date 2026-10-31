// "Moving now": today's news as hunches, with the companies each one moves and how they're trading today.
import React, { Suspense, lazy, useEffect, useState } from 'react';
import { Play } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { getMovers } from '../lib/api';

const StoryViewer = lazy(() => import('./StoryViewer'));

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

function Pct({ v }) {
  if (v == null) return null;
  return <span className={`text-xs font-semibold tabular-nums ${v >= 0 ? 'text-green-400' : 'text-red-400'}`}>{v >= 0 ? '+' : ''}{(v * 100).toFixed(1)}% today</span>;
}

// Leads with the news and the companies it touches (a stock research card), not a statement to vote on.
export function MoverCard({ item, i = 0 }) {
  const navigate = useNavigate();
  const [story, setStory] = useState(false);
  const ai = item.hunch && item.hunch !== item.headline;
  return (
    <>
    {story && <Suspense fallback={null}><StoryViewer headline={item.headline} onClose={() => setStory(false)} /></Suspense>}
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
      className="rounded-2xl border border-slate-700 bg-slate-900/90 p-4">
      <div className="text-[11px] text-slate-500">{[item.source, ago(item.created_at)].filter(Boolean).join(' · ')}</div>
      <div className="mt-1 text-base font-bold leading-snug">
        {item.url ? <a href={item.url} target="_blank" rel="noopener noreferrer" className="hover:text-blue-200">{item.headline}</a> : item.headline}
      </div>
      {ai && <p className="mt-1 text-sm text-slate-400"><span className="text-slate-500">What it could mean: </span>{item.hunch}.</p>}

      <div className="mt-3 text-[11px] uppercase tracking-wider text-slate-500 font-semibold">Companies it touches</div>
      <ul className="mt-1.5 divide-y divide-slate-800 rounded-xl border border-slate-800 bg-slate-950/50">
        {item.companies.map((c) => (
          <li key={c.ticker} className="flex items-center gap-3 px-3 py-2">
            <span className="font-bold w-14 shrink-0">{c.ticker}</span>
            <span className="min-w-0 flex-1 text-xs text-slate-400 truncate">{c.why}</span>
            <span className="shrink-0 text-right leading-tight">
              {c.direction && <span className={`block text-[11px] ${c.direction === 'up' ? 'text-green-300' : 'text-red-300'}`}>{c.direction === 'up' ? 'could gain' : 'could lose'}</span>}
              <Pct v={c.change} />
            </span>
          </li>
        ))}
      </ul>

      <button onClick={() => setStory(true)} className="mt-3 w-full flex items-center justify-center gap-2 rounded-xl border border-blue-500/60 bg-blue-500/10 hover:bg-blue-500/20 py-2.5 text-sm font-bold text-blue-100">
        <Play className="h-4 w-4 fill-current" /> Watch the story in 30 seconds
      </button>
      <button onClick={() => navigate(believeUrl(item.hunch))} className="mt-2 w-full rounded-xl bg-blue-600 hover:bg-blue-500 py-2.5 text-sm font-bold">
        See how to invest in this →
      </button>
      {ai && (
        <button onClick={() => navigate(doubtUrl(item.hunch))} className="mt-2 w-full text-xs text-slate-400 hover:text-slate-200">
          Think it's overblown? See the other side
        </button>
      )}
    </motion.div>
    </>
  );
}
