// Yes / No: "Will NVDA close above $150 on Fri Nov 21?" The market's odds from real option prices, the brain's
// lean, and a fixed-cost practice trade (call spread for YES, put spread for NO). Graded after expiration.
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import Page, { Card } from './ui/Page';
import { yesnoExpirations, yesnoQuote, yesnoCall, yesnoMine, yesnoMyRecord, yesnoScorecard } from '../lib/api';

const usd = (v, d = 0) => `$${Number(v || 0).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })}`;
// A strike as the market lists it: $185, $182.50 (not $182.5).
const strikeTxt = (k) => (Number.isInteger(k) ? String(k) : Number(k).toFixed(2));
// Practice YES / NO prices are to the cent; show the cents so YES + NO visibly add up to (just under) the payout.
const usdc = (v) => usd(v, Math.abs(Math.round(Number(v || 0) * 100)) % 100 ? 2 : 0);
const pc = (p) => `${Math.round(Number(p || 0) * 100)}%`;
// Odds near 50% keep one decimal so 49.8% and 50.2% don't both read "50%" on opposite sides.
const pcSide = (p) => { const v = Number(p || 0) * 100; return Math.round(v) === 50 && Math.abs(v - 50) >= 0.05 ? `${v.toFixed(1)}%` : `${Math.round(v)}%`; };
const fmtShort = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
const fmtDay = (iso) => { const d = new Date(`${iso}T12:00:00`); return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }); };
// The record's verdict is clustered by closing day: 15 stocks that close the same Friday share one market move.
const VERDICT = {
  too_early: (s) => `Too early to say whether its odds beat the market's. Questions that close on the same day share one market move, so each closing day counts once, and the verdict waits for ${s.min_days || 5} days (${s.days || 0} so far).`,
  better: () => "Its odds have been closer to what happened than the market's, by more than luck would explain (each closing day counted once).",
  worse: () => "Its odds have been further from what happened than the market's, by more than luck would explain (each closing day counted once).",
  about_same: () => "Its odds and the market's are about even so far: the gap is within what luck would explain (each closing day counted once).",
};
const POPULAR = ['SPY', 'QQQ', 'NVDA', 'AAPL', 'TSLA', 'AMZN', 'META', 'MSFT'];

// The user's own record: right X of Y, beside how many the market's odds at the time expected (a 90% favourite
// being right says little). Same-day answers share one market move, so the luck band is clustered by closing day.
function MyRecord({ rec }) {
  if (!rec || !rec.graded) return null;
  if (rec.verdict === 'too_few') {
    return <p className="mt-2 text-xs text-slate-400">Your record shows once {rec.min} answers are graded ({rec.graded} so far). It will set how often you were right beside what the market's odds expected.</p>;
  }
  const said = {
    too_early: `Too early to call it skill or luck: answers that close on the same day share one market move, so the verdict waits for ${rec.min_days} closing days (${rec.days} so far).`,
    ahead: 'Ahead of the market\'s odds by more than luck would explain (each closing day counted once).',
    behind: 'Behind the market\'s odds by more than luck would explain (each closing day counted once).',
    within_luck: `Within what luck would explain (about ±${Math.round(2 * (rec.se || 0) * 10) / 10} answers either way, each closing day counted once).`,
  }[rec.verdict];
  return (
    <div className="mt-2 rounded-2xl border border-slate-700 bg-slate-900/50 p-3 text-sm">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-slate-300">You were right</span>
        <span className="font-extrabold tabular-nums">{rec.right} of {rec.graded}</span>
      </div>
      <div className="mt-1 flex items-baseline justify-between gap-2">
        <span className="text-slate-400 min-w-0">Market's odds expected</span>
        <span className="shrink-0 font-bold tabular-nums text-slate-300">{rec.expected}</span>
      </div>
      <p className="mt-2 text-xs text-slate-400">When you answered, the market gave your side {pc(rec.avg_odds)} on average. {said}</p>
    </div>
  );
}

// The brain's own daily questions, in the open: the market's odds and the brain's when it asked, then the close and
// right / wrong. Its lean only nudges the market's odds, so it takes the other side only near 50%; those are marked.
// Graded ones get their own list: it asks ~11 a day, 5+ days out, so the newest-asked list is nearly all open and the
// record's right / wrong answers would never show.
function QuestionRow({ r }) {
  return (
    <div className="py-2 flex items-center justify-between gap-2">
      <span className="min-w-0">
        <span className="block">{r.ticker} above {usd(r.level, r.level % 1 ? 2 : 0)} <span className="whitespace-nowrap">on {fmtDay(r.expiration)}</span></span>
        <span className="block text-[11px] text-slate-500 tabular-nums">
          {r.asked && <><span className="whitespace-nowrap">Asked {fmtShort(r.asked)}</span>{' · '}</>}
          <span className="whitespace-nowrap">market {pcSide(r.market_p)} yes</span>{' · '}<span className="whitespace-nowrap">brain {pcSide(r.brain_p)} yes</span>
          {r.close_price != null && <>{' · '}<span className="whitespace-nowrap">closed {usd(r.close_price, 2)}</span></>}
        </span>
        {r.disagrees && <span className="block text-[11px] text-amber-300">Took the other side from the market</span>}
      </span>
      <span className="shrink-0 flex items-center gap-2">
        <b className={r.side === 'yes' ? 'text-green-300' : 'text-red-300'}>{r.side.toUpperCase()}</b>
        <span className={`text-xs px-2 py-0.5 rounded-full ${r.result === 'right' ? 'bg-green-500/20 text-green-200' : r.result === 'wrong' ? 'bg-red-500/20 text-red-200' : 'bg-slate-700 text-slate-300'}`}>{r.result}</span>
      </span>
    </div>
  );
}

function QuestionList({ title, note, rows, first }) {
  const [all, setAll] = useState(false);
  if (!rows || !rows.length) return null;
  const shown = all ? rows : rows.slice(0, first);
  const key = (r, i) => `${r.ticker}-${r.level}-${r.expiration}-${i}`;
  return (
    <div className="mt-3">
      <div className="text-xs text-slate-400 font-semibold">{title}</div>
      {note && <div className="text-[11px] text-slate-500">{note}</div>}
      <div className="mt-1 divide-y divide-slate-800">
        {shown.map((r, i) => <QuestionRow key={key(r, i)} r={r} />)}
      </div>
      {rows.length > first && (
        <button onClick={() => setAll(!all)} className="mt-1 text-xs text-blue-300">{all ? 'Show fewer' : `Show all ${rows.length}`}</button>
      )}
    </div>
  );
}

function BrainQuestions({ graded, recent }) {
  const open = (recent || []).filter((r) => r.result === 'open');
  const g = graded || [];
  if (!g.length && !open.length) return null;
  const right = g.filter((r) => r.result === 'right').length;
  return (
    <>
      <QuestionList title="Latest graded" rows={g} first={6}
        note={g.length ? `Its side was right on ${right} of these ${g.length}, latest closing day first.` : null} />
      <QuestionList title="Waiting for the close" rows={open} first={g.length ? 3 : 6} />
      <p className="mt-2 text-xs text-slate-400">Odds are as they stood when it asked, with the line set near that day's price. Its lean starts from the market's odds and moves them a few points, so it picks a different side only when the market is close to 50%.</p>
    </>
  );
}

// Close Call answers placed as practice trades, added up on the same cash numbers as the Portfolio's closed list.
function TradesTotal({ t }) {
  if (!t) return null;
  const sign = (v) => `${v < 0 ? '−' : '+'}${usd(Math.abs(v))}`;
  return (
    <div className="mt-2 rounded-2xl border border-slate-700 bg-slate-900/50 p-3 text-sm">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-slate-300 min-w-0">Your practice trades</span>
        {t.settled > 0
          ? <span className={`shrink-0 font-extrabold tabular-nums ${t.pnl > 0 ? 'text-green-300' : t.pnl < 0 ? 'text-red-300' : ''}`}>{sign(t.pnl)}</span>
          : <span className="shrink-0 text-slate-400">none settled yet</span>}
      </div>
      <p className="mt-1 text-xs text-slate-400">
        {t.settled > 0 ? `${t.settled} settled or closed, ${t.won} made money. ` : ''}
        {t.open > 0 ? `${t.open} still open. ` : ''}
        Trades settle at the closing price on their expiration day. A close between the two strikes can make a right answer lose a little, or a wrong one make a little.
      </p>
    </div>
  );
}

// One answer's practice trade: what's at risk while it's open, what it made or lost once settled, and a plain
// note when the trade and the yes/no answer disagree (closed between the strikes, past the breakeven or short of it).
function TradeLine({ c }) {
  const t = c.trade;
  if (!t) return null;
  if (t.status !== 'closed' || t.pnl == null) {
    return <span className="block text-[11px] text-slate-400 tabular-nums">Practice trade · {usd(t.cost)} at risk</span>;
  }
  const up = t.pnl >= 0;
  const amt = `${up ? '+' : '−'}${usd(Math.abs(t.pnl))}`;
  const odd = t.expired && ((c.result === 'right' && t.pnl < 0) || (c.result === 'wrong' && t.pnl > 0));
  return (
    <>
      <span className="block text-[11px] tabular-nums text-slate-400">
        Practice trade <b className={up ? 'text-green-300' : 'text-red-300'}>{amt}</b>{t.expired ? ' at expiration' : ' (closed early)'}
      </span>
      {odd && (
        <span className="block text-[11px] text-amber-200/90 whitespace-normal">
          {c.result === 'right'
            ? `Right on the question, but it closed between the strikes, short of the trade's breakeven.`
            : `Wrong on the question, but it closed between the strikes, past the trade's breakeven.`}
        </span>
      )}
    </>
  );
}

function OddsBar({ label, p, tone }) {
  return (
    <div>
      <div className="flex justify-between gap-2 text-sm"><span className="text-slate-300 min-w-0">{label}</span><span className="shrink-0 whitespace-nowrap font-extrabold tabular-nums">{pc(p)} YES</span></div>
      <div className="mt-1 h-3 rounded-full bg-slate-800 overflow-hidden">
        <div className={`h-full rounded-full ${tone}`} style={{ width: `${Math.max(2, Math.min(98, p * 100))}%` }} />
      </div>
    </div>
  );
}

// The range option prices put about a 2-in-3 chance on by the expiration, with today's price and the line on it,
// so "Will it close above $160?" sits next to how far the market thinks it could go. Information only.
// The same spreads on the listed quotes right now, next to the practice price. A desk reads a digital's odds off the
// mid but pays the ask, so this says what the odds must be to break even at the ask, and when quotes are too wide to use.
function ListedCosts({ c, open }) {
  if (!c || !c.yes || !c.no) return null;
  const sides = [['yes', 'YES', 'text-green-300'], ['no', 'NO', 'text-red-300']];
  const outside = sides.map(([k, label]) => {
    const s = c[k];
    if (s.wide || c.out_of_step || s.practice == null) return null;
    if (s.practice < s.bid) return `Practice ${label} at ${usd(s.practice)} is below the listed bid, cheaper than a real fill right now.`;
    if (s.practice > s.ask) return `Practice ${label} at ${usd(s.practice)} is above the listed ask, dearer than a real fill right now.`;
    return null;
  }).filter(Boolean);
  const over = sides.filter(([k]) => c[k].ask >= c.payout).map(([, label]) => label);
  return (
    <div className="mt-4 rounded-2xl border border-slate-700/70 bg-slate-900/60 p-3">
      <div className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">What a real order would pay</div>
      <div className="text-[11px] text-slate-500">Listed quotes for the same spreads right now, per contract</div>
      <div className="mt-2 space-y-1">
        {sides.map(([k, label, tone]) => (
          <div key={k} className="flex items-baseline gap-3 text-sm tabular-nums">
            <span className={`w-8 shrink-0 font-bold ${tone}`}>{label}</span>
            <span className="text-slate-200"><span className="whitespace-nowrap">{usd(c[k].bid)} bid / {usd(c[k].ask)} ask</span> <span className="whitespace-nowrap text-slate-400">· practice {c[k].practice != null ? usd(c[k].practice) : 'n/a'}</span></span>
          </div>
        ))}
      </div>
      {c.out_of_step && !c.wide ? (
        <p className="mt-2 text-xs text-amber-300">These quotes don't fit together: YES and NO always pay {usd(c.payout)} between them, yet {c.yes.bid + c.no.bid > c.payout ? `selling both at the bid would bring in ${usd(c.yes.bid + c.no.bid)}` : `buying both at the ask would cost only ${usd(c.yes.ask + c.no.ask)}`}. The call and put quotes were set at different moments{open ? '' : ' (common outside market hours, 9:30 AM to 4 PM ET)'}, so a real order wouldn't fill like this. Read the practice price as a fair-value estimate.</p>
      ) : c.wide ? (
        <p className="mt-2 text-xs text-amber-300">These quotes are too wide to trade as shown{over.length ? ` (the ${over.join(' and ')} ask is at or above the ${usd(c.payout)} the spread can pay)` : ''}. {open ? "The market is open, so this contract just trades thinly right now (and the free quote feed we use can show quotes wider than a broker would)." : "That's usual outside market hours (9:30 AM to 4 PM ET)."} Read the practice price as a fair-value estimate, not a fill you could get now.</p>
      ) : (
        <p className="mt-2 text-xs text-slate-400">Practice trades fill at the practice price. A real order to buy pays up to the ask: there, YES needs a {pc(c.yes.odds_at_ask)} chance to break even{c.yes.odds_at_practice != null ? ` (not ${pc(c.yes.odds_at_practice)})` : ''} and NO {pc(c.no.odds_at_ask)}{c.no.odds_at_practice != null ? ` (not ${pc(c.no.odds_at_practice)})` : ''}. Selling before expiration gets the bid, so a round trip costs about {usd(c.yes.ask - c.yes.bid)} on YES and {usd(c.no.ask - c.no.bid)} on NO.</p>
      )}
      {outside.length > 0 && <p className="mt-1 text-xs text-slate-400">{outside.join(' ')}</p>}
    </div>
  );
}

function MoveRange({ m, spot, level }) {
  if (!m || !m.lines) return null;
  const lo = Math.min(m.low, level, spot);
  const hi = Math.max(m.high, level, spot);
  const pad = (hi - lo) * 0.06 || 1;
  const pos = (v) => ((v - (lo - pad)) / (hi - lo + 2 * pad)) * 100;
  // A label near either end hangs inward so it never runs off a 375px screen.
  const tag = (v) => { const p = pos(v); return { left: `${p}%`, transform: p < 18 ? 'none' : p > 82 ? 'translateX(-100%)' : 'translateX(-50%)' }; };
  const fmt = (v) => usd(v, v % 1 ? 2 : 0);
  return (
    <div className="mt-4 rounded-2xl border border-slate-700 bg-slate-900/50 p-3">
      <div className="text-xs uppercase tracking-wider text-slate-400 font-semibold">How far it could move</div>
      <div className="relative mt-7 mb-7 h-2 rounded-full bg-slate-800" aria-hidden="true">
        <div className="absolute h-2 rounded-full bg-slate-500/70" style={{ left: `${pos(m.low)}%`, width: `${pos(m.high) - pos(m.low)}%` }} />
        <div className="absolute -top-1 h-4 w-0.5 -ml-px bg-white" style={{ left: `${pos(spot)}%` }} />
        <div className="absolute -top-6 whitespace-nowrap text-[11px] text-slate-300 tabular-nums" style={tag(spot)}>now {usd(spot, 2)}</div>
        <div className="absolute -top-1.5 h-5 w-0.5 -ml-px bg-blue-400" style={{ left: `${pos(level)}%` }} />
        <div className="absolute top-4 whitespace-nowrap text-[11px] font-bold text-blue-300 tabular-nums" style={tag(level)}>line {fmt(level)}</div>
      </div>
      <p className="text-xs text-slate-300">{m.lines[0]} <span className="text-slate-400">The grey band is that range.</span></p>
      {m.lines[1] && <p className="mt-2 text-xs text-amber-200">{m.lines[1]}</p>}
    </div>
  );
}

export default function YesNoPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [ticker, setTicker] = useState((params.get('t') || 'SPY').toUpperCase());
  const [typed, setTyped] = useState('');
  const [setup, setSetup] = useState(null);
  const [exp, setExp] = useState('');
  const [level, setLevel] = useState('');
  const [q, setQ] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [toast, setToast] = useState('');
  const [contracts, setContracts] = useState(1);
  const [mine, setMine] = useState([]);
  const [score, setScore] = useState(null);
  const [rec, setRec] = useState(null);

  const loadMine = useCallback(() => {
    yesnoMine().then((r) => setMine(Array.isArray(r) ? r : [])).catch(() => {});
    yesnoMyRecord().then((r) => setRec(r && r.graded != null ? r : null)).catch(() => {});
  }, []);
  useEffect(() => { loadMine(); yesnoScorecard().then(setScore).catch(() => {}); }, [loadMine]);

  useEffect(() => {
    setSetup(null); setQ(null); setErr('');
    yesnoExpirations(ticker).then((r) => {
      if (r?.status === 'error') { setErr(r.message); return; }
      setSetup(r);
      const t0 = Date.now();
      setExp(r.expirations.find((e) => (new Date(`${e}T21:00:00Z`) - t0) / 86400000 >= 5) || r.expirations[0]);
      setLevel(String(r.lines[Math.floor(r.lines.length / 2)]));
    }).catch((e) => setErr(e.message));
  }, [ticker]);

  useEffect(() => {
    if (!setup || !exp || !level) return;
    const id = setTimeout(() => {
      setBusy(true); setErr('');
      yesnoQuote(ticker, level, exp).then((r) => {
        if (r?.status === 'error') { setErr(r.message); setQ(null); } else setQ(r);
      }).catch((e) => setErr(e.message)).finally(() => setBusy(false));
    }, 350);
    return () => clearTimeout(id);
  }, [setup, ticker, exp, level]);

  const answer = async (side, trade) => {
    setBusy(true);
    try {
      const r = await yesnoCall({ ticker, level: Number(level), expiration: exp, side, trade, contracts });
      setToast(r?.status === 'success' ? r.message : (r?.message || 'Try again.'));
      loadMine();
    } catch (e) { setToast(e.message); }
    finally { setBusy(false); setTimeout(() => setToast(''), 5000); }
  };

  const go = (e) => { e.preventDefault(); const t = typed.trim().toUpperCase(); if (t) { setTicker(t); setTyped(''); } };

  return (
    <Page title="Close Call" subtitle="Yes or no: will it close above the line? Real option odds, the brain's lean, practice money.">
      <Card className="mt-6">
        <form onSubmit={go} className="flex gap-2">
          <input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder={`Stock or ETF (now ${ticker})`}
            className="flex-1 min-w-0 rounded-2xl bg-slate-800/80 border border-slate-700 px-4 py-3 text-white placeholder-slate-500 focus:border-blue-400 outline-none" />
          <button className="rounded-2xl bg-blue-600 px-4 font-bold">Go</button>
        </form>
        <div className="mt-3 flex flex-wrap gap-2">
          {POPULAR.map((t) => (
            <button key={t} onClick={() => setTicker(t)} className={`text-xs px-3 py-1.5 rounded-full border ${t === ticker ? 'border-blue-400 bg-blue-500/20' : 'border-slate-700 bg-slate-800/70'}`}>{t}</button>
          ))}
        </div>
      </Card>

      {err && <Card className="mt-4 text-sm text-amber-200 border-amber-500/40">{err}</Card>}
      {!setup && !err && <div className="mt-4 h-40 rounded-3xl bg-slate-800/50 animate-pulse" />}

      {setup && (
        <Card className="mt-4">
          <div className="text-xs uppercase tracking-wider text-slate-400 font-semibold">{ticker} is at {usd(setup.spot, 2)}</div>
          <div className="mt-3 text-sm text-slate-300">Close above</div>
          <div className="mt-1 flex flex-wrap gap-2">
            {setup.lines.map((l) => (
              <button key={l} onClick={() => setLevel(String(l))} className={`px-3 py-2 rounded-xl border text-sm font-bold tabular-nums ${String(l) === String(level) ? 'border-blue-400 bg-blue-500/20' : 'border-slate-700 bg-slate-800/70'}`}>{usd(l, l % 1 ? 2 : 0)}</button>
            ))}
            <input inputMode="decimal" placeholder="Other $" aria-label="Your own price"
              value={setup.lines.some((l) => String(l) === String(level)) ? '' : level}
              onChange={(e) => { const v = e.target.value.replace(/[^0-9.]/g, ''); if (v) setLevel(v); }}
              className="w-24 rounded-xl bg-slate-900/60 border border-dashed border-slate-600 px-3 py-2 text-sm tabular-nums placeholder-slate-500" />
          </div>
          <div className="mt-4 text-sm text-slate-300">On</div>
          <div className="mt-1 flex gap-2 overflow-x-auto pb-1">
            {setup.expirations.map((e) => (
              <button key={e} onClick={() => setExp(e)} className={`shrink-0 px-3 py-2 rounded-xl border text-sm font-bold ${e === exp ? 'border-blue-400 bg-blue-500/20' : 'border-slate-700 bg-slate-800/70'}`}>{fmtDay(e)}</button>
            ))}
          </div>
        </Card>
      )}

      {q && (
        <Card className={`mt-4 ${busy ? 'opacity-60' : ''}`}>
          <div className="text-xl font-extrabold leading-snug">{q.question}</div>
          <div className="mt-4 space-y-3">
            <OddsBar label="Market's odds (risk-neutral)" p={q.market_p} tone="bg-slate-400" />
            {q.odds_source && <div className="-mt-1 text-[11px] text-slate-500">From {q.odds_source}.</div>}
            <OddsBar label={q.brain_model === 'learned' ? "Brain's lean (learned)" : "Brain's lean (starting rules, untested)"} p={q.brain_p} tone="bg-blue-500" />
          </div>
          <MoveRange m={q.move} spot={q.spot} level={q.level} />
          <ul className="mt-3 text-xs text-slate-400 space-y-1">
            {q.reasons.map((r) => <li key={r}>• {r}</li>)}
            <li>• {q.brain_model === 'learned'
              ? "This lean went live only after beating the market's odds on graded questions it hadn't seen. Every answer is graded."
              : "The brain's track record is on 90-day stock ideas, not short yes/no questions. Until a learned lean beats the market's odds on graded questions it hasn't seen, fixed starting rules move the odds a few points at most. Every answer is graded."}</li>
          </ul>

          <div className="mt-5 grid grid-cols-2 gap-3">
            {['yes', 'no'].map((side) => {
              const t = q[side];
              const yes = side === 'yes';
              return (
                <div key={side} className={`rounded-2xl border p-3 ${yes ? 'border-green-400/40 bg-green-500/[0.07]' : 'border-red-400/40 bg-red-500/[0.07]'}`}>
                  <div className={`text-2xl font-black ${yes ? 'text-green-300' : 'text-red-300'}`}>{side.toUpperCase()}</div>
                  {t.cost != null ? (
                    <div className="mt-1 text-sm text-slate-200">Risk <b>{usdc(t.cost * contracts)}</b> to make <b>{usdc(t.profit * contracts)}</b></div>
                  ) : <div className="mt-1 text-sm text-slate-400">No price right now</div>}
                  {t.cost != null && t.breakeven != null && (
                    <div className="mt-0.5 text-xs text-slate-400 tabular-nums">Breaks even {yes ? 'above' : 'below'} {usd(t.breakeven, 2)}</div>
                  )}
                  <button disabled={busy || t.cost == null} onClick={() => answer(side, true)}
                    className={`mt-3 w-full rounded-xl py-2.5 font-bold disabled:opacity-40 ${yes ? 'bg-green-600' : 'bg-red-600'}`}>Practice trade</button>
                  <button disabled={busy} onClick={() => answer(side, false)} className="mt-2 w-full rounded-xl py-2 text-sm border border-slate-600 text-slate-200">Just call it</button>
                </div>
              );
            })}
          </div>
          <div className="mt-3 flex items-center justify-between text-sm">
            <span className="text-slate-400">Contracts</span>
            <div className="flex items-center gap-2">
              <button onClick={() => setContracts((c) => Math.max(1, c - 1))} className="w-8 h-8 rounded-lg bg-slate-800 border border-slate-700">−</button>
              <span className="w-6 text-center font-bold tabular-nums">{contracts}</span>
              <button onClick={() => setContracts((c) => Math.min(50, c + 1))} className="w-8 h-8 rounded-lg bg-slate-800 border border-slate-700">+</button>
            </div>
          </div>
          <ListedCosts c={q.listed} open={q.market_closed === false} />
          <p className="mt-3 text-xs text-slate-500">{q.spread_note} Built from real listed {q.ticker} options. The odds are risk-neutral (what option prices imply, not a forecast); over days or weeks they sit close to real-world odds. {q.price_source === 'strikes' && q.leg_vols ? `Practice trades cost the listed mid prices of the $${strikeTxt(q.strikes[0])} and $${strikeTxt(q.strikes[1])} options, each at its own implied volatility (${(q.leg_vols[0] * 100).toFixed(1)}% and ${(q.leg_vols[1] * 100).toFixed(1)}%, so skew is included), before bid/ask costs.` : q.price_source === 'smile' && q.leg_vols ? `Practice trades price the $${strikeTxt(q.strikes[0])} and $${strikeTxt(q.strikes[1])} options at the smile's implied volatilities for those strikes (${(q.leg_vols[0] * 100).toFixed(1)}% and ${(q.leg_vols[1] * 100).toFixed(1)}%, so skew is included and YES costs about the odds shown), before bid/ask costs.` : q.price_source === 'spread' ? `Practice trades cost the listed mid price of the same $${strikeTxt(q.strikes[0])}/$${strikeTxt(q.strikes[1])} spreads (skew included), before bid/ask costs.` : q.price_source === 'line_iv' ? "Practice trades are priced at the line's implied volatility (no tight quote on the trade's strikes), before bid/ask costs." : 'Practice trades are priced at an estimated volatility (no live option quotes), before bid/ask costs.'} Practice money. Not investment advice.</p>
        </Card>
      )}

      {toast && <div className="fixed left-1/2 -translate-x-1/2 bottom-28 z-50 max-w-sm w-[92%] rounded-2xl bg-slate-800 border border-slate-600 px-4 py-3 text-sm shadow-xl">{toast}</div>}

      {mine.length > 0 && (
        <Card className="mt-4">
          <div className="flex items-center justify-between">
            <div className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Your answers</div>
            <button onClick={() => navigate('/portfolio')} className="text-xs text-blue-300">Portfolio →</button>
          </div>
          <MyRecord rec={rec} />
          <TradesTotal t={rec?.trades} />
          <div className="mt-2 divide-y divide-slate-800">
            {mine.slice(0, 12).map((c) => (
              <div key={c.id} className="py-2 flex items-center justify-between text-sm">
                <span className="min-w-0">
                  <span className="block">{c.ticker} above {usd(c.level, c.level % 1 ? 2 : 0)} <span className="whitespace-nowrap">on {fmtDay(c.expiration)}</span></span>
                  {c.market_p != null && (
                    <span className="block text-[11px] text-slate-500 tabular-nums">Market gave {c.side.toUpperCase()} {pc(c.side === 'yes' ? c.market_p : 1 - c.market_p)}{c.close_price != null ? ` · closed ${usd(c.close_price, 2)}` : ''}</span>
                  )}
                  <TradeLine c={c} />
                </span>
                <span className="shrink-0 ml-2 flex items-center gap-2">
                  <b className={c.side === 'yes' ? 'text-green-300' : 'text-red-300'}>{c.side.toUpperCase()}</b>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${c.result === 'right' ? 'bg-green-500/20 text-green-200' : c.result === 'wrong' ? 'bg-red-500/20 text-red-200' : 'bg-slate-700 text-slate-300'}`}>{c.result}</span>
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {score && (
        <Card className="mt-4 text-sm">
          <div className="text-xs uppercase tracking-wider text-slate-400 font-semibold">The brain's Close Call record</div>
          {score.graded ? (
            <>
              <p className="mt-2 text-slate-300">{score.graded.toLocaleString()} question{score.graded === 1 ? '' : 's'} graded{score.days === 1 ? (score.graded > 1 ? ', all closing on the same day' : '') : score.days ? `, closing on ${score.days} different days` : ''}.
                The brain's lean picked the right side {pc(score.brain_side_right)} of the time{score.market_side_right != null ? `; the market's odds alone (above or below 50%) picked it ${pc(score.market_side_right)}` : ''}.</p>
              {score.disagree?.n > 0 && (
                <p className="mt-2 text-slate-300">Where its lean took the other side from the market's odds, it was right {score.disagree.right} of {score.disagree.n}{score.disagree.days > 1 ? ` (closing on ${score.disagree.days} days)` : score.disagree.n > 1 ? ', all closing on one day' : ''}. That is where it differs from simply following the market.</p>
              )}
              <p className="mt-2 text-slate-300">{VERDICT[score.verdict] ? VERDICT[score.verdict](score) : VERDICT.too_early(score)} <span className="text-slate-400 tabular-nums">(Brier {score.brier_brain} vs the market's {score.brier_market}; lower is better.)</span></p>
            </>
          ) : (
            <p className="mt-2 text-slate-300">New. Every trading day the brain asks itself one question on each of 15 big stocks (skipping any it already has open); each is graded after its expiration. {score.brain_open ? `${score.brain_open} of its questions are waiting now.` : ''}</p>
          )}
          <BrainQuestions graded={score.graded_recent} recent={score.recent} />
        </Card>
      )}
    </Page>
  );
}
