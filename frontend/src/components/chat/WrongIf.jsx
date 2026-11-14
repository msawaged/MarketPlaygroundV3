// "I'm wrong if...": the user's own one-line pre-mortem for a call, with an optional price line on one pick.
// Shown back on My beliefs next to how the call is doing. Information only: nothing trades when a line is crossed.
import React, { useState } from 'react';
import { saveWrongIf } from '../../lib/api';

const MAX = 140;

// Same wording as the card's horizon ("~3 months", "~12 months"), so the pre-mortem looks ahead as far as the call does.
function horizonText(days) {
  const d = Number(days) || 0;
  if (d <= 0) return null;
  return d >= 60 ? `${Math.round(d / 30)} months` : `${d} days`;
}

export default function WrongIf({ beliefId, picks = [], horizonDays = null, initial = null, compact = false, inChat = false, onSaved, onCancel }) {
  const lineable = picks.filter((p) => (p.direction === 'bullish' || p.direction === 'bearish') && Number(p.price || p.entry_price) > 0);
  const [open, setOpen] = useState(!compact);
  const [text, setText] = useState(initial?.text || '');
  const [ticker, setTicker] = useState(initial?.ticker || lineable[0]?.ticker || '');
  const [price, setPrice] = useState(initial?.price != null ? String(initial.price) : '');
  const [state, setState] = useState({ saving: false, error: null, saved: initial || null });

  const pick = lineable.find((p) => p.ticker === ticker);
  const entry = pick ? Number(pick.price || pick.entry_price) : null;
  const below = pick?.direction === 'bullish';

  const starters = [];
  if (pick) {
    const px = (entry * (below ? 0.9 : 1.1)).toFixed(2);
    starters.push({ label: `${pick.ticker} closes ${below ? 'below' : 'above'} $${px}`, apply: () => setPrice(px) });
  }
  starters.push({ label: 'it trails the S&P by 5%+ in 30 days', apply: () => setText('it trails the S&P 500 by more than 5% in 30 days') });

  async function save() {
    setState((s) => ({ ...s, saving: true, error: null }));
    try {
      const r = await saveWrongIf(beliefId, { text: text.trim() || null, price: price ? Number(price) : null, ticker: price ? ticker : null });
      setState({ saving: false, error: null, saved: r.wrong_if });
      setOpen(false);
      onSaved?.(r.wrong_if);
    } catch (e) {
      setState((s) => ({ ...s, saving: false, error: e.message }));
    }
  }

  if (!beliefId) return null;

  if (state.saved && !open) {
    return (
      <div className="mt-3 rounded-2xl border border-amber-400/30 bg-amber-500/10 px-3 py-2.5 text-sm">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-amber-200">You said you'd be wrong if</div>
            {state.saved.text && <div className="text-slate-100 break-words">{state.saved.text}</div>}
            {state.saved.price != null && (
              <div className="text-slate-200">{state.saved.ticker} closes {(lineable.find((p) => p.ticker === state.saved.ticker)?.direction || state.saved.direction) === 'bearish' ? 'above' : 'below'} ${Number(state.saved.price).toFixed(2)}</div>
            )}
          </div>
          <button onClick={() => setOpen(true)} className="shrink-0 text-xs font-semibold text-amber-200 hover:text-white">Edit</button>
        </div>
        {inChat && <div className="mt-1 text-[11px] text-slate-400">Saved. My beliefs shows it next to how the call does.</div>}
      </div>
    );
  }

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className={inChat ? 'mt-3 w-full text-left rounded-2xl border border-dashed border-slate-600 px-3 py-2.5 hover:border-amber-300' : 'mt-3 text-xs font-semibold text-amber-200 hover:text-white'}>
        {inChat ? (
          <>
            <div className="text-sm font-semibold text-amber-200">+ I'm wrong if…</div>
            <div className="text-xs text-slate-400">Optional: write down what would prove this call wrong. We'll show it back as it plays out.</div>
          </>
        ) : "+ I'm wrong if…"}
      </button>
    );
  }

  return (
    <div className="mt-3 rounded-2xl border border-slate-700 bg-slate-900/80 p-3">
      <div className="font-bold text-sm">I'm wrong if…</div>
      <p className="mt-0.5 text-xs text-slate-400">{horizonText(horizonDays) ? `Imagine it's ${horizonText(horizonDays)} from now and this call lost.` : 'Imagine this call lost.'} Why? Write it down now and check it later. Optional.</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {starters.map((s) => (
          <button key={s.label} type="button" onClick={s.apply} className="text-[11px] px-2.5 py-1 rounded-full bg-slate-800 border border-slate-700 text-slate-200 hover:border-amber-300">…{s.label}</button>
        ))}
      </div>
      <label className="mt-2 block">
        <span className="sr-only">I'm wrong if</span>
        <input value={text} onChange={(e) => setText(e.target.value.slice(0, MAX))} maxLength={MAX} placeholder="…new home sales keep falling"
          className="w-full rounded-xl bg-slate-800 border border-slate-700 px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-amber-300" />
      </label>
      <div className="mt-0.5 text-right text-[10px] text-slate-500">{text.length}/{MAX}</div>
      {lineable.length > 0 && (
        <div className="mt-1 flex items-center gap-2 text-xs text-slate-300 flex-wrap">
          <span>Price line (optional):</span>
          {lineable.length > 1 ? (
            <select value={ticker} onChange={(e) => { setTicker(e.target.value); setPrice(''); }} className="rounded-lg bg-slate-800 border border-slate-700 px-2 py-1 text-white">
              {lineable.map((p) => <option key={p.ticker} value={p.ticker}>{p.ticker}</option>)}
            </select>
          ) : <span className="font-semibold text-white">{ticker}</span>}
          <span className="inline-flex items-center gap-1 whitespace-nowrap">closes {below ? 'below' : 'above'} $
          <input value={price} onChange={(e) => setPrice(e.target.value.replace(/[^0-9.]/g, ''))} inputMode="decimal" placeholder={entry ? (entry * (below ? 0.9 : 1.1)).toFixed(2) : ''}
            className="w-20 rounded-lg bg-slate-800 border border-slate-700 px-2 py-1 text-white placeholder-slate-500 focus:outline-none focus:border-amber-300" aria-label="Price line" /></span>
          {entry && <span className="text-slate-500">({inChat ? 'now' : 'at the call'} ${entry.toFixed(2)})</span>}
        </div>
      )}
      {state.error && <div className="mt-2 text-xs text-red-300">{state.error}</div>}
      <div className="mt-3 flex items-center gap-3">
        <button onClick={save} disabled={state.saving || (!text.trim() && !price)} className="rounded-xl bg-amber-500 text-slate-950 font-bold text-sm px-4 py-2 disabled:opacity-40">{state.saving ? 'Saving…' : 'Save'}</button>
        <button onClick={() => (onCancel ? onCancel() : setOpen(false))} className="text-xs text-slate-400 hover:text-white">{state.saved ? 'Cancel' : 'Skip'}</button>
      </div>
      <p className="mt-2 text-[10px] text-slate-500">Your own test of your idea, not advice. Nothing trades if a line is crossed.</p>
    </div>
  );
}
