// Invest real money through the person's OWN Alpaca account: preview, read, tick, confirm.
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { previewOrder, placeOrder, refreshBroker } from '../../lib/broker';

export default function RealMoneySheet({ open, onClose, pick, beliefId, defaultAmount = 100, broker }) {
  const [amount, setAmount] = useState(Math.min(defaultAmount, broker?.max_order_usd || defaultAmount));
  const [pv, setPv] = useState(null);
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [done, setDone] = useState(null);

  const reset = () => { setPv(null); setOk(false); setErr(null); setDone(null); };
  const close = () => { reset(); onClose(); };

  const doPreview = async () => {
    setBusy(true); setErr(null);
    try { setPv(await previewOrder({ ticker: pick.ticker, amount: Number(amount), beliefId, pickId: pick.pick_id })); }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  const doPlace = async () => {
    setBusy(true); setErr(null);
    try { setDone(await placeOrder(pv.preview_id)); refreshBroker(); }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  const paper = broker?.env !== 'live';

  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-[85] flex items-end sm:items-center justify-center bg-black/70 backdrop-blur-sm p-3"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={close} role="dialog" aria-modal="true" aria-label="Invest real money">
          <motion.div initial={{ y: 40 }} animate={{ y: 0 }} exit={{ y: 40 }} onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md rounded-3xl bg-slate-900 border border-slate-700 p-5 text-left">
            <div className="flex items-center justify-between">
              <div className="text-[11px] uppercase tracking-wider font-semibold text-amber-300">{paper ? 'Your Alpaca account · practice side' : 'Real money · your Alpaca account'}</div>
              <button onClick={close} className="text-slate-400 hover:text-white text-sm">Close</button>
            </div>
            <div className="mt-1 text-2xl font-extrabold">Buy {pick.ticker}</div>

            {done ? (
              <div className="mt-4">
                <div className="rounded-2xl bg-green-950/40 border border-green-500/30 p-4 text-green-100">
                  ✓ Order sent to Alpaca ({done.alpaca_status}). It fills at the market price; check your Alpaca app for the final details.
                </div>
                <button onClick={close} className="mt-4 w-full rounded-2xl bg-blue-600 py-3 font-bold">Done</button>
              </div>
            ) : !pv ? (
              <div className="mt-4 space-y-3">
                <label className="block">
                  <span className="text-xs font-semibold text-slate-300">Amount in dollars (up to ${(broker?.max_order_usd || 1000).toLocaleString()})</span>
                  <input type="number" min="1" max={broker?.max_order_usd || 1000} value={amount} onChange={(e) => setAmount(e.target.value)}
                    className="mt-1 w-full rounded-2xl bg-slate-950/70 border border-slate-700 focus:border-blue-400 px-3.5 py-3 text-lg text-white focus:outline-none" />
                </label>
                {broker?.account && <p className="text-xs text-slate-400">Buying power: ${broker.account.buying_power.toLocaleString(undefined, { maximumFractionDigits: 2 })}</p>}
                {err && <div className="rounded-2xl bg-red-950/50 border border-red-500/40 px-3.5 py-2.5 text-sm text-red-200" role="alert">{err}</div>}
                <button onClick={doPreview} disabled={busy || !(Number(amount) >= 1)} className="w-full rounded-2xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 py-3.5 font-bold">
                  {busy ? 'Checking…' : 'Preview order'}
                </button>
              </div>
            ) : (
              <div className="mt-4 space-y-3">
                <div className="rounded-2xl bg-slate-800/70 border border-slate-700 p-3.5 text-sm text-slate-100 leading-relaxed">{pv.plain}</div>
                {pv.warnings.map((w) => <div key={w} className="rounded-2xl bg-amber-400/10 border border-amber-300/30 px-3.5 py-2.5 text-sm text-amber-100">{w}</div>)}
                <label className="flex gap-3 items-start text-sm text-slate-200">
                  <input type="checkbox" checked={ok} onChange={(e) => setOk(e.target.checked)} className="mt-1 w-5 h-5" />
                  <span>{paper
                    ? "I understand this places an order in my Alpaca practice account (no real money), and MarketPlayground's ideas are for education, not advice."
                    : "I understand this places a real order in my own account, I can lose money, and MarketPlayground's ideas are for education, not advice."}</span>
                </label>
                {err && <div className="rounded-2xl bg-red-950/50 border border-red-500/40 px-3.5 py-2.5 text-sm text-red-200" role="alert">{err}</div>}
                <div className="grid grid-cols-2 gap-2">
                  <button onClick={reset} className="rounded-2xl border border-slate-700 bg-slate-800 py-3 font-bold">Change</button>
                  <button onClick={doPlace} disabled={!ok || busy} className="rounded-2xl bg-green-600 hover:bg-green-500 disabled:opacity-40 py-3 font-bold">
                    {busy ? 'Sending…' : `Buy $${Number(pv.amount_usd).toLocaleString()}`}
                  </button>
                </div>
                <p className="text-[11px] text-slate-500">This preview expires in 2 minutes.</p>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
