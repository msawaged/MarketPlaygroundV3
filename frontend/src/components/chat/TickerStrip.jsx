// Scrolling live-price strip. Tap "Edit" to add or remove tickers.
// Uses a CSS animation instead of re-rendering every frame.
import React, { useEffect, useRef, useState } from 'react';
import { getTickerPrices, searchTickers } from '../../lib/api';

const KEY = 'mp_elite_symbols';
const DEFAULTS = ['SPY', 'QQQ', 'AAPL', 'NVDA', 'TSLA'];

function loadSymbols() {
  try {
    const s = JSON.parse(localStorage.getItem(KEY) || 'null');
    return Array.isArray(s) && s.length ? s : DEFAULTS;
  } catch { return DEFAULTS; }
}

export default function TickerStrip() {
  const [symbols, setSymbols] = useState(loadSymbols);
  const [rows, setRows] = useState([]);
  const [editing, setEditing] = useState(false);
  const [q, setQ] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const abortRef = useRef(null);

  useEffect(() => { try { localStorage.setItem(KEY, JSON.stringify(symbols)); } catch { /* private mode */ } }, [symbols]);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      if (!symbols.length) { setRows([]); return; }
      try {
        const data = await getTickerPrices(symbols);
        const list = Array.isArray(data) ? data : Object.entries(data || {}).map(([symbol, v]) => ({ symbol, ...v }));
        const bySym = Object.fromEntries(list.filter((r) => r && r.symbol).map((r) => [r.symbol, r]));
        if (alive) setRows(symbols.map((s) => bySym[s]).filter(Boolean));
      } catch { /* keep last prices */ }
    };
    load();
    const id = setInterval(load, 30000);
    return () => { alive = false; clearInterval(id); };
  }, [symbols]);

  useEffect(() => {
    const term = q.trim();
    if (!term) { setSuggestions([]); return; }
    const id = setTimeout(async () => {
      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      try {
        const s = await searchTickers(term, ctrl.signal);
        setSuggestions(Array.isArray(s) ? s.slice(0, 8) : []);
      } catch { setSuggestions([]); }
    }, 250);
    return () => clearTimeout(id);
  }, [q]);

  const add = (sym) => {
    const S = String(sym || '').toUpperCase().trim();
    if (/^[A-Z0-9.\-]{1,6}$/.test(S) && !symbols.includes(S)) setSymbols((p) => [...p, S]);
    setQ(''); setSuggestions([]);
  };
  const remove = (sym) => setSymbols((p) => p.filter((s) => s !== sym));

  const items = rows.length ? [...rows, ...rows] : [];
  const duration = Math.max(20, rows.length * 6);

  return (
    <div className="relative bg-slate-950/95 border-b border-slate-800 text-white">
      <style>{`@keyframes mp-marquee{from{transform:translateX(0)}to{transform:translateX(-50%)}}
        @media (prefers-reduced-motion: reduce){.mp-marquee{animation:none!important}}`}</style>
      <div className="flex items-center">
        <div className="flex-1 overflow-hidden py-2">
          {items.length ? (
            <div className="mp-marquee flex w-max gap-8 px-3 whitespace-nowrap" style={{ animation: `mp-marquee ${duration}s linear infinite` }}>
              {items.map((r, i) => {
                const up = (r.change ?? 0) >= 0;
                return (
                  <span key={`${r.symbol}-${i}`} className="inline-flex items-center gap-2 text-sm">
                    <span className="font-bold text-blue-400">{r.symbol}</span>
                    <span className="font-semibold">{r.price != null ? `$${Number(r.price).toLocaleString(undefined, { maximumFractionDigits: 2 })}` : '—'}</span>
                    {r.changePercent != null && (
                      <span className={up ? 'text-green-400' : 'text-red-400'}>{up ? '▲' : '▼'} {Math.abs(Number(r.changePercent)).toFixed(2)}%</span>
                    )}
                  </span>
                );
              })}
            </div>
          ) : (
            <div className="px-3 text-xs text-slate-500">Live prices appear here</div>
          )}
        </div>
        <button onClick={() => setEditing(true)} className="shrink-0 px-3 py-2 text-xs text-slate-300 hover:text-white border-l border-slate-800">
          Edit
        </button>
      </div>

      {editing && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4" onClick={() => setEditing(false)}>
          <div className="bg-slate-800 rounded-xl p-4 w-full max-w-sm max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold mb-3">Your tickers</h3>
            <label className="block text-xs text-slate-400 mb-1" htmlFor="ticker-search">Add a ticker</label>
            <input
              id="ticker-search" value={q} onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') add(q); }}
              placeholder="Search, e.g. AAPL"
              className="w-full mb-2 bg-slate-700 border border-slate-600 rounded px-3 py-2 text-sm text-white placeholder-slate-400"
            />
            {suggestions.length > 0 && (
              <div className="mb-3 bg-slate-700 border border-slate-600 rounded">
                {suggestions.map((s) => (
                  <button key={s} onClick={() => add(s)} className="block w-full text-left px-3 py-2 hover:bg-slate-600 text-sm">{s}</button>
                ))}
              </div>
            )}
            <div className="space-y-2 mb-3">
              {symbols.map((s) => (
                <div key={s} className="flex items-center justify-between bg-slate-700 px-3 py-2 rounded">
                  <span>{s}</span>
                  <button onClick={() => remove(s)} className="text-sm text-red-300 hover:text-red-200">Remove</button>
                </div>
              ))}
            </div>
            <button onClick={() => setEditing(false)} className="w-full px-3 py-2 bg-blue-600 hover:bg-blue-500 rounded text-sm font-semibold">Done</button>
          </div>
        </div>
      )}
    </div>
  );
}
