// "Price check" for an option idea: fair vs put-call parity, cheap or expensive vs how much the stock moves,
// and what it costs to trade. Loads on tap (live quotes), one block per option leg.
import React, { useState } from 'react';
import { request } from '../../lib/api';

const TONE = { cheap: 'text-green-300', normal: 'text-slate-100', expensive: 'text-amber-300', unknown: 'text-slate-300' };

export default function PriceCheck({ ticker, legs, pickId }) {
  const opts = (legs || []).filter((l) => l.option_type && l.strike_price && l.expiration).slice(0, 2);
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  if (!opts.length) return null;

  const run = async () => {
    setBusy(true);
    try {
      setRes(await Promise.all(opts.map((l) => request(`/v4/price_check?${new URLSearchParams({
        underlying: ticker, option_type: String(l.option_type).toLowerCase(), strike: l.strike_price,
        expiration: String(l.expiration).slice(0, 10), ...(pickId ? { pick_id: pickId } : {}),
      })}`).catch((e) => ({ available: false, reason: e.message })))));
    } finally { setBusy(false); }
  };

  return (
    <div className="rounded-2xl border border-slate-700 bg-slate-950/40 p-3.5">
      <div className="flex items-center justify-between gap-2">
        <div className="text-[11px] uppercase tracking-wider text-slate-300 font-semibold">Price check</div>
        {!res && (
          <button onClick={run} disabled={busy} className="rounded-xl border border-slate-600 px-3 py-1.5 text-xs font-bold hover:border-blue-300 disabled:opacity-50">
            {busy ? 'Checking live prices…' : 'Is this a fair price?'}
          </button>
        )}
      </div>
      {res && res.map((r, i) => (
        <div key={i} className={i ? 'mt-3 pt-3 border-t border-slate-800' : 'mt-2'}>
          {!r.available ? <p className="text-sm text-slate-400">{r.reason}</p> : (
            <>
              <div className="text-xs text-slate-400">{opts.length > 1 ? `${opts[i].action || ''} ` : ''}{r.underlying} ${r.strike} {r.type} · {r.expiration}</div>
              <div className={`mt-0.5 font-bold ${TONE[r.vol_verdict]}`}>{r.headline}</div>
              <ul className="mt-1.5 space-y-1.5 text-sm text-slate-300 leading-snug">
                {r.lines.map((t) => <li key={t}>{t}</li>)}
              </ul>
              <p className="mt-2 text-[11px] text-slate-500 leading-snug">{r.note}</p>
            </>
          )}
        </div>
      ))}
    </div>
  );
}
