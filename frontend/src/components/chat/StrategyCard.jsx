// "3 ways to trade it": every pick the v4 engine returns, each with its real
// trade, numbers, interactive profit/loss chart and investment sizing.
import React, { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import PayoffChart from './PayoffChart';
import { useNavigate } from 'react-router-dom';
import { buildModel, sizePosition, scenarios, summarize, money, plainEnglish, niceDate } from '../../lib/payoff';
import { sendFeedback, paperTrade, paperTradeOptions } from '../../lib/api';
import Term from '../ui/Term';
import ReplayPanel from './ReplayPanel';
import { shareCard } from '../../lib/shareCard';
import { useBroker } from '../../lib/broker';
import RealMoneySheet from './RealMoneySheet';
import StrategyGuide from './StrategyGuide';

const PLAIN = {
  'Buy Stock': 'Own the shares. You gain if the price rises; your risk is what you put in.',
  'Long Call': 'Buy the right to purchase shares at a set price. Big upside if it rises fast; you can lose the whole cost.',
  'Bull Call Spread': 'Buy a call and sell a higher one. Gains if it rises, with both the gain and the loss capped.',
  'Long Put': 'Buy the right to sell shares at a set price. Gains if it falls; you can lose the whole cost.',
  'Bear Put Spread': 'Buy a put and sell a lower one. Gains if it falls, with both the gain and the loss capped.',
  'Iron Condor': 'Collect a credit by betting the price stays in a range. Small capped gain, larger capped loss.',
  'Long Straddle': 'Buy a call and a put at the same price. You win if it makes a big move either way; you lose if it barely moves.',
  'Long Strangle': 'Buy a call above and a put below today\'s price. Cheaper than a straddle, but it needs an even bigger move either way.',
  'Sell / Avoid': 'A way to act on the belief without a trade: avoid owning it, or trim if you already do.',
};

const AMOUNTS = [500, 1000, 2500, 5000];
const MAX_AMOUNT = 100000; // the practice account starts with $100,000
const TERM_FOR = { 'Per contract': 'contract', 'Max gain': 'max gain', Breakeven: 'breakeven' };

function DirectionBadge({ direction }) {
  const bull = direction === 'bullish';
  if (direction === 'volatile') {
    return (
      <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-violet-500/15 text-violet-300">
        <Term k="big move">Big move</Term>
      </span>
    );
  }
  return (
    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${bull ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400'}`}>
      <Term k={bull ? 'bullish' : 'bearish'}>{bull ? 'Bullish' : 'Bearish'}</Term>
    </span>
  );
}

const TONE = {
  neutral: 'text-slate-200',
  good: 'text-green-300',
  bad: 'text-red-300',
  warn: 'text-amber-200',
};
const DOT = { neutral: 'bg-slate-400', good: 'bg-green-400', bad: 'bg-red-400', warn: 'bg-amber-300' };

const RISK_NEXT = {
  conservative: { bolder: 'moderate' },
  moderate: { safer: 'conservative', bolder: 'aggressive' },
  aggressive: { safer: 'moderate' },
};

function Stat({ label, value, tone }) {
  const color = tone === 'good' ? 'text-green-400' : tone === 'bad' ? 'text-red-400' : tone === 'warn' ? 'text-amber-300' : 'text-white';
  return (
    <div className="bg-slate-800/70 rounded-lg px-3 py-2 min-w-0">
      <div className="text-[11px] uppercase tracking-wide text-slate-400">{TERM_FOR[label] ? <Term k={TERM_FOR[label]}>{label}</Term> : label}</div>
      <div className={`text-sm font-bold truncate ${color}`}>{value}</div>
    </div>
  );
}

const FAMILY_SHARES = new Set(['Buy Stock', 'Sell / Avoid']);
const kindLabel = (s) => (s === 'Buy Stock' ? 'Shares' : s === 'Sell / Avoid' ? 'Stay out' : 'Options');

export default function StrategyCard({ data, belief, riskProfile = 'moderate', onRerun, onRefine, prefs, onTune }) {
  const navigate = useNavigate();
  const [shared, setShared] = useState(null);
  const [replay, setReplay] = useState(null);
  const broker = useBroker();
  const [realOpen, setRealOpen] = useState(false);
  const picks = (data.picks || []).filter((p) => p.shown).slice(0, 3);
  const [idx, setIdx] = useState(0);
  const [amount, setAmount] = useState(1000);
  const [custom, setCustom] = useState('');
  const [status, setStatus] = useState({}); // pick_id -> 'up' | 'down' | 'traded' | 'tracking' | 'error:...'
  const [busy, setBusy] = useState(false);
  const [useAlt, setUseAlt] = useState({}); // pick_id -> true when showing the other version
  const basePick = picks[idx];
  const pick = basePick && useAlt[basePick.pick_id] && basePick.alt
    ? { ...basePick, structure: basePick.alt.structure, trade: basePick.alt.trade, structure_reason: '' }
    : basePick;
  const interp = data.interpretation || {};

  const model = useMemo(() => (pick ? buildModel(pick.trade, pick.price) : null), [pick]);
  const sizing = useMemo(() => (model ? sizePosition(model, amount) : null), [model, amount]);
  const sum = useMemo(() => (model ? summarize(model) : null), [model]);
  const scen = useMemo(() => (model ? scenarios(model, amount) : []), [model, amount]);
  const plain = useMemo(
    () => (model && sum ? plainEnglish(model, sum, sizing?.units || 1, pick?.ticker, amount) : []),
    [model, sum, sizing, pick, amount]
  );

  if (!pick) return null;
  const isOptions = model?.kind === 'options';
  const avoid = model?.kind === 'avoid';
  const legs = pick.trade?.trade_legs || [];
  const skey = `${pick.pick_id}${useAlt[pick.pick_id] && basePick.alt ? ':alt' : ''}`;
  const st = status[skey];
  const track = pick.track_record;
  const fit = Math.max(0, Math.min(100, Math.round((pick.claude_score ?? pick.score ?? 0.5) * 100)));

  const feedback = (kind) => {
    setStatus((s) => ({ ...s, [skey]: kind }));
    sendFeedback(data.belief_id, kind, pick.pick_id);
  };

  const share = async () => {
    const url = `${window.location.origin}/chat?b=${encodeURIComponent(belief || '')}`;
    const pctTxt = (v) => `${v >= 0 ? '+' : ''}${(v * 100).toFixed(1)}%`;
    const card = replay ? {
      kicker: 'If I\u2019d believed this a year ago', belief,
      headline: `My picks ${pctTxt(replay.basket_return)} vs S&P 500 ${pctTxt(replay.spy_return)}`,
      good: replay.belief_right,
      picks: replay.picks.map((p) => ({ ticker: p.ticker, label: 'past 12 months', value: pctTxt(p.return), good: p.right })),
      url: `${window.location.host}`,
    } : {
      kicker: 'My belief', belief, headline: `${picks.length} ways to trade it`,
      picks: picks.map((p) => ({ ticker: p.ticker, label: p.structure, value: `${Math.round((p.claude_score ?? 0.5) * 100)}% fit`, good: null })),
      url: `${window.location.host}`,
    };
    setShared('making');
    try {
      const how = await shareCard(card, `My belief: "${belief}" ${url}`);
      setShared(how === 'downloaded' ? 'saved' : null);
      if (how === 'downloaded') setTimeout(() => setShared(null), 2500);
    } catch {
      try { await navigator.clipboard.writeText(url); setShared('copied'); setTimeout(() => setShared(null), 2500); } catch { setShared(null); }
    }
  };
  const next = RISK_NEXT[riskProfile] || RISK_NEXT.moderate;

  const doPaperTrade = async () => {
    if (avoid) {
      feedback('executed');
      setStatus((s) => ({ ...s, [skey]: 'tracking' }));
      return;
    }
    if (isOptions) {
      if (sizing?.over) {
        setStatus((s) => ({ ...s, [skey]: `error:One contract costs about $${Math.round(sizing.per).toLocaleString()}. Raise the amount or switch to shares.` }));
        return;
      }
      setBusy(true);
      try {
        const r = await paperTradeOptions({ ticker: pick.ticker, structure: pick.structure, trade_legs: legs, contracts: Math.min(1000, sizing?.units || 1), belief });
        if (r?.status === 'success') {
          sendFeedback(data.belief_id, 'executed', pick.pick_id);
          setStatus((s) => ({ ...s, [skey]: `opt:${r.message}` }));
        } else {
          setStatus((s) => ({ ...s, [skey]: `error:${r?.message || 'The practice trade did not go through.'}` }));
        }
      } catch (e) {
        setStatus((s) => ({ ...s, [skey]: `error:${e.message}` }));
      } finally {
        setBusy(false);
      }
      return;
    }
    setBusy(true);
    try {
      const r = await paperTrade({
        ticker: pick.ticker, type: pick.trade.type, asset_class: 'equity',
        trade_legs: [{ action: 'Buy', ticker: pick.ticker }], investment_amount: amount,
      }, belief);
      if (r?.status === 'success' || r?.status === 'queued') {
        sendFeedback(data.belief_id, 'executed', pick.pick_id);
        setStatus((s) => ({ ...s, [skey]: r.status === 'queued' ? `queued:${r.message}` : 'traded' }));
      } else {
        setStatus((s) => ({ ...s, [skey]: `error:${r?.message || 'The paper trade did not go through.'}` }));
      }
    } catch (e) {
      setStatus((s) => ({ ...s, [skey]: `error:${e.message}` }));
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

      {(interp.clarify_question && onRefine) && (
        <div className="px-4 pt-3">
          <div className="rounded-2xl bg-amber-400/10 border border-amber-300/30 p-3">
            <div className="text-sm text-amber-100"><span className="font-bold">Quick question:</span> {interp.clarify_question}</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {interp.clarify_options.map((o) => (
                <button key={o} onClick={() => onRefine(o)} className="rounded-full px-3 py-1.5 text-xs font-semibold bg-slate-900/80 border border-amber-300/40 text-amber-50 hover:border-amber-200">{o}</button>
              ))}
            </div>
            <div className="mt-1.5 text-[11px] text-amber-200/70">Or keep going: these picks are my best guess.</div>
          </div>
        </div>
      )}

      <div className="px-4 pt-3">
        <StrategyGuide current={data.prefs || prefs} onTune={onTune} />
      </div>

      <div className="px-4 pt-3">
        <ReplayPanel picks={picks} onResult={setReplay} />
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
            <div className={`text-[11px] ${i === idx ? 'text-blue-100' : 'text-slate-400'}`}>{kindLabel(useAlt[p.pick_id] && p.alt ? p.alt.structure : p.structure)}</div>
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
              <span><Term k="fit">Fit with your belief</Term></span><span className="text-slate-200 font-semibold">{fit}%</span>
            </div>
            <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
              <div className="h-full bg-blue-500" style={{ width: `${fit}%` }} />
            </div>
            {track && track.n > 0 && (
              <p className="text-xs text-slate-400">
                <Term k="track record">Track record</Term> on this theme: beat the S&amp;P 500 in {Math.round(track.hit * 100)}% of {track.n} past picks
                ({track.mean >= 0 ? '+' : ''}{(track.mean * 100).toFixed(1)}% on average after 30 days).
              </p>
            )}
          </div>

          {basePick.alt && (
            <div>
              <div className="text-xs text-slate-400 mb-1.5">How do you want to trade {pick.ticker}?</div>
              <div className="grid grid-cols-2 gap-1 rounded-xl bg-slate-800 p-1" role="radiogroup" aria-label="Shares or options">
                {[basePick, { ...basePick, ...basePick.alt, _alt: true }].map((v) => {
                  const shares = FAMILY_SHARES.has(v.structure);
                  const on = !!useAlt[basePick.pick_id] === !!v._alt;
                  return (
                    <button key={v._alt ? 'alt' : 'main'} role="radio" aria-checked={on}
                      onClick={() => setUseAlt((u) => ({ ...u, [basePick.pick_id]: !!v._alt }))}
                      className={`rounded-lg py-2 text-sm font-bold ${on ? 'bg-blue-600 text-white' : 'text-slate-300 hover:text-white'}`}>
                      {shares ? '📈 Shares' : '🎯 Options'}
                      <span className={`block text-[11px] font-medium ${on ? 'text-blue-100' : 'text-slate-500'}`}>{shares ? (v.structure === 'Buy Stock' ? 'Simple: own it' : 'Stay out / sell') : v.structure}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Strategy */}
          <div className="rounded-xl bg-slate-800/60 border border-slate-700 p-3">
            <div className="flex items-center justify-between">
              <div className="font-bold text-white">
                {/spread/i.test(pick.structure) ? <Term k="spread">{pick.structure}</Term>
                  : /condor/i.test(pick.structure) ? <Term k="iron condor">{pick.structure}</Term>
                  : /straddle/i.test(pick.structure) ? <Term k="straddle">{pick.structure}</Term>
                  : /strangle/i.test(pick.structure) ? <Term k="strangle">{pick.structure}</Term>
                  : <Term k={pick.structure.toLowerCase()}>{pick.structure}</Term>}
              </div>
              {pick.trade?.expiration && <div className="text-xs text-slate-400"><Term k="expiration">Expires</Term> {niceDate(pick.trade.expiration)}</div>}
            </div>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">{PLAIN[pick.structure] || pick.trade?.plain || ''}</p>
            {pick.structure_reason && pick.structure_reason !== 'rule' && (
              <p className="text-xs text-blue-200 mt-1.5 leading-relaxed"><span className="font-semibold">Why this strategy: </span>{pick.structure_reason}</p>
            )}
            {isOptions && model?.daysToExp > 0 && (
              <p className="text-[11px] text-slate-500 mt-1.5">
                ⏳ {model.daysToExp} days until it expires. Options lose value as time passes, so we never suggest ones with under 30 days left.
              </p>
            )}
            {legs.length > 0 && (
              <ul className="mt-2 space-y-1">
                {legs.map((l, i) => (
                  <li key={i} className="flex justify-between gap-2 text-sm">
                    <span className="whitespace-nowrap"><span className={l.action === 'Sell' ? 'text-red-300' : 'text-green-300'}>{l.action}</span> <span className="text-white">{l.ticker}</span>{l.option_type ? <> <Term k={String(l.option_type).toLowerCase()}>{l.option_type}</Term></> : ''}</span>
                    {l.strike_price ? <span className="text-slate-300 text-right whitespace-nowrap">${l.strike_price} <Term k="strike">strike</Term>{l.est_premium ? <span className="text-slate-500"> · ${l.est_premium}</span> : ''}</span> : <span className="text-slate-500">{l.instrument === 'stock' ? 'shares' : ''}</span>}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {plain.length > 0 && (
            <div className="rounded-2xl border border-blue-400/25 bg-blue-500/[0.07] p-3.5">
              <div className="text-[11px] uppercase tracking-wider text-blue-300 font-semibold mb-2">The deal, in plain English</div>
              <ul className="space-y-1.5">
                {plain.map((l, i) => (
                  <li key={i} className={`flex gap-2.5 text-sm leading-snug ${TONE[l.tone]}`}>
                    <span className={`mt-1.5 w-1.5 h-1.5 rounded-full shrink-0 ${DOT[l.tone]}`} aria-hidden />
                    <span>{l.text}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {!avoid && sum && (
            <>
              <div className="grid grid-cols-3 gap-2">
                <Stat label={isOptions ? 'Per contract' : 'Price'} value={isOptions ? money(model.capitalPerUnit) : `$${Number(pick.price).toFixed(2)}`} />
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
                      onClick={() => { setAmount(a); setCustom(''); }}
                      className={`rounded-lg py-2 text-sm font-bold border ${a === amount && !custom ? 'bg-blue-600 border-blue-400 text-white' : 'bg-slate-800 border-slate-700 text-slate-200 hover:border-slate-500'}`}
                    >
                      ${a.toLocaleString()}
                    </button>
                  ))}
                </div>
                <label className={`mt-2 flex items-center gap-2 rounded-lg border px-3 py-2 ${custom ? 'border-blue-400 bg-blue-600/10' : 'border-slate-700 bg-slate-800/60'}`}>
                  <span className="text-xs text-slate-400 shrink-0">Or type any amount</span>
                  <span className="ml-auto text-slate-400 font-bold">$</span>
                  <input
                    type="text" inputMode="decimal" placeholder="e.g. 750" value={custom}
                    aria-label="Custom amount in dollars"
                    onChange={(e) => {
                      const raw = e.target.value.replace(/[^0-9.]/g, '');
                      setCustom(raw);
                      const n = Math.round(Number(raw));
                      if (n >= 1) setAmount(Math.min(n, MAX_AMOUNT));
                    }}
                    onBlur={() => { if (custom && !(Number(custom) >= 1)) { setCustom(''); setAmount(1000); } }}
                    className="w-28 bg-transparent text-right font-bold text-white placeholder:text-slate-500 focus:outline-none"
                  />
                </label>
                {Number(custom) > MAX_AMOUNT && <p className="text-[11px] text-amber-200 mt-1">The practice account holds ${MAX_AMOUNT.toLocaleString()}, so this uses ${MAX_AMOUNT.toLocaleString()}.</p>}
                {sizing?.over ? (
                  <div className="mt-2 rounded-xl border border-amber-300/40 bg-amber-400/10 p-3 text-sm text-amber-100">
                    One {pick.ticker} contract costs about ${Math.round(sizing.per).toLocaleString()}, more than your ${amount.toLocaleString()}.
                    <div className="mt-2 flex flex-wrap gap-2">
                      {basePick.alt && FAMILY_SHARES.has(useAlt[basePick.pick_id] ? basePick.structure : basePick.alt.structure)
                        && (useAlt[basePick.pick_id] ? basePick.structure : basePick.alt.structure) === 'Buy Stock' && (
                        <button onClick={() => setUseAlt((u) => ({ ...u, [basePick.pick_id]: !u[basePick.pick_id] }))}
                          className="rounded-lg bg-blue-600 hover:bg-blue-500 px-3 py-1.5 text-xs font-bold text-white">Buy ${amount.toLocaleString()} of shares instead</button>
                      )}
                      {Math.ceil(sizing.per) <= MAX_AMOUNT && (
                        <button onClick={() => { const n = Math.ceil(sizing.per / 50) * 50; setAmount(n); setCustom(String(n)); }}
                          className="rounded-lg border border-amber-200/50 px-3 py-1.5 text-xs font-bold">Put in ${(Math.ceil(sizing.per / 50) * 50).toLocaleString()}</button>
                      )}
                    </div>
                  </div>
                ) : sizing?.note && <p className="text-[11px] text-slate-500 mt-1.5">{sizing.note}</p>}
              </div>

              <PayoffChart
                key={skey}
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
              disabled={busy || st === 'traded' || st === 'tracking' || st?.startsWith?.('queued:') || st?.startsWith?.('opt:')}
              className="rounded-lg py-3 text-sm font-bold bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-60"
            >
              {busy ? 'Placing…' : st === 'traded' || st?.startsWith?.('opt:') ? 'Paper traded' : st?.startsWith?.('queued:') ? 'Queued for the open' : st === 'tracking' ? 'Tracking' : avoid ? 'Track it' : 'Paper trade'}
            </button>
          </div>
          {st === 'up' && <p className="text-xs text-green-400">Thanks. Your vote helps everyone get better picks.</p>}
          {st === 'down' && <p className="text-xs text-slate-400">Got it. We'll show picks like this less often.</p>}
          {st?.startsWith?.('queued:') && <p className="text-xs text-amber-200">{st.slice(7)} Find it under Practice.</p>}
          {st?.startsWith?.('opt:') && <p className="text-xs text-blue-300">{st.slice(4)} <button onClick={() => navigate('/portfolio')} className="underline font-semibold">See it in Portfolio →</button></p>}
          {st === 'traded' && <p className="text-xs text-blue-300">Added ${amount.toLocaleString()} of {pick.ticker} to your practice portfolio. No real money.</p>}
          {(st === 'tracking' || st === 'traded') && (
            <p className="text-xs text-blue-300">
              {st === 'tracking' ? "We'll grade this idea against the market at 1 week, 1 month and 3 months. " : ''}
              <button onClick={() => navigate('/my')} className="underline font-semibold">See it in My calls →</button>
            </p>
          )}
          {st?.startsWith?.('error:') && <p className="text-xs text-red-400">{st.slice(6)}</p>}

          {broker?.enabled && broker?.connected && pick.structure === 'Buy Stock' && pick.direction === 'bullish' && (
            <button onClick={() => setRealOpen(true)} className="w-full rounded-lg py-3 text-sm font-bold border border-amber-300/50 bg-amber-400/10 text-amber-100 hover:border-amber-200">
              {broker.env === 'live' ? '💵 Invest real money in' : '💵 Buy in my Alpaca account (practice side):'} {pick.ticker}
            </button>
          )}
          <RealMoneySheet open={realOpen} onClose={() => setRealOpen(false)} pick={pick} beliefId={data.belief_id} defaultAmount={amount} broker={broker} />

          {/* Variations + share */}
          <div className="grid grid-cols-3 gap-2 pt-1">
            {onRerun && next.safer && (
              <button onClick={() => onRerun(next.safer)} className="rounded-full px-3.5 py-2 text-xs font-semibold bg-slate-800 border border-slate-700 text-slate-200 hover:border-blue-400">
                🛡️ Safer
              </button>
            )}
            {onRerun && next.bolder && (
              <button onClick={() => onRerun(next.bolder)} className="rounded-full px-3.5 py-2 text-xs font-semibold bg-slate-800 border border-slate-700 text-slate-200 hover:border-blue-400">
                🚀 Bolder
              </button>
            )}
            <button onClick={share} className="rounded-full px-3.5 py-2 text-xs font-semibold bg-slate-800 border border-slate-700 text-slate-200 hover:border-blue-400 col-start-3">
              {shared === 'making' ? 'Making…' : shared === 'saved' ? '✓ Image saved' : shared === 'copied' ? '✓ Link copied' : '↗ Share'}
            </button>
          </div>
        </motion.div>
      </AnimatePresence>

      {(interp.wrong_if?.length > 0 || interp.exit_rule) && (
        <div className="mx-4 mb-4 rounded-2xl border border-slate-700 bg-slate-800/40 p-3.5">
          <div className="text-[11px] uppercase tracking-wider text-slate-300 font-semibold">🧭 What would prove this wrong</div>
          {interp.wrong_if?.length > 0 && (
            <ul className="mt-2 space-y-1">
              {interp.wrong_if.map((w) => <li key={w} className="text-sm text-slate-200 flex gap-2"><span className="text-slate-500">•</span>{w}</li>)}
            </ul>
          )}
          {interp.exit_rule && <p className="mt-2 text-sm text-white"><span className="font-semibold text-blue-300">Exit plan: </span>{interp.exit_rule}</p>}
        </div>
      )}

      <div className="px-4 py-3 bg-slate-950/60 border-t border-slate-800 text-[11px] text-slate-500 leading-relaxed">
        Ideas for education, not investment advice. Prices are delayed; option prices are estimates. Trading involves risk, including loss of what you invest.
      </div>
    </motion.div>
  );
}
