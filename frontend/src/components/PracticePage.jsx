// Practice portfolio: pretend money, real prices.
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { RefreshCw } from 'lucide-react';
import Page, { Card } from './ui/Page';
import Term from './ui/Term';
import { getPortfolio, closePosition, cancelQueued } from '../lib/api';

const usd = (v, d = 0) => `${v < 0 ? '−' : ''}$${Math.abs(Number(v || 0)).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })}`;
const signed = (v, d = 2) => `${v >= 0 ? '+' : '−'}$${Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })}`;

export default function PracticePage() {
  const navigate = useNavigate();
  const [s, setS] = useState({ loading: true });
  const [confirm, setConfirm] = useState(null);
  const [closing, setClosing] = useState(null);
  const [toast, setToast] = useState(null);

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
        setToast(`Sold ${p.ticker}: ${signed(pnl)} ${pnl >= 0 ? '🎉' : ''}`);
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
      {s.loading && <div className="mt-6 h-40 rounded-3xl bg-slate-800/50 animate-pulse" />}
      {s.error && <Card className="mt-6 text-sm text-red-200 border-red-500/40">Couldn't load your practice account: {s.error}</Card>}

      {a && (
        <Card className="mt-6 bg-gradient-to-br from-blue-600/25 to-slate-900/70 border-blue-400/30">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs uppercase tracking-wider text-blue-200 font-semibold">Account value</div>
              <div className="mt-1 text-4xl font-extrabold tabular-nums">{usd(a.total_value)}</div>
              <div className={`mt-1 text-sm font-bold ${a.total_pnl >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                {signed(a.total_pnl)} ({a.total_return_pct >= 0 ? '+' : ''}{a.total_return_pct.toFixed(2)}%) since you started with {usd(start)}
              </div>
            </div>
            {s.data?.summary?.performance_grade && (positions.length > 0 || Math.abs(a.total_pnl) > 0.005) && (
              <div className="text-center">
                <div className="w-12 h-12 rounded-2xl bg-white/10 flex items-center justify-center text-xl font-extrabold">{s.data.summary.performance_grade}</div>
                <div className="text-[10px] text-slate-400 mt-1">grade</div>
              </div>
            )}
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
          <b>The market is closed.</b> New trades wait and fill at the opening price ({mkt.next_open_text}), just like a real broker. Prices can jump overnight.
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
                  <div className="text-xs text-slate-400">{o.quantity} shares · fills at the opening price{o.side !== 'sell' ? ` · about ${usd(o.quantity * o.est_price)} now` : ''}</div>
                </div>
                <button onClick={() => cancel(o)} className="rounded-xl border border-slate-600 px-3 py-2 text-sm font-semibold hover:border-slate-400">Cancel</button>
              </Card>
            ))}
          </div>
        </>
      )}

      {a && positions.length === 0 && queued.length === 0 && (
        <Card className="mt-4 text-center py-7">
          <div className="text-4xl" aria-hidden>🧪</div>
          <div className="mt-2 font-bold text-lg">Nothing here yet</div>
          <p className="mt-1 text-sm text-slate-400 max-w-xs mx-auto">Share a belief, pick a stock idea and tap <Term k="paper trade">Paper trade</Term>. It lands here.</p>
          <button onClick={() => navigate('/chat')} className="mt-5 rounded-2xl bg-blue-600 hover:bg-blue-500 px-5 py-3 font-bold">Find an idea</button>
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
                      <div className="text-xs text-slate-400">{Number(p.quantity).toLocaleString()} shares @ {usd(p.avg_price, 2)} · now {usd(p.current_price, 2)}</div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className={`text-lg font-extrabold ${up ? 'text-green-300' : 'text-red-300'}`}>{signed(p.unrealized_pnl)}</div>
                      <div className={`text-xs ${up ? 'text-green-400/80' : 'text-red-400/80'}`}>{p.unrealized_pnl_pct >= 0 ? '+' : ''}{p.unrealized_pnl_pct.toFixed(2)}%</div>
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

      <p className="mt-5 text-[11px] text-slate-500">Practice account. No real money moves. Prices may be delayed.</p>

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
