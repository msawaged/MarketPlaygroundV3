// "3 ways to trade it": every pick the v4 engine returns, each with its real
// trade, numbers, interactive profit/loss chart and investment sizing.
import React, { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import PayoffChart from './PayoffChart';
import { buildModel, sizePosition, scenarios, summarize, money } from '../../lib/payoff';
import { sendFeedback, paperTrade } from '../../lib/api';

const PLAIN = {
  'Buy Stock': 'Own the shares. You gain if the price rises; your risk is what you put in.',
  'Long Call': 'Buy the right to purchase shares at a set price. Big upside if it rises fast; you can lose the whole cost.',
  'Bull Call Spread': 'Buy a call and sell a higher one. Gains if it rises, with both the gain and the loss capped.',
  'Long Put': 'Buy the right to sell shares at a set price. Gains if it falls; you can lose the whole cost.',
  'Bear Put Spread': 'Buy a put and sell a lower one. Gains if it falls, with both the gain and the loss capped.',
  'Iron Condor': 'Collect a credit by betting the price stays in a range. Small capped gain, larger capped loss.',
  'Sell / Avoid': 'A way to act on the belief without a trade: avoid owning it, or trim if you already do.',
};

const AMOUNTS = [500, 1000, 2500, 5000];

function DirectionBadge({ direction }) {
  const bull = direction === 'bullish';
  return (
    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${bull ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400'}`}>
      {bull ? 'Bullish' : 'Bearish'}
    </span>
  );
}

function Stat({ label, value, tone }) {
  const color = tone === 'good' ? 'text-green-400' : tone === 'bad' ? 'text-red-400' : tone === 'warn' ? 'text-amber-300' : 'text-white';
  return (
    <div className="bg-slate-800/70 rounded-lg px-3 py-2 min-w-0">
      <div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div>
      <div className={`text-sm font-bold truncate ${color}`}>{value}</div>
    </div>
  );
}

export default function StrategyCard({ data, belief }) {
  const picks = (data.picks || []).filter((p) => p.shown).slice(0, 3);
  const [idx, setIdx] = useState(0);
  const [amount, setAmount] = useState(1000);
  const [status, setStatus] = useState({}); // pick_id -> 'up' | 'down' | 'traded' | 'tracking' | 'error:...'
  const [busy, setBusy] = useState(false);
  const pick = picks[idx];
  const interp = data.interpretation || {};

  const model = useMemo(() => (pick ? buildModel(pick.trade, pick.price) : null), [pick]);
  const sizing = useMemo(() => (model ? sizePosition(model, amount) : null), [model, amount]);
  const sum = useMemo(() => (model ? summarize(model) : null), [model]);
  const scen = useMemo(() => (model ? scenarios(model, amount) : []), [model, amount]);

  if (!pick) return null;
  const isOptions = model?.kind === 'options';
  const avoid = model?.kind === 'avoid';
  const legs = pick.trade?.trade_legs || [];
  const st = status[pick.pick_id];
  const track = pick.track_record;
  const fit = Math.max(0, Math.min(100, Math.round((pick.claude_score ?? pick.score ?? 0.5) * 100)));

  const feedback = (kind) => {
    setStatus((s) => ({ ...s, [pick.pick_id]: kind }));
    sendFeedback(data.belief_id, kind, pick.pick_id);
  };

  const doPaperTrade = async () => {
    if (isOptions || avoid) {
      feedback('executed');
      setStatus((s) => ({ ...s, [pick.pick_id]: 'tracking' }));
      return;
    }
    setBusy(true);
    try {
      const r = await paperTrade({
        ticker: pick.ticker, type: pick.trade.type, asset_class: 'equity',
        trade_legs: [{ action: 'Buy', ticker: pick.ticker }], investment_amount: amount,
      }, belief);
      if (r?.status === 'success') {
        sendFeedback(data.belief_id, 'executed', pick.pick_id);
        setStatus((s) => ({ ...s, [pick.pick_id]: 'traded' }));
      } else {
        setStatus((s) => ({ ...s, [pick.pick_id]: `error:${r?.message || 'The paper trade did not go through.'}` }));
      }
    } catch (e) {
      setStatus((s) => ({ ...s, [pick.pick_id]: `error:${e.message}` }));
    } finally {
      setBusy(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="mt-3 rounded-2xl border border-blue-500/30 bg-slate-900/95 overflow-hidden"
    >
      {/* Belief, as the engine understood it */}
      <div className="p-4 bg-gradient-to-br from-blue-600/25 via-slate-900 to-slate-900 border-b border-slate-800">
        <div className="text-[11px] uppercase tracking-wider text-blue-300 font-semibold">
          {picks.length} way{picks.length > 1 ? 's' : ''} to trade it
        </div>
        {interp.summary && <p className="mt-1 text-white font-semibold leading-snug">{interp.summary}</p>}
        {interp.causal_chain && <p className="mt-1 text-sm text-slate-300 leading-relaxed">{interp.causal_chain}</p>}
        <div className="mt-2 flex flex-wrap gap-1.5">
          {(interp.themes || []).map((t) => (
            <span key={t} className="text-[11px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">{t}</span>
          ))}
          {interp.horizon_days && (
            <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
              ~{interp.horizon_days >= 60 ? `${Math.round(interp.horizon_days / 30)} months` : `${interp.horizon_days} days`}
            </span>
          )}
        </div>
      </div>

      {/* Pick tabs */}
      <div className="flex gap-2 p-3 overflow-x-auto" role="tablist" aria-label="Trade ideas">
        {picks.map((p, i) => (
          <button
            key={p.pick_id}
            role="tab"
            aria-selected={i === idx}
            onClick={() => setIdx(i)}
            className={`shrink-0 text-left rounded-xl px-3 py-2 border transition-colors ${
              i === idx ? 'bg-blue-600 border-blue-400 text-white' : 'bg-slate-800 border-slate-700 text-slate-300 hover:border-slate-500'
            }`}
          >
            <div className="text-sm font-bold">{p.ticker}</div>
            <div className={`text-[11px] ${i === idx ? 'text-blue-100' : 'text-slate-400'}`}>{p.structure}</div>
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={pick.pick_id}
          initial={{ opacity: 0, x: 12 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -12 }}
          transition={{ duration: 0.2 }}
          className="px-4 pb-4 space-y-4"
        >
          {/* Pick header */}
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-2xl font-extrabold text-white">{pick.ticker}</span>
                <DirectionBadge direction={pick.direction} />
              </div>
              <div className="text-sm text-slate-400 truncate">{pick.name}</div>
            </div>
            <div className="text-right shrink-0">
              <div className="text-xl font-bold text-white">${Number(pick.price).toFixed(2)}</div>
              <div className="text-[11px] text-slate-500">last price</div>
            </div>
          </div>

          <p className="text-sm text-slate-300 leading-relaxed"><span className="text-slate-400">Why: </span>{pick.rationale}</p>

          {/* Fit + track record */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs text-slate-400">
              <span>Fit with your belief</span><span className="text-slate-200 font-semibold">{fit}%</span>
            </div>
            <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
              <div className="h-full bg-blue-500" style={{ width: `${fit}%` }} />
            </div>
            {track && track.n > 0 && (
              <p className="text-xs text-slate-400">
                Track record on this theme: beat the S&amp;P 500 in {Math.round(track.hit * 100)}% of {track.n} past picks
                ({track.mean >= 0 ? '+' : ''}{(track.mean * 100).toFixed(1)}% on average after 30 days).
              </p>
            )}
          </div>

          {/* Strategy */}
          <div className="rounded-xl bg-slate-800/60 border border-slate-700 p-3">
            <div className="flex items-center justify-between">
              <div className="font-bold text-white">{pick.structure}</div>
              {pick.trade?.expiration && <div className="text-xs text-slate-400">Expires {pick.trade.expiration}</div>}
            </div>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">{PLAIN[pick.structure] || ''}</p>
            {legs.length > 0 && (
              <ul className="mt-2 space-y-1">
                {legs.map((l, i) => (
                  <li key={i} className="flex justify-between text-sm">
                    <span><span className={l.action === 'Sell' ? 'text-red-300' : 'text-green-300'}>{l.action}</span> <span className="text-white">{l.ticker}</span>{l.option_type ? ` ${l.option_type}` : ''}</span>
                    {l.strike_price ? <span className="text-slate-300">${l.strike_price} strike{l.est_premium ? ` · ~$${l.est_premium}` : ''}</span> : <span className="text-slate-500">{l.instrument === 'stock' ? 'shares' : ''}</span>}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {!avoid && sum && (
            <>
              <div className="grid grid-cols-3 gap-2">
                <Stat label={isOptions ? 'Cost / contract' : 'Price'} value={isOptions ? money(model.capitalPerUnit) : `$${Number(pick.price).toFixed(2)}`} />
                <Stat label="Max gain" value={isOptions ? money(sum.maxProfit) : 'Unlimited'} tone="good" />
                <Stat label="Breakeven" value={sum.breakevens.length ? sum.breakevens.map((b) => `$${b.toFixed(2)}`).join(' / ') : '—'} tone="warn" />
              </div>
              {isOptions && (
                <p className="text-[11px] text-slate-500 -mt-2">Per contract (100 shares). Max loss per contract: {money(Math.abs(sum.maxLoss))}.</p>
              )}

              {/* Investment */}
              <div>
                <div className="text-xs text-slate-400 mb-1.5">If you put in</div>
                <div className="grid grid-cols-4 gap-2">
                  {AMOUNTS.map((a) => (
                    <button
                      key={a}
                      onClick={() => setAmount(a)}
                      className={`rounded-lg py-2 text-sm font-bold border ${a === amount ? 'bg-blue-600 border-blue-400 text-white' : 'bg-slate-800 border-slate-700 text-slate-200 hover:border-slate-500'}`}
                    >
                      ${a.toLocaleString()}
                    </button>
                  ))}
                </div>
                {sizing?.note && <p className="text-[11px] text-slate-500 mt-1.5">{sizing.note}</p>}
              </div>

              <PayoffChart
                key={pick.pick_id}
                model={model}
                units={sizing?.units || 1}
                ticker={pick.ticker}
                sizeLabel={isOptions ? `${sizing.units} contract${sizing.units > 1 ? 's' : ''}` : `$${amount.toLocaleString()} of shares`}
              />

              {/* Scenarios */}
              <div className="grid grid-cols-3 gap-2">
                {scen.map((s) => (
                  <div key={s.label} className={`rounded-lg p-2 text-center border ${s.pnl >= 0 ? 'bg-green-500/10 border-green-500/30' : 'bg-red-500/10 border-red-500/30'}`}>
                    <div className="text-[11px] text-slate-400">{pick.ticker} {s.label.toLowerCase()}</div>
                    <div className={`text-base font-bold ${s.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>{money(s.pnl, { sign: true })}</div>
                    {s.cost > 0 && <div className="text-[10px] text-slate-500">{s.pnl >= 0 ? '+' : ''}{Math.round((s.pnl / s.cost) * 100)}% of cost</div>}
                  </div>
                ))}
              </div>
              <p className="text-[11px] text-slate-500 -mt-2">{isOptions ? 'At expiration.' : 'Price moves at any point you sell.'} Estimates, before fees.</p>
            </>
          )}

          {/* Actions */}
          <div className="grid grid-cols-3 gap-2">
            <button
              onClick={() => feedback('up')}
              aria-pressed={st === 'up'}
              className={`rounded-lg py-3 text-sm font-bold border ${st === 'up' ? 'bg-green-600 border-green-400 text-white' : 'bg-slate-800 border-slate-700 text-slate-200 hover:border-slate-500'}`}
            >
              👍 Good pick
            </button>
            <button
              onClick={() => feedback('down')}
              aria-pressed={st === 'down'}
              className={`rounded-lg py-3 text-sm font-bold border ${st === 'down' ? 'bg-red-600 border-red-400 text-white' : 'bg-slate-800 border-slate-700 text-slate-200 hover:border-slate-500'}`}
            >
              👎 Not for me
            </button>
            <button
              onClick={doPaperTrade}
              disabled={busy || st === 'traded' || st === 'tracking'}
              className="rounded-lg py-3 text-sm font-bold bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-60"
            >
              {busy ? 'Placing…' : st === 'traded' ? 'Paper traded' : st === 'tracking' ? 'Tracking' : isOptions || avoid ? 'Track it' : 'Paper trade'}
            </button>
          </div>
          {st === 'up' && <p className="text-xs text-green-400">Thanks. Your vote helps everyone get better picks.</p>}
          {st === 'down' && <p className="text-xs text-slate-400">Got it. We'll show picks like this less often.</p>}
          {st === 'traded' && <p className="text-xs text-blue-300">Added ${amount.toLocaleString()} of {pick.ticker} to your practice portfolio. No real money.</p>}
          {st === 'tracking' && <p className="text-xs text-blue-300">We'll grade this idea against the market at 1 week, 1 month and 3 months.</p>}
          {st?.startsWith?.('error:') && <p className="text-xs text-red-400">{st.slice(6)}</p>}
        </motion.div>
      </AnimatePresence>

      <div className="px-4 py-3 bg-slate-950/60 border-t border-slate-800 text-[11px] text-slate-500 leading-relaxed">
        Ideas for education, not investment advice. Prices are delayed; option prices are estimates. Trading involves risk, including loss of what you invest.
      </div>
    </motion.div>
  );
}
