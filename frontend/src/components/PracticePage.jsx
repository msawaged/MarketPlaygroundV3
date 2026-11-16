// Practice portfolio: pretend money, real prices.
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { RefreshCw, LineChart } from 'lucide-react';
import Page, { Card } from './ui/Page';
import Term from './ui/Term';
import { getPortfolio, closePosition, cancelQueued, closeOption } from '../lib/api';

const shares = (q) => { const n = Number(q || 0); return `${n.toLocaleString('en-US', { maximumFractionDigits: 4 })} share${n === 1 ? '' : 's'}`; };
const usd = (v, d = 0) => `${v < 0 ? '−' : ''}$${Math.abs(Number(v || 0)).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })}`;
const signed = (v, d = 2) => `${v >= 0 ? '+' : '−'}$${Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })}`;

// "+1.23%"; tiny moves read "<0.01%" instead of a misleading "-0.00%".
function fmtPct(v) {
  const x = Number(v) || 0;
  if (x !== 0 && Math.abs(x) < 0.005) return `${x > 0 ? '+' : '−'}<0.01%`;
  return `${x >= 0 ? '+' : '−'}${Math.abs(x).toFixed(2)}%`;
}

// "Buy $180 call · Sell $210 call": an options row is unreadable without its strikes.
function strikeText(k) { const n = Number(k); return Number.isInteger(n) ? `$${n}` : `$${n.toFixed(2)}`; }
function legsText(legs) {
  if (!Array.isArray(legs) || !legs.length) return '';
  return legs.map((l) => {
    if (l.instrument === 'stock') return `${l.action === 'Sell' ? 'Short' : 'Own'} ${l.quantity || 100} shares`;
    if (l.strike_price == null) return '';
    return `${l.action} ${strikeText(l.strike_price)} ${String(l.option_type || '').toLowerCase()}`.trim();
  }).filter(Boolean).join(' · ');
}

const shortDate = (iso) => {
  if (!iso) return '';
  const d = new Date(String(iso).length === 10 ? `${iso}T12:00:00` : iso);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: d.getFullYear() === new Date().getFullYear() ? undefined : 'numeric' });
};

// One sold / closed / expired trade: what it cost, what came back, the gain. These are the numbers that moved the cash.
function ClosedRow({ t }) {
  const known = t.pnl != null;
  const up = known && t.pnl >= 0;
  const opt = t.kind === 'options';
  const tag = opt ? (t.expired ? 'Expired' : 'Closed') : (t.position_type === 'short' ? 'Covered' : 'Sold');
  return (
    <Card className="py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-lg font-extrabold">{t.ticker}</span>
            {opt && <span className="text-[10px] font-bold uppercase rounded-full px-2 py-0.5 bg-blue-500/15 text-blue-200">{t.structure}</span>}
            <span className="text-[10px] font-bold uppercase rounded-full px-2 py-0.5 bg-slate-800 text-slate-300">{tag} {shortDate(t.closed_at)}</span>
          </div>
          {opt ? (
            <>
              {legsText(t.legs) && <div className="text-xs text-slate-300 mt-0.5">{legsText(t.legs)}</div>}
              <div className="text-xs text-slate-400">{t.contracts} contract{t.contracts > 1 ? 's' : ''} · set aside {usd(t.cost)} · got back {usd(t.proceeds)}{t.expired && t.proceeds === 0 ? ' (expired worthless)' : ''}</div>
            </>
          ) : known ? (
            <div className="text-xs text-slate-400">{shares(t.quantity)} · bought {usd(t.avg_price, 2)} · sold {usd(t.exit_price, 2)} · got {usd(t.proceeds)}</div>
          ) : (
            <div className="text-xs text-slate-400">{shares(t.quantity)} sold at {usd(t.exit_price, 2)} for {usd(t.proceeds)} · cost not recorded (an older sale)</div>
          )}
        </div>
        {known && (
          <div className="text-right shrink-0">
            <div className={`text-base font-extrabold ${up ? 'text-green-300' : 'text-red-300'}`}>{signed(t.pnl)}</div>
            {t.pnl_pct != null && <div className={`text-xs ${up ? 'text-green-400/80' : 'text-red-400/80'}`}>{fmtPct(t.pnl_pct)}</div>}
          </div>
        )}
      </div>
      {t.belief && <p className="mt-1.5 text-xs text-slate-400 italic truncate">“{t.belief}”</p>}
    </Card>
  );
}

export default function PracticePage() {
  const navigate = useNavigate();
  const [s, setS] = useState({ loading: true });
  const [confirm, setConfirm] = useState(null);
  const [closing, setClosing] = useState(null);
  const [toast, setToast] = useState(null);
  const [allClosed, setAllClosed] = useState(false);

  const load = useCallback(() => {
    setS((x) => ({ ...x, refreshing: true }));
    getPortfolio().then((d) => setS({ data: d })).catch((e) => setS({ error: e.message }));
  }, []);
  useEffect(() => { load(); const id = setInterval(load, 60000); return () => clearInterval(id); }, [load]);

  const sell = async (p) => {
    setClosing(p.position_id);
    try {
      const r = await closePosition(p.position_id);
      if (r?.status === 'queued') {
        setToast(r.message);
        setTimeout(() => setToast(null), 5000);
      } else {
        const pnl = Number(r?.realized_pnl ?? 0);
        setToast(`Sold ${p.ticker}: ${signed(pnl)} `);
        setTimeout(() => setToast(null), 3500);
      }
      load();
    } catch (e) {
      setToast(`Couldn't sell: ${e.message}`);
      setTimeout(() => setToast(null), 3500);
    } finally {
      setClosing(null); setConfirm(null);
    }
  };

  const cancel = async (o) => {
    try { await cancelQueued(o.order_id); setToast(`Cancelled the queued ${o.ticker} order`); }
    catch (e) { setToast(`Couldn't cancel: ${e.message}`); }
    setTimeout(() => setToast(null), 3500);
    load();
  };

  const a = s.data?.account;
  const positions = s.data?.positions || [];
  const queued = s.data?.queued_orders || [];
  const opts = s.data?.option_positions || [];
  const closedTrades = s.data?.closed_trades || [];
  const closedKnown = closedTrades.filter((t) => t.pnl != null);
  const realized = closedKnown.reduce((x, t) => x + Number(t.pnl), 0);
  const closedShown = allClosed ? closedTrades : closedTrades.slice(0, 5);
  const closeOpt = async (o) => {
    setClosing(o.position_id);
    try {
      const r = await closeOption(o.position_id);
      setToast(r?.status === 'success' ? r.message : `Couldn't close: ${r?.message || 'try again'}`);
      load();
    } catch (e) { setToast(`Couldn't close: ${e.message}`); }
    finally { setClosing(null); setConfirm(null); setTimeout(() => setToast(null), 3500); }
  };
  const mkt = s.data?.market;
  const sellQueued = new Set(queued.filter((o) => o.side === 'sell').map((o) => o.ticker));
  const start = s.data?.summary?.starting_balance || 100000;
  const investedPct = a ? Math.min(100, (a.equity_value / Math.max(1, a.total_value)) * 100) : 0;

  return (
    <Page
      title="Practice"
      subtitle="Pretend $100,000. Real prices. Zero risk."
      right={
        <button onClick={load} aria-label="Refresh" className="mt-2 w-10 h-10 rounded-2xl bg-slate-800/80 border border-slate-700 flex items-center justify-center hover:border-blue-400">
          <RefreshCw className={`w-4 h-4 ${s.refreshing ? 'animate-spin' : ''}`} />
        </button>
      }
    >
      <button onClick={() => navigate('/close-call')} className="mt-4 w-full flex items-center justify-between rounded-2xl border border-slate-700 bg-slate-900/60 px-4 py-2.5 text-left text-sm hover:border-blue-400">
        <span><b>Close Call</b> <span className="text-slate-400">· will it close above the line? Fixed risk, fixed payout.</span></span>
        <span className="text-blue-300" aria-hidden>→</span>
      </button>
      {s.loading && <div className="mt-6 h-40 rounded-3xl bg-slate-800/50 animate-pulse" />}
      {s.error && <Card className="mt-6 text-sm text-red-200 border-red-500/40">Couldn't load your practice account: {s.error}</Card>}

      {a && (
        <Card className="mt-6 bg-gradient-to-br from-blue-600/25 to-slate-900/70 border-blue-400/30">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs uppercase tracking-wider text-blue-200 font-semibold">Account value</div>
              <div className="mt-1 text-4xl font-extrabold tabular-nums">{usd(a.total_value)}</div>
              <div className={`mt-1 text-sm font-bold ${a.total_pnl >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                {signed(a.total_pnl)} ({fmtPct(a.total_return_pct)}) since you started with {usd(start)}
              </div>
            </div>
          </div>
          <div className="mt-4 h-2.5 rounded-full bg-slate-800 overflow-hidden flex">
            <motion.div className="h-full bg-blue-400" initial={{ width: 0 }} animate={{ width: `${investedPct}%` }} transition={{ duration: 0.8 }} />
          </div>
          <div className="mt-1.5 flex justify-between text-xs text-slate-300">
            <span><span className="inline-block w-2 h-2 rounded-full bg-blue-400 mr-1" />Invested {usd(a.equity_value)}</span>
            <span>Cash {usd(a.cash_balance)}</span>
          </div>
        </Card>
      )}

      {mkt && !mkt.is_open && (
        <div className="mt-4 rounded-2xl bg-amber-400/10 border border-amber-300/30 px-4 py-3 text-sm text-amber-100" role="status">
          <b>The market is closed.</b> New share trades wait and fill at the opening price ({mkt.next_open_text}), just like a real broker. Prices can jump overnight. Practice options and Close Calls open right away at an estimate from the last prices.
        </div>
      )}

      {queued.length > 0 && (
        <>
          <div className="mt-6 text-xs uppercase tracking-wider text-slate-400 font-semibold">Waiting for the open</div>
          <div className="mt-2 space-y-2">
            {queued.map((o) => (
              <Card key={o.order_id} className="flex items-center justify-between gap-3 py-3">
                <div>
                  <div className="font-bold">{o.side === 'sell' ? 'Sell' : 'Buy'} {o.ticker}</div>
                  <div className="text-xs text-slate-400">{shares(o.quantity)} · fills at the opening price{o.side !== 'sell' ? ` · about ${usd(o.quantity * o.est_price)} now` : ''}</div>
                </div>
                <button onClick={() => cancel(o)} className="rounded-xl border border-slate-600 px-3 py-2 text-sm font-semibold hover:border-slate-400">Cancel</button>
              </Card>
            ))}
          </div>
        </>
      )}

      {a && positions.length === 0 && queued.length === 0 && opts.length === 0 && (
        <Card className="mt-4 text-center py-7">
          <LineChart className="mx-auto w-9 h-9 text-blue-300" aria-hidden />
          <div className="mt-2 font-bold text-lg">{closedTrades.length ? 'No open positions' : 'Nothing here yet'}</div>
          <p className="mt-1 text-sm text-slate-400 max-w-xs mx-auto">{closedTrades.length ? 'Your past trades are below. ' : ''}Share a belief, pick a stock idea and tap <Term k="paper trade">Paper trade</Term>. It lands here.</p>
          <button onClick={() => navigate('/chat')} className="mt-5 rounded-2xl bg-blue-600 hover:bg-blue-500 px-5 py-3 font-bold">Find an idea</button>
          <p className="mt-4 text-xs text-slate-500">Calls you made without practice money are in{' '}
            <button onClick={() => navigate('/my')} className="underline text-slate-300">My beliefs</button>.</p>
        </Card>
      )}

      {positions.length > 0 && <div className="mt-6 text-xs uppercase tracking-wider text-slate-400 font-semibold">Your positions</div>}
      <div className="mt-2 space-y-3">
        <AnimatePresence>
          {positions.map((p) => {
            const up = p.unrealized_pnl >= 0;
            return (
              <motion.div key={p.position_id || p.strategy_id} layout initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, x: -40 }}>
                <Card>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xl font-extrabold">{p.ticker}</span>
                        <span className="text-[10px] font-bold uppercase rounded-full px-2 py-0.5 bg-slate-800 text-slate-300">{p.position_type}</span>
                      </div>
                      <div className="text-xs text-slate-400">{shares(p.quantity)} @ {usd(p.avg_price, 2)} · now {usd(p.current_price, 2)}</div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className={`text-lg font-extrabold ${up ? 'text-green-300' : 'text-red-300'}`}>{signed(p.unrealized_pnl)}</div>
                      <div className={`text-xs ${up ? 'text-green-400/80' : 'text-red-400/80'}`}>{fmtPct(p.unrealized_pnl_pct)}</div>
                    </div>
                  </div>
                  {p.belief && <p className="mt-2 text-sm text-slate-300 italic truncate">“{p.belief}”</p>}
                  <div className="mt-3 flex items-center justify-between">
                    <span className="text-xs text-slate-500">Worth {usd(p.market_value)}</span>
                    {confirm === p.position_id ? (
                      <span className="flex gap-2">
                        <button onClick={() => setConfirm(null)} className="rounded-xl px-3 py-2 text-xs font-semibold bg-slate-800 border border-slate-700">Keep</button>
                        <button onClick={() => sell(p)} disabled={closing === p.position_id} className="rounded-xl px-3 py-2 text-xs font-bold bg-red-600 hover:bg-red-500 disabled:opacity-60">
                          {closing === p.position_id ? 'Selling…' : mkt && !mkt.is_open ? 'Sell at the open' : `Sell for ${usd(p.market_value)}`}
                        </button>
                      </span>
                    ) : (
                      sellQueued.has(p.ticker)
                        ? <span className="rounded-xl px-3 py-2 text-xs font-semibold bg-amber-400/10 border border-amber-300/30 text-amber-100">Sale queued</span>
                        : <button onClick={() => setConfirm(p.position_id)} disabled={!p.position_id} className="rounded-xl px-3 py-2 text-xs font-semibold bg-slate-800 border border-slate-700 hover:border-red-400">Sell</button>
                    )}
                  </div>
                </Card>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>

      {opts.length > 0 && <div className="mt-6 text-xs uppercase tracking-wider text-slate-400 font-semibold">Your options trades</div>}
      <div className="mt-2 space-y-3">
        {opts.map((o) => {
          const up = o.pnl >= 0;
          return (
            <Card key={o.position_id}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xl font-extrabold">{o.ticker}</span>
                    <span className="text-[10px] font-bold uppercase rounded-full px-2 py-0.5 bg-blue-500/15 text-blue-200">{o.structure}</span>
                  </div>
                  {legsText(o.legs) && <div className="text-xs text-slate-300 mt-0.5">{legsText(o.legs)}</div>}
                  <div className="text-xs text-slate-400">{o.contracts} contract{o.contracts > 1 ? 's' : ''} · expires {new Date(o.expiration + 'T12:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })} · stock {usd(o.spot, 2)}</div>
                </div>
                <div className="text-right shrink-0">
                  <div className={`text-lg font-extrabold ${up ? 'text-green-300' : 'text-red-300'}`}>{signed(o.pnl)}</div>
                  <div className={`text-xs ${up ? 'text-green-400/80' : 'text-red-400/80'}`}>{o.pnl_pct >= 0 ? '+' : ''}{o.pnl_pct.toFixed(1)}%</div>
                </div>
              </div>
              {o.belief && <p className="mt-2 text-sm text-slate-300 italic truncate">“{o.belief}”</p>}
              <div className="mt-3 flex items-center justify-between">
                <span className="text-xs text-slate-500">Worth about {usd(o.value)} (estimated)</span>
                {confirm === o.position_id ? (
                  <span className="flex gap-2">
                    <button onClick={() => setConfirm(null)} className="rounded-xl px-3 py-2 text-xs font-semibold bg-slate-800 border border-slate-700">Keep</button>
                    <button onClick={() => closeOpt(o)} disabled={closing === o.position_id} className="rounded-xl px-3 py-2 text-xs font-bold bg-red-600 hover:bg-red-500 disabled:opacity-60">
                      {closing === o.position_id ? 'Closing…' : `Close for about ${usd(o.value)}`}
                    </button>
                  </span>
                ) : (
                  <button onClick={() => setConfirm(o.position_id)} className="rounded-xl px-3 py-2 text-xs font-semibold bg-slate-800 border border-slate-700 hover:border-red-400">Close</button>
                )}
              </div>
            </Card>
          );
        })}
      </div>

      {closedTrades.length > 0 && (
        <>
          <div className="mt-6 flex items-baseline justify-between gap-3">
            <span className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Closed trades</span>
            {closedKnown.length > 0 && (
              <span className="text-xs text-slate-400">
                Locked in: <b className={realized >= 0 ? 'text-green-300' : 'text-red-300'}>{signed(realized, 0)}</b> on {closedKnown.length} trade{closedKnown.length === 1 ? '' : 's'}
              </span>
            )}
          </div>
          <div className="mt-2 space-y-2">
            {closedShown.map((t) => <ClosedRow key={`${t.kind}-${t.id}`} t={t} />)}
          </div>
          {closedTrades.length > 5 && (
            <button onClick={() => setAllClosed((v) => !v)} className="mt-2 w-full rounded-xl border border-slate-700 py-2 text-xs font-semibold text-slate-300 hover:border-slate-500">
              {allClosed ? 'Show fewer' : `Show all ${closedTrades.length}`}
            </button>
          )}
          <p className="mt-2 text-[11px] text-slate-500">Already counted in your account value above. Options amounts are estimates.</p>
        </>
      )}

      <p className="mt-5 text-[11px] text-slate-500">Practice account. No real money moves. Prices may be delayed; options prices are estimates.</p>

      <AnimatePresence>
        {toast && (
          <motion.div initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 30, opacity: 0 }}
            className="fixed left-1/2 -translate-x-1/2 bottom-24 z-[70] rounded-2xl bg-slate-800 border border-slate-600 px-4 py-3 text-sm font-semibold shadow-2xl" role="status">
            {toast}
          </motion.div>
        )}
      </AnimatePresence>
    </Page>
  );
}
