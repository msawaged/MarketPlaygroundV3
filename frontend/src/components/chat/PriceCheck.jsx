// "Price check" for an option idea: fair vs put-call parity, cheap or expensive vs how much the stock moves,
// and what it costs to trade. Loads on tap (live quotes), one block per option leg.
import React, { useState } from 'react';
import { request } from '../../lib/api';
import { niceDate } from '../../lib/payoff';

const TONE = { cheap: 'text-green-300', normal: 'text-slate-100', expensive: 'text-amber-300', unknown: 'text-slate-300' };

const usd = (x) => `$${Math.abs(x).toFixed(2)}`;

// The whole trade per share, three ways: the card's estimate, the listed mids, and the natural price (pay the ask
// on buys, get the bid on sells). Only when every option leg was checked against its own listed contract.
function wholeTrade(opts, res) {
  if (opts.length < 2 || res.some((r) => !r.available || !r.card?.same_contract || !r.card.mid)) return null;
  let card = 0, mid = 0, nat = 0;
  opts.forEach((l, i) => {
    const s = l.action === 'Sell' ? -1 : 1, q = Number(l.quantity) || 1, r = res[i];
    card += s * q * Number(l.est_premium); mid += s * q * r.mid; nat += s * q * (s > 0 ? r.ask : r.bid);
  });
  return { card, mid, nat };
}

export default function PriceCheck({ ticker, legs, pickId, trade, spot }) {
  const all = (legs || []).filter((l) => l.option_type && l.strike_price && l.expiration);
  const opts = all.slice(0, 2);
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  if (!opts.length) return null;

  const run = async () => {
    setBusy(true);
    try {
      setRes(await Promise.all(opts.map((l) => request(`/v4/price_check?${new URLSearchParams({
        underlying: ticker, option_type: String(l.option_type).toLowerCase(), strike: l.strike_price,
        expiration: String(l.expiration).slice(0, 10), ...(pickId ? { pick_id: pickId } : {}),
        ...(Number(l.est_premium) > 0 ? {
          card_premium: l.est_premium, ...(trade?.vol ? { card_vol: trade.vol } : {}),
          ...(trade?.vol_source ? { card_vol_source: trade.vol_source } : {}), ...(spot ? { card_spot: spot } : {}),
        } : {}),
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
              <div className="text-xs text-slate-400">{opts.length > 1 ? `${opts[i].action || ''} ` : ''}{r.underlying} ${r.strike} {r.type} · {niceDate(r.expiration)}</div>
              {(Math.abs(Number(r.strike) - Number(opts[i].strike_price)) > 0.001 || r.expiration !== String(opts[i].expiration).slice(0, 10)) && (
                <div className="text-[11px] text-slate-500">Closest listed contract to the idea's ${Number(opts[i].strike_price)} · {niceDate(String(opts[i].expiration).slice(0, 10))}</div>
              )}
              <div className={`mt-0.5 font-bold ${TONE[r.vol_verdict]}`}>{r.headline}</div>
              {r.card && (
                <div className="mt-1.5 rounded-xl bg-slate-800/60 px-3 py-2">
                  <div className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">Card vs listed</div>
                  <div className="mt-0.5 text-sm tabular-nums">
                    <span className="text-slate-300">Card {usd(r.card.premium)}</span>
                    {r.card.same_contract && r.card.mid ? <span className="text-slate-400"> · listed mid {usd(r.card.mid)}</span> : null}
                  </div>
                  <p className={`mt-1 text-xs leading-snug ${r.card.in_spread === false && Math.abs(r.card.diff_pct || 0) >= 0.1 ? 'text-amber-200' : 'text-slate-400'}`}>{r.card.text}</p>
                </div>
              )}
              <ul className="mt-1.5 space-y-1.5 text-sm text-slate-300 leading-snug">
                {r.lines.map((t) => <li key={t}>{t}</li>)}
              </ul>
              {(i === res.length - 1 || r.note !== res[res.length - 1].note) && (
                <p className="mt-2 text-[11px] text-slate-500 leading-snug">{r.note}</p>
              )}
            </>
          )}
        </div>
      ))}
      {res && (() => {
        const w = opts.length === all.length ? wholeTrade(opts, res) : null;
        if (!w) return null;
        const word = (x) => (x >= 0 ? `costs ${usd(x)}` : `brings in ${usd(x)}`);
        return (
          <div className="mt-3 pt-3 border-t border-slate-800 text-sm">
            <div className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">Whole trade, per share</div>
            <ul className="mt-1 space-y-0.5 text-slate-300 tabular-nums">
              <li>Card estimate: {word(w.card)}</li>
              <li>At listed mids: {word(w.mid)}</li>
              <li>Buying at the ask, selling at the bid: {word(w.nat)}</li>
            </ul>
            <p className="mt-1 text-[11px] text-slate-500">Times 100 per contract. A limit order between the last two is usual; the card and its payoff use the estimate.</p>
          </div>
        );
      })()}
    </div>
  );
}
