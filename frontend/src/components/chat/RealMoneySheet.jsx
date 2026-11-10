// Real money through the person's OWN Alpaca account: preview, read, tick, confirm.
// Three kinds of order:
//   - stock:  buy a dollar amount of a stock/ETF (market order)
//   - option: buy one listed call or put (limit order; the most you can lose is what you pay)
//   - close:  sell something you hold (stocks at market, options with a limit)
import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { previewOrder, previewOptionOrder, previewClose, placeOrder, refreshBroker } from '../../lib/broker';

const usd = (v) => `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function RealMoneySheet({ open, onClose, pick, beliefId, defaultAmount = 100, broker, leg, position, onDone }) {
  const mode = position ? 'close' : leg ? 'option' : 'stock';
  const cap = broker?.max_order_usd || 1000;
  const [amount, setAmount] = useState(Math.min(defaultAmount, cap));
  const [contracts, setContracts] = useState(1);
  const [limit, setLimit] = useState('');
  // Exits, in whole percent. Starting values are only a starting point; the person sets them.
  const [useExits, setUseExits] = useState(false);
  const [tpPct, setTpPct] = useState(mode === 'option' ? 50 : 20);
  const [slPct, setSlPct] = useState(mode === 'option' ? 40 : 10);
  const exits = useExits ? { tp: Number(tpPct) > 0 ? Number(tpPct) / 100 : null, sl: Number(slPct) > 0 ? Number(slPct) / 100 : null } : null;
  const [pv, setPv] = useState(null);
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [done, setDone] = useState(null);

  const reset = () => { setPv(null); setOk(false); setErr(null); setDone(null); };
  const close = () => { reset(); onClose(); };

  const doPreview = async () => {
    setBusy(true); setErr(null);
    try {
      if (mode === 'option') {
        setPv(await previewOptionOrder({ leg, underlying: pick.ticker, contracts, limitPrice: limit || null, beliefId, pickId: pick.pick_id, exits }));
      } else if (mode === 'close') {
        setPv(await previewClose({ symbol: position.symbol, limitPrice: limit || null }));
      } else {
        setPv(await previewOrder({ ticker: pick.ticker, amount: Number(amount), beliefId, pickId: pick.pick_id, exits }));
      }
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  const doPlace = async () => {
    setBusy(true); setErr(null);
    try { setDone(await placeOrder(pv.preview_id)); refreshBroker(); onDone && onDone(); }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  const paper = broker?.env !== 'live';
  const optType = String(leg?.option_type || '').toLowerCase();
  const title = mode === 'close' ? `Sell ${position.kind === 'option' ? position.label.replace(/^[\d.]+ /, '') : position.symbol}`
    : mode === 'option' ? `Buy a ${pick.ticker} ${optType}` : `Buy ${pick.ticker}`;
  const sell = pv?.side === 'sell';
  const goLabel = !pv ? '' : sell ? `Sell · ${usd(pv.amount_usd)}` : pv.kind === 'option'
    ? `Buy ${pv.contracts} contract${pv.contracts !== 1 ? 's' : ''} · ${usd(pv.total_usd)}` : `Buy ${usd(pv.amount_usd)}`;
  const input = 'mt-1 w-full rounded-2xl bg-slate-950/70 border border-slate-700 focus:border-blue-400 px-3.5 py-3 text-lg text-white focus:outline-none';

  // Portal to <body>: a parent with backdrop-blur would otherwise trap this "fixed" overlay inside itself.
  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-[85] flex items-end sm:items-center justify-center bg-black/70 backdrop-blur-sm p-3"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={close} role="dialog" aria-modal="true" aria-label="Real-money order">
          <motion.div initial={{ y: 40 }} animate={{ y: 0 }} exit={{ y: 40 }} onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md rounded-3xl bg-slate-900 border border-slate-700 p-5 text-left max-h-[92vh] overflow-y-auto">
            <div className="flex items-center justify-between">
              <div className="text-[11px] uppercase tracking-wider font-semibold text-amber-300">{paper ? 'Your Alpaca account · practice side' : 'Real money · your Alpaca account'}</div>
              <button onClick={close} className="text-slate-400 hover:text-white text-sm">Close</button>
            </div>
            <div className="mt-1 text-2xl font-extrabold break-words">{title}</div>
            {mode === 'option' && !pv && !done && (
              <p className="mt-1 text-sm text-slate-400">${Number(leg.strike_price)} strike · expires {String(leg.expiration).slice(0, 10)}. We'll use the closest contract listed on the exchange.</p>
            )}

            {done ? (
              <div className="mt-4">
                <div className="rounded-2xl bg-green-950/40 border border-green-500/30 p-4 text-green-100">
                  ✓ Order sent to Alpaca ({done.alpaca_status}). {pv?.kind === 'option' || pv?.limit_price
                    ? "It's a limit order: it fills only at your price or better, and is cancelled at the close if it doesn't."
                    : 'It fills at the market price.'} You'll see it under Account → Your brokerage.
                </div>
                {done.warning && <div className="mt-2 rounded-2xl bg-amber-400/10 border border-amber-300/30 px-3.5 py-2.5 text-sm text-amber-100">{done.warning}</div>}
                <button onClick={close} className="mt-4 w-full rounded-2xl bg-blue-600 py-3 font-bold">Done</button>
              </div>
            ) : !pv ? (
              <div className="mt-4 space-y-3">
                {mode === 'stock' && (
                  <label className="block">
                    <span className="text-xs font-semibold text-slate-300">Amount in dollars (up to ${cap.toLocaleString()})</span>
                    <input type="number" inputMode="decimal" min="1" max={cap} value={amount} onChange={(e) => setAmount(e.target.value)} className={input} />
                  </label>
                )}
                {mode === 'option' && (
                  <>
                    <label className="block">
                      <span className="text-xs font-semibold text-slate-300">Contracts (each controls 100 shares)</span>
                      <input type="number" inputMode="numeric" min="1" max="20" step="1" value={contracts} onChange={(e) => setContracts(e.target.value)} className={input} />
                    </label>
                    <label className="block">
                      <span className="text-xs font-semibold text-slate-300">Most you'll pay per share (optional; blank = current asking price)</span>
                      <input type="number" inputMode="decimal" min="0.01" step="0.01" placeholder="Asking price" value={limit} onChange={(e) => setLimit(e.target.value)} className={input} />
                    </label>
                  </>
                )}
                {mode === 'close' && (
                  <>
                    <p className="text-sm text-slate-300">You hold {position.label}. This sells all of it.</p>
                    {position.kind === 'option' && (
                      <label className="block">
                        <span className="text-xs font-semibold text-slate-300">Least you'll accept per share (optional; blank = current bid)</span>
                        <input type="number" inputMode="decimal" min="0.01" step="0.01" placeholder="Current bid" value={limit} onChange={(e) => setLimit(e.target.value)} className={input} />
                      </label>
                    )}
                  </>
                )}
                {mode !== 'close' && (
                  <div className="rounded-2xl border border-slate-700 bg-slate-950/40 p-3">
                    <label className="flex items-center gap-3 text-sm font-semibold">
                      <input type="checkbox" checked={useExits} onChange={(e) => setUseExits(e.target.checked)} className="w-5 h-5" />
                      Add take-profit and max loss
                    </label>
                    {useExits && (
                      <>
                        <div className="mt-2 grid grid-cols-2 gap-2">
                          <label className="block">
                            <span className="text-[11px] text-slate-400">Take profit at +%</span>
                            <input type="number" inputMode="decimal" min="1" max="1000" value={tpPct} onChange={(e) => setTpPct(e.target.value)} className={input} />
                          </label>
                          <label className="block">
                            <span className="text-[11px] text-slate-400">Max loss −%</span>
                            <input type="number" inputMode="decimal" min="1" max="95" value={slPct} onChange={(e) => setSlPct(e.target.value)} className={input} />
                          </label>
                        </div>
                        <p className="mt-2 text-[11px] text-slate-400 leading-snug">
                          {mode === 'option'
                            ? 'Max loss: a stop order waits at Alpaca, renewed each trading morning. Take profit: MarketPlayground watches the price and sells, usually within seconds in market hours. Leave a box at 0 to skip it.'
                            : 'Both wait at Alpaca, even if MarketPlayground is offline. Needs whole shares, so the amount rounds down. Leave a box at 0 to skip it.'}
                        </p>
                      </>
                    )}
                  </div>
                )}
                {broker?.account && mode !== 'close' && (
                  <p className="text-xs text-slate-400">{mode === 'option' ? 'Options buying power' : 'Buying power'}: {usd(mode === 'option' ? (broker.account.options_buying_power ?? broker.account.buying_power) : broker.account.buying_power)}</p>
                )}
                {err && <div className="rounded-2xl bg-red-950/50 border border-red-500/40 px-3.5 py-2.5 text-sm text-red-200" role="alert">{err}</div>}
                <button onClick={doPreview}
                  disabled={busy || (mode === 'stock' && !(Number(amount) >= 1)) || (mode === 'option' && !(Number(contracts) >= 1))}
                  className="w-full rounded-2xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 py-3.5 font-bold">
                  {busy ? 'Checking…' : 'Preview order'}
                </button>
              </div>
            ) : (
              <div className="mt-4 space-y-3">
                {pv.kind === 'option' && (
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="rounded-2xl bg-slate-800/70 border border-slate-700 p-3"><div className="text-[11px] text-slate-400">Contract</div><div className="font-bold leading-snug">{pv.label}</div></div>
                    <div className="rounded-2xl bg-slate-800/70 border border-slate-700 p-3"><div className="text-[11px] text-slate-400">{sell ? 'Least per share' : 'Most per share'}</div><div className="font-bold">{usd(pv.limit_price)}</div><div className="text-[11px] text-slate-500">bid {usd(pv.bid)} · ask {usd(pv.ask)}</div></div>
                    {!sell && <div className="rounded-2xl bg-slate-800/70 border border-slate-700 p-3"><div className="text-[11px] text-slate-400">Most you can lose</div><div className="font-bold text-red-300">{usd(pv.max_loss_usd)}</div></div>}
                    {!sell && <div className="rounded-2xl bg-slate-800/70 border border-slate-700 p-3"><div className="text-[11px] text-slate-400">Breakeven at expiration</div><div className="font-bold">{usd(pv.breakeven)}</div></div>}
                  </div>
                )}
                {pv.exits && (
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    {pv.exits.tp_price != null && <div className="rounded-2xl bg-green-950/30 border border-green-500/30 p-3"><div className="text-[11px] text-green-200/80">Take profit{pv.kind === 'option' ? ' (about)' : ''}</div><div className="font-bold text-green-200">{usd(pv.exits.tp_price)} · +{Math.round(pv.exits.tp_pct * 100)}%</div></div>}
                    {pv.exits.sl_price != null && <div className="rounded-2xl bg-red-950/30 border border-red-500/30 p-3"><div className="text-[11px] text-red-200/80">Max loss{pv.kind === 'option' ? ' (about)' : ''}</div><div className="font-bold text-red-200">{usd(pv.exits.sl_price)} · −{Math.round(pv.exits.sl_pct * 100)}%</div></div>}
                  </div>
                )}
                <div className="rounded-2xl bg-slate-800/70 border border-slate-700 p-3.5 text-sm text-slate-100 leading-relaxed">{pv.plain}</div>
                {pv.warnings.map((w) => <div key={w} className="rounded-2xl bg-amber-400/10 border border-amber-300/30 px-3.5 py-2.5 text-sm text-amber-100">{w}</div>)}
                <label className="flex gap-3 items-start text-sm text-slate-200">
                  <input type="checkbox" checked={ok} onChange={(e) => setOk(e.target.checked)} className="mt-1 w-5 h-5 shrink-0" />
                  <span>{paper
                    ? "I understand this places an order in my Alpaca practice account (no real money), and MarketPlayground's ideas are for education, not advice."
                    : "I understand this places a real order in my own account, I can lose money, and MarketPlayground's ideas are for education, not advice."}</span>
                </label>
                {err && <div className="rounded-2xl bg-red-950/50 border border-red-500/40 px-3.5 py-2.5 text-sm text-red-200" role="alert">{err}</div>}
                <div className="grid grid-cols-2 gap-2">
                  <button onClick={reset} className="rounded-2xl border border-slate-700 bg-slate-800 py-3 font-bold">Change</button>
                  <button onClick={doPlace} disabled={!ok || busy}
                    className={`rounded-2xl ${sell ? 'bg-red-600 hover:bg-red-500' : 'bg-green-600 hover:bg-green-500'} disabled:opacity-40 py-3 font-bold text-sm`}>
                    {busy ? 'Sending…' : goLabel}
                  </button>
                </div>
                <p className="text-[11px] text-slate-500">This preview expires in 2 minutes.</p>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
