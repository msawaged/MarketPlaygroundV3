// News search: find this week's stories about one company, ticker or topic, plus that company's latest headlines.
import React, { useEffect, useRef, useState } from 'react';
import { Search, X } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { searchMovers } from '../lib/api';
import { MoverCard, Pct, ago } from './MoversFeed';

// "NVIDIA Corporation Common Stock" -> "NVIDIA Corporation" (or "NVIDIA" for a sentence)
export function shortName(name, bare = false) {
  const n = String(name || '').replace(/\s+(Common Stock|Ordinary Shares|Class [A-C]\b.*|American Depositary.*)$/i, '').trim();
  return bare ? n.replace(/,?\s+(Inc\.?|Corp\.?|Corporation|Co\.?|Ltd\.?|plc|Holdings?|Company)$/i, '').trim() : n;
}

export function useNewsQuery() {
  const [params, setParams] = useSearchParams();
  const q = params.get('q') || '';
  const setQ = (v) => {
    const next = new URLSearchParams(params);
    if (v) next.set('q', v); else next.delete('q');
    setParams(next, { replace: true });
  };
  return [q, setQ];
}

export function SearchBox({ q, setQ }) {
  const [text, setText] = useState(q);
  useEffect(() => { setText(q); }, [q]);
  useEffect(() => {
    const id = setTimeout(() => { if (text.trim() !== q) setQ(text.trim()); }, 400);
    return () => clearTimeout(id);
  }, [text]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <form role="search" onSubmit={(e) => { e.preventDefault(); setQ(text.trim()); e.currentTarget.querySelector('input')?.blur(); }}
      className="mt-4 flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900 px-3 focus-within:border-blue-500">
      <Search className="h-4 w-4 shrink-0 text-slate-500" aria-hidden="true" />
      <input type="search" value={text} onChange={(e) => setText(e.target.value)} maxLength={60}
        placeholder="Search a company, ticker or topic" aria-label="Search the news"
        enterKeyHint="search" autoCapitalize="none" autoCorrect="off"
        className="min-w-0 flex-1 bg-transparent py-2.5 text-[16px] text-white placeholder:text-slate-500 outline-none [&::-webkit-search-cancel-button]:hidden" />
      {text && (
        <button type="button" onClick={() => { setText(''); setQ(''); }} aria-label="Clear search" className="p-1 text-slate-400 hover:text-white">
          <X className="h-4 w-4" />
        </button>
      )}
    </form>
  );
}

export function SearchResults({ q, setQ }) {
  const navigate = useNavigate();
  const [state, setState] = useState({ loading: true, data: null, error: false });
  const ctrl = useRef(null);
  useEffect(() => {
    if (q.replace(/^\$/, '').length < 2) { setState({ loading: false, data: null, error: false }); return undefined; }
    ctrl.current?.abort();
    const c = new AbortController();
    ctrl.current = c;
    setState((s) => ({ ...s, loading: true, error: false }));
    searchMovers(q, c.signal)
      .then((data) => setState({ loading: false, data, error: false }))
      .catch((e) => { if (e?.name !== 'AbortError') setState({ loading: false, data: null, error: true }); });
    return () => c.abort();
  }, [q]);

  if (q.replace(/^\$/, '').length < 2) return <p className="mt-4 text-sm text-slate-400">Type at least 2 letters.</p>;
  const d = state.data;
  if (state.loading && !d) return <p className="mt-4 text-slate-400">Searching…</p>;
  if (state.error) return <p className="mt-4 rounded-xl border border-red-500/40 bg-red-950/40 p-4 text-sm text-red-200">Search isn't working right now. Try again in a minute.</p>;
  if (!d) return null;
  const days = Math.round(d.days || 7);
  const co = d.company;
  const nothing = !d.stories?.length && !co;
  return (
    <div className={state.loading ? 'opacity-60' : ''}>
      {co?.guess && !d.stories?.length && (
        <p className="mt-4 text-sm text-slate-400">
          No stories mention “{d.q}” in the past {days} days. {co.ticker} is also a stock ticker ({shortName(co.name, true) || co.ticker}), so here it is in case you meant the company:
        </p>
      )}
      {co && (
        <div className="mt-4 rounded-2xl border border-slate-700 bg-slate-900/90 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="text-lg font-bold">{co.ticker}</div>
              <div className="text-xs text-slate-400 line-clamp-1">{shortName(co.name)}</div>
            </div>
            <div className="shrink-0 text-right leading-tight">
              {co.price != null && <div className="font-semibold tabular-nums">${Number(co.price).toLocaleString(undefined, { maximumFractionDigits: 2 })}</div>}
              <Pct v={co.change} day={co.change_day} vs={co.vs_market} />
            </div>
          </div>
          {d.headlines?.length > 0 && (
            <>
              <div className="mt-3 text-[11px] uppercase tracking-wider text-slate-500 font-semibold">Latest headlines about {co.ticker}</div>
              <ul className="mt-1.5 divide-y divide-slate-800 rounded-xl border border-slate-800 bg-slate-950/50">
                {d.headlines.map((h) => (
                  <li key={h.headline} className="px-3 py-2">
                    {h.url
                      ? <a href={h.url} target="_blank" rel="noopener noreferrer" className="text-sm leading-snug hover:text-blue-200">{h.headline}</a>
                      : <span className="text-sm leading-snug">{h.headline}</span>}
                    <div className="text-[11px] text-slate-500">{[h.source, ago(h.created_at)].filter(Boolean).join(' · ')}</div>
                  </li>
                ))}
              </ul>
            </>
          )}
          {!d.headlines?.length && <p className="mt-2 text-xs text-slate-500">No recent headlines about {co.ticker} from our news source.</p>}
          <div className="mt-3 grid grid-cols-2 gap-2">
            <button onClick={() => navigate(`/close-call?t=${encodeURIComponent(co.ticker)}`)} className="rounded-xl border border-slate-600 py-2.5 text-sm font-bold hover:bg-slate-800">
              Close Call on {co.ticker}
            </button>
            <button onClick={() => navigate(`/chat?b=${encodeURIComponent(`${shortName(co.name, true) || co.ticker} will `)}`)}
              className="rounded-xl bg-blue-600 hover:bg-blue-500 py-2.5 text-sm font-bold">
              Make a call on it →
            </button>
          </div>
        </div>
      )}

      {d.stories?.length > 0 && (
        <>
          <h2 className="mt-6 text-sm font-bold text-slate-300">
            {d.stories.length === 1 ? '1 story' : `${d.stories.length} stories`} from the past {days} days
          </h2>
          <div className="mt-2 space-y-3">
            {d.stories.map((it, i) => <MoverCard key={it.headline} item={it} i={i} />)}
          </div>
        </>
      )}
      {co && !co.guess && !d.stories?.length && (
        <p className="mt-4 text-sm text-slate-400">None of the stories we picked in the past {days} days move {co.ticker}.</p>
      )}

      {nothing && (
        <div className="mt-4 rounded-2xl border border-slate-700 bg-slate-900 p-4">
          <div className="font-semibold">No stories about “{d.q}” in the past {days} days</div>
          <p className="mt-1 text-sm text-slate-400">
            Search covers the stories on this page this week. Try a company's name or its ticker (like NVDA), or a broader word like “oil” or “chips”.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button onClick={() => navigate(`/chat?b=${encodeURIComponent(d.q)}`)} className="rounded-xl bg-blue-600 hover:bg-blue-500 px-4 py-2 text-sm font-bold">
              Ask about “{d.q.length > 24 ? d.q.slice(0, 24) + '…' : d.q}” →
            </button>
            <button onClick={() => setQ('')} className="rounded-xl border border-slate-600 px-4 py-2 text-sm font-bold">Back to today's news</button>
          </div>
        </div>
      )}
    </div>
  );
}
