// Public "my real-money journey": every filled real trade from the owner's own Alpaca account, wins and losses.
// Built to be screen-recorded for social: big numbers, one card per trade, nothing hidden or cherry-picked.
import React, { useEffect, useState } from 'react';
import Page, { Card, pct } from './ui/Page';
import { getJourney } from '../lib/broker';

const day = (iso) => (iso ? new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '');
const tone = (v) => (v == null ? 'text-slate-300' : v >= 0 ? 'text-green-300' : 'text-red-300');

export default function JourneyPage() {
  const [j, setJ] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { getJourney().then(setJ).catch((e) => setErr(e.message)); }, []);

  const s = j?.summary;
  const who = j?.name ? `${j.name}'s` : 'My';
  return (
    <Page title={`${who} real-money journey`} subtitle="Real trades from my own brokerage account. Every one, wins and losses.">
      {err && <Card className="mt-6 text-red-200">{err}</Card>}
      {!j && !err && <Card className="mt-6 text-slate-400">Loading…</Card>}
      {j && !j.enabled && (
        <Card className="mt-6">
          <div className="font-bold">Not public yet</div>
          <p className="mt-1 text-sm text-slate-300">The real-money journey starts soon. Practice with play money in the meantime.</p>
        </Card>
      )}
      {j?.enabled && (
        <>
          <Card className="mt-6">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold uppercase rounded-full px-2 py-0.5 bg-amber-400/15 text-amber-200">{j.env === 'live' ? 'Real money' : 'Alpaca practice side'}</span>
              {j.started && <span className="text-xs text-slate-400">since {day(j.started)}</span>}
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2 text-center">
              <div>
                <div className={`text-2xl font-extrabold ${tone(s.return_on_invested)}`}>{pct(s.return_on_invested)}</div>
                <div className="text-[11px] text-slate-400 leading-tight">on money put in</div>
              </div>
              <div>
                <div className="text-2xl font-extrabold">{s.closed ? `${s.wins}/${s.closed}` : '—'}</div>
                <div className="text-[11px] text-slate-400 leading-tight">closed trades won</div>
              </div>
              <div>
                <div className="text-2xl font-extrabold">{s.open}</div>
                <div className="text-[11px] text-slate-400 leading-tight">still open</div>
              </div>
            </div>
            {j.dollars && s.invested_usd != null && (
              <p className="mt-3 text-center text-sm text-slate-300">
                ${s.invested_usd.toLocaleString()} put in · <span className={tone(s.pl_usd)}>{s.pl_usd >= 0 ? '+' : '-'}${Math.abs(s.pl_usd).toLocaleString()}</span>
              </p>
            )}
            <p className="mt-3 text-[11px] text-slate-500 leading-snug">
              Open trades are valued at today's price. "vs S&P" compares each trade with the S&P 500 (SPY) over the same days.{' '}
              {j.trades} filled order{j.trades !== 1 ? 's' : ''} so far; none are left out.
            </p>
          </Card>

          {j.lots.length === 0 && <Card className="mt-3 text-slate-300">No trades yet. The first one shows up here the moment it fills.</Card>}
          <div className="mt-3 space-y-2.5">
            {j.lots.map((l, i) => (
              <Card key={`${l.symbol}-${l.opened}-${i}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-bold break-words">{l.label}</div>
                    <div className="text-xs text-slate-400">
                      {l.kind === 'option' ? 'Option' : 'Stock'} · bought {day(l.opened)}{l.closed ? ` · sold ${day(l.closed)}` : ' · still open'}
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className={`text-xl font-extrabold ${tone(l.return)}`}>{pct(l.return)}</div>
                    {l.vs_spy != null && <div className={`text-xs ${tone(l.vs_spy)}`}>{pct(l.vs_spy)} vs S&P</div>}
                  </div>
                </div>
                {l.belief && <p className="mt-2 text-sm text-slate-300 italic break-words">“{l.belief}”</p>}
                <div className="mt-1.5 text-[11px] text-slate-500">
                  ${l.entry.toFixed(2)} → {l.now_or_exit != null ? `$${l.now_or_exit.toFixed(2)}` : 'no price right now'}{l.kind === 'option' ? ' per share of the contract' : ''}
                  {j.dollars && l.cost_usd != null ? ` · $${l.cost_usd.toLocaleString()} in` : ''}
                </div>
              </Card>
            ))}
          </div>
          <p className="mt-4 text-[11px] text-slate-500 leading-snug">
            My own money and my own decisions, shown for education. This isn't financial advice or a recommendation to buy or sell anything.
            Past results don't predict future results, and options can lose their whole value.
          </p>
        </>
      )}
    </Page>
  );
}
