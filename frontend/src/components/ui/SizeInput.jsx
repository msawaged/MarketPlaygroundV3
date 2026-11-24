// One sizing control for every trade ticket: a mode switch ($ / % of account, or % of position when trimming),
// a typed amount first, quick picks under it, and the parent's readout of what that size means.
import React, { useEffect, useState } from 'react';
import { getPortfolio } from '../../lib/api';
import { parseAmount } from '../../lib/sizing';

const MODE_LABEL = { usd: 'Dollars', pct: '% of account', pos: '% of position', n: 'Contracts' };

export default function SizeInput({ title = 'Size', modes = ['usd', 'pct'], mode, onMode, raw, onRaw, picks = {}, accent = 'blue', children }) {
  const on = accent === 'red' ? 'bg-red-600/90 border-red-400 text-white' : 'bg-blue-600 border-blue-400 text-white';
  const ring = accent === 'red' ? 'focus-within:border-red-400' : 'focus-within:border-blue-400';
  const isPct = mode === 'pct' || mode === 'pos';
  const quick = picks[mode] || [];
  return (
    <div>
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <span className="text-xs text-slate-400 shrink-0">{title}</span>
        <div className="flex rounded-lg bg-slate-800 p-0.5" role="tablist" aria-label={`${title} by`}>
          {modes.map((m) => (
            <button key={m} role="tab" aria-selected={mode === m} onClick={() => onMode(m)}
              className={`rounded-md px-2.5 py-1 text-[11px] font-bold whitespace-nowrap ${mode === m ? 'bg-slate-600 text-white' : 'text-slate-400'}`}>
              {MODE_LABEL[m]}
            </button>
          ))}
        </div>
      </div>
      <label className={`flex items-center gap-1 rounded-xl border border-slate-700 bg-slate-800/70 px-3 py-2.5 ${ring}`}>
        {mode === 'usd' && <span className="text-slate-400 font-bold text-lg">$</span>}
        <input type="text" inputMode="decimal" value={raw} placeholder="0"
          aria-label={`${title} in ${MODE_LABEL[mode].toLowerCase()}`}
          onChange={(e) => onRaw(e.target.value.replace(/[^0-9.,]/g, ''))}
          className="min-w-0 flex-1 bg-transparent text-xl font-extrabold text-white tabular-nums placeholder:text-slate-600 focus:outline-none" />
        {isPct && <span className="text-slate-400 font-bold text-lg">%</span>}
        {mode === 'n' && <span className="text-slate-400 text-sm">contracts</span>}
      </label>
      {quick.length > 0 && (
        <div className="mt-2 flex gap-1.5">
          {quick.map((q) => (
            <button key={q} onClick={() => onRaw(String(q))}
              className={`flex-1 rounded-lg py-1.5 text-xs font-bold border ${raw !== '' && Number(q) === parseAmount(raw) ? on : 'bg-slate-800 border-slate-700 text-slate-300'}`}>
              {isPct ? (Number(q) === 100 && mode === 'pos' ? 'All' : `${q}%`) : mode === 'n' ? q : `$${Number(q).toLocaleString()}`}
            </button>
          ))}
        </div>
      )}
      {children && <div className="mt-2 text-[11px] text-slate-400 leading-relaxed" aria-live="polite">{children}</div>}
    </div>
  );
}

/** The practice account's book for sizing: total value (NAV), spare cash, and what's held per ticker. */
export function useBook(enabled = true) {
  const [book, setBook] = useState(null);
  useEffect(() => {
    if (!enabled) return undefined;
    let live = true;
    getPortfolio().then((d) => {
      if (!live) return;
      const a = d?.account || {};
      const held = {};
      (d?.positions || []).forEach((p) => { if (p.position_type === 'long') held[p.ticker] = Number(p.quantity) || 0; });
      setBook({ value: Number(a.total_value) || 0, cash: Number(a.buying_power) || 0, held });
    }).catch(() => live && setBook({ error: true }));
    return () => { live = false; };
  }, [enabled]);
  return book;
}
