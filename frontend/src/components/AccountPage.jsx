// Sign up / log in, and the signed-in account screen.
import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Eye, EyeOff, Check, Mail } from 'lucide-react';
import Page, { Card } from './ui/Page';
import {
  useAccount, signup, login, logout, refreshAccount, updateName, changePassword, deleteAccount, initials,
  resendVerification, forgotPassword,
  passkeySupported, biometricName, passkeyStatus, addPasskey, loginWithPasskey, removePasskeys, passkeyCancelled,
} from '../lib/auth';
import { useBroker, refreshBroker, connectBroker, disconnectBroker, getPositions, getOrders, getExits, cancelExit, setRealMoney } from '../lib/broker';
import RealMoneySheet from './chat/RealMoneySheet';
import WhatsNew from './WhatsNew';
import AlertsCard from './AlertsCard';

function Field({ label, type = 'text', value, onChange, autoComplete, placeholder, reveal }) {
  const [show, setShow] = useState(false);
  const id = `f-${label.replace(/\s+/g, '-').toLowerCase()}`;
  return (
    <label htmlFor={id} className="block">
      <span className="text-xs font-semibold text-slate-300">{label}</span>
      <span className="mt-1 flex items-center rounded-2xl bg-slate-950/70 border border-slate-700 focus-within:border-blue-400 px-3.5">
        <input
          id={id}
          type={reveal && show ? 'text' : type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete={autoComplete}
          placeholder={placeholder}
          className="flex-1 min-w-0 bg-transparent py-3 text-base text-white placeholder-slate-500 focus:outline-none"
        />
        {reveal && (
          <button type="button" onClick={() => setShow((s) => !s)} aria-label={show ? 'Hide password' : 'Show password'} className="text-slate-400 hover:text-white p-1">
            {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        )}
      </span>
    </label>
  );
}

const PERKS = ['Your calls on every device', 'Your practice portfolio follows you', 'Free during the beta'];

function SignedOut() {
  const navigate = useNavigate();
  const loc = useLocation();
  const [mode, setMode] = useState(new URLSearchParams(loc.search).get('mode') === 'login' ? 'login' : 'signup');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [check, setCheck] = useState(null);   // email waiting for confirmation
  const [notice, setNotice] = useState(null);
  const [unverified, setUnverified] = useState(false);

  const resend = async () => {
    try { await resendVerification(check || email); setNotice('Sent. Check your inbox (and spam).'); } catch (e2) { setErr(e2.message); }
  };
  const forgot = async () => {
    if (!email) { setErr('Type your email above first.'); return; }
    try { await forgotPassword(email); setNotice(`If there's an account for ${email}, we just emailed a link to reset the password.`); }
    catch (e2) { setErr(e2.message); }
  };

  if (check) {
    return (
      <Card className="mt-6 text-center py-7">
        <Mail className="mx-auto w-10 h-10 text-blue-400" aria-hidden />
        <div className="mt-2 text-xl font-extrabold">Check your email</div>
        <p className="mt-2 text-sm text-slate-300 max-w-xs mx-auto">We sent a link to <b className="text-white">{check}</b>. Tap it to confirm your email and you're in.</p>
        <p className="mt-2 text-xs text-slate-500">Not there after a minute? Check spam or promotions.</p>
        {notice && <p className="mt-3 text-sm text-green-300">{notice}</p>}
        {err && <p className="mt-3 text-sm text-red-300">{err}</p>}
        <div className="mt-5 flex justify-center gap-3">
          <button onClick={resend} className="rounded-2xl bg-slate-800 border border-slate-600 px-4 py-2.5 text-sm font-bold">Send it again</button>
          <button onClick={() => { setCheck(null); setMode('login'); setNotice(null); }} className="rounded-2xl bg-blue-600 px-4 py-2.5 text-sm font-bold">I confirmed: log in</button>
        </div>
      </Card>
    );
  }

  const faceLogin = async () => {
    setErr(null); setNotice(null); setBusy(true);
    try {
      await loginWithPasskey();
      const next = new URLSearchParams(loc.search).get('next');
      if (next) navigate(next);
    } catch (e2) {
      if (!passkeyCancelled(e2)) setErr(e2.message);
    } finally {
      setBusy(false);
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    setErr(null); setNotice(null); setUnverified(false);
    if (mode === 'signup' && password.length < 8) { setErr('Use at least 8 characters for your password.'); return; }
    setBusy(true);
    try {
      if (mode === 'signup') {
        const r = await signup({ email, password, name });
        if (r?.needs_verification) { setCheck(r.email); if (!r.sent) setErr("We couldn't send the email just now. Tap 'Send it again'."); return; }
      } else await login({ email, password });
      const next = new URLSearchParams(loc.search).get('next');
      if (next) navigate(next);
    } catch (e2) {
      setErr(e2.message);
      if (e2.status === 403) setUnverified(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Card className="mt-6 bg-gradient-to-br from-blue-600/25 to-slate-900/70 border-blue-400/30">
        <ul className="space-y-2">
          {PERKS.map((p) => (
            <li key={p} className="flex items-center gap-2.5 text-sm">
              <span className="w-5 h-5 rounded-full bg-green-500/20 text-green-300 flex items-center justify-center"><Check className="w-3 h-3" /></span>{p}
            </li>
          ))}
        </ul>
      </Card>

      <div className="mt-5 grid grid-cols-2 rounded-2xl bg-slate-900/80 border border-slate-700 p-1" role="tablist">
        {[['signup', 'Create account'], ['login', 'Log in']].map(([id, label]) => (
          <button key={id} role="tab" aria-selected={mode === id} onClick={() => { setMode(id); setErr(null); }}
            className={`rounded-xl py-2.5 text-sm font-bold transition ${mode === id ? 'bg-blue-600 text-white' : 'text-slate-300'}`}>
            {label}
          </button>
        ))}
      </div>

      <form onSubmit={submit} className="mt-4 space-y-3">
        <AnimatePresence initial={false}>
          {mode === 'signup' && (
            <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
              <Field label="First name (optional)" value={name} onChange={setName} autoComplete="given-name" placeholder="Alex" />
            </motion.div>
          )}
        </AnimatePresence>
        <Field label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" placeholder="you@example.com" />
        <Field label="Password" type="password" value={password} onChange={setPassword} reveal
          autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} placeholder={mode === 'signup' ? 'At least 8 characters' : ''} />
        {err && <div className="rounded-2xl bg-red-950/50 border border-red-500/40 px-3.5 py-2.5 text-sm text-red-200" role="alert">{err}
          {unverified && <button type="button" onClick={resend} className="block mt-1.5 underline font-semibold text-white">Send the confirmation email again</button>}
        </div>}
        {notice && <div className="rounded-2xl bg-green-950/40 border border-green-500/30 px-3.5 py-2.5 text-sm text-green-200" role="status">{notice}</div>}
        <button type="submit" disabled={busy || !email || !password}
          className="w-full rounded-2xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 py-3.5 font-bold">
          {busy ? 'One moment…' : mode === 'signup' ? 'Create my free account' : 'Log in'}
        </button>
        {mode === 'login' && passkeySupported() && (
          <button type="button" disabled={busy} onClick={faceLogin}
            className="w-full rounded-2xl border border-slate-600 bg-slate-900/80 hover:border-blue-400 py-3.5 font-bold">
            Log in with {biometricName()}
          </button>
        )}
        {mode === 'login' && (
          <p className="text-xs text-slate-400 text-center"><button type="button" onClick={forgot} className="underline text-blue-300 font-semibold">Forgot your password?</button> We'll email you a link.</p>
        )}
        {mode === 'login' && <WhatsNew max={3} className="mt-2" />}
        {mode === 'signup' && (
          <p className="text-[11px] text-slate-500 text-center leading-relaxed">
            Anything you've already done on this device moves into your account. We never sell your data. MarketPlayground is for education, not investment advice.
          </p>
        )}
      </form>
    </>
  );
}

export function FaceIdCard({ compact = false, onDone }) {
  const [on, setOn] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const name = biometricName();
  useEffect(() => { if (passkeySupported()) passkeyStatus().then((r) => setOn(r.passkeys > 0)).catch(() => setOn(false)); }, []);
  if (!passkeySupported() || on === null || (compact && on)) return null;
  const turnOn = async () => {
    setBusy(true); setErr(null);
    try { await addPasskey(); setOn(true); onDone?.(); } catch (e) { if (!passkeyCancelled(e)) setErr(e.message); } finally { setBusy(false); }
  };
  const turnOff = async () => { setBusy(true); try { await removePasskeys(); setOn(false); } finally { setBusy(false); } };
  return (
    <Card className="mt-3">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-bold">Log in with {name}</div>
          <div className="text-xs text-slate-400">{on ? 'On for this account. No password needed on this device.' : 'Skip the password next time.'}</div>
        </div>
        {on
          ? <button onClick={turnOff} disabled={busy} className="shrink-0 rounded-2xl border border-slate-700 px-4 py-2 text-sm font-bold hover:border-slate-500">Turn off</button>
          : <button onClick={turnOn} disabled={busy} className="shrink-0 rounded-2xl bg-blue-600 hover:bg-blue-500 px-4 py-2 text-sm font-bold">{busy ? 'One moment…' : 'Turn on'}</button>}
      </div>
      {err && <p className="mt-2 text-xs text-red-300">{err}</p>}
    </Card>
  );
}

function RealHoldings({ broker }) {
  const [pos, setPos] = useState(null);
  const [ords, setOrds] = useState(null);
  const [selling, setSelling] = useState(null);
  const [err, setErr] = useState(null);
  const [exits, setExits] = useState([]);
  const load = () => {
    getPositions().then(setPos).catch((e) => setErr(e.message));
    getOrders().then(setOrds).catch(() => setOrds([]));
    getExits().then(setExits).catch(() => setExits([]));
  };
  const live = (sym) => exits.filter((x) => x.symbol === sym && ['at_alpaca', 'waiting_fill', 'armed', 'tp_sent'].includes(x.status));
  const money = (v) => (v == null ? '—' : `$${Number(v).toFixed(2)}`);
  useEffect(load, []);
  const pct = (v) => `${v >= 0 ? '+' : ''}${(v * 100).toFixed(1)}%`;
  return (
    <div className="mt-4">
      <div className="text-xs font-bold uppercase tracking-wider text-slate-400">What you hold</div>
      {err && <p className="mt-1 text-sm text-red-300">{err}</p>}
      {pos === null ? <p className="mt-1 text-sm text-slate-500">Loading…</p> : pos.length === 0 ? (
        <p className="mt-1 text-sm text-slate-400">Nothing yet.</p>
      ) : (
        <ul className="mt-1.5 space-y-1.5">
          {pos.map((p) => (
            <li key={p.symbol} className="flex items-center justify-between gap-2 rounded-2xl bg-slate-950/50 border border-slate-800 px-3 py-2.5">
              <div className="min-w-0">
                <div className="text-sm font-semibold break-words">{p.label}</div>
                <div className="text-xs text-slate-400">
                  ${p.market_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ·{' '}
                  <span className={p.unrealized_plpc >= 0 ? 'text-green-300' : 'text-red-300'}>{pct(p.unrealized_plpc)}</span> since you bought
                </div>
                {live(p.symbol).map((x) => (
                  <div key={x.id} className="mt-1 text-[11px] text-slate-400">
                    {x.tp_price != null && <span className="text-green-300">Take profit {money(x.tp_price)}</span>}
                    {x.tp_price != null && x.sl_price != null && ' · '}
                    {x.sl_price != null && <span className="text-red-300">Max loss {money(x.sl_price)}</span>}
                    {x.status === 'waiting_fill' && ' · set when the buy fills'}
                    {x.held_at === 'alpaca' ? ' · held at Alpaca' : ' · stop at Alpaca, take-profit watched'}
                    {x.kind === 'option' && <button onClick={() => cancelExit(x.id).then(load).catch((e) => setErr(e.message))} className="ml-1 underline">turn off</button>}
                    {x.note && <div className="text-amber-200/80">{x.note}</div>}
                  </div>
                ))}
              </div>
              <button onClick={() => setSelling(p)} className="shrink-0 rounded-xl border border-slate-600 px-3 py-1.5 text-xs font-bold hover:border-red-300">Sell</button>
            </li>
          ))}
        </ul>
      )}
      {ords && ords.length > 0 && (
        <>
          <div className="mt-4 text-xs font-bold uppercase tracking-wider text-slate-400">Recent orders</div>
          <ul className="mt-1.5 space-y-1 text-sm">
            {ords.slice(0, 8).map((o) => (
              <li key={o.id} className="flex justify-between gap-2">
                <span className="min-w-0 break-words"><span className={o.side === 'sell' ? 'text-red-300' : 'text-green-300'}>{o.side === 'sell' ? 'Sold' : 'Bought'}</span> {o.label}</span>
                <span className="shrink-0 text-slate-400">{o.filled_avg_price ? `$${o.filled_avg_price.toFixed(2)}` : (o.status || 'sent').replace(/_/g, ' ')}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      <a href="/journey" className="mt-3 inline-block text-sm text-blue-300 underline">Your public real-money journey →</a>
      {selling && (
        <RealMoneySheet open={!!selling} onClose={() => setSelling(null)} broker={broker} position={selling} onDone={load} />
      )}
    </div>
  );
}

function Toggle({ on, disabled, onChange, label }) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={label} disabled={disabled} onClick={() => onChange(!on)}
      className={`relative shrink-0 w-14 h-8 rounded-full transition-colors ${on ? 'bg-green-500' : 'bg-slate-600'} ${disabled ? 'opacity-40 cursor-not-allowed' : ''}`}>
      <span className={`absolute top-1 left-1 w-6 h-6 rounded-full bg-white shadow transition-transform ${on ? 'translate-x-6' : ''}`} />
    </button>
  );
}

const SETUP_ITEMS = [
  ['real_money_setting', 'MP_REAL_MONEY', 'on', 'turns the feature on'],
  ['keys', 'MP_BROKER_KEY_ID + MP_BROKER_SECRET_KEY', 'your live Alpaca API keys', 'connects your own account'],
  ['live', 'MP_BROKER_ENV', 'live', 'real money instead of Alpaca\'s practice side'],
  ['pilot_list', 'MP_REAL_MONEY_PILOT', 'your login email', 'only your account can use it'],
];

function Steps({ items }) {
  return (
    <ol className="mt-2 space-y-2">
      {items.map(([done, text], i) => (
        <li key={i} className="flex gap-2.5 text-sm">
          <span className={`shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${done ? 'bg-green-500 text-slate-950' : 'bg-slate-700 text-slate-200'}`}>{done ? '✓' : i + 1}</span>
          <span className="text-slate-300 leading-snug pt-0.5">{text}</span>
        </li>
      ))}
    </ol>
  );
}

function Brokerage() {
  const b = useBroker();
  const loc = useLocation();
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const [cap, setCap] = useState('');
  const flag = new URLSearchParams(loc.search).get('broker');
  useEffect(() => { refreshBroker(); }, []);
  useEffect(() => { if (b?.max_order_usd) setCap(String(b.max_order_usd)); }, [b?.max_order_usd]);
  if (!b) return null;

  const flip = async (on) => {
    setBusy(true); setErr(null);
    try { await setRealMoney(on); } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  const saveCap = async () => {
    setErr(null);
    try { await setRealMoney(b.on, Number(cap)); } catch (e) { setErr(e.message); }
  };
  const live = b.env === 'live';
  let status;
  if (!b.pilot && !b.owner) status = 'Coming soon. Practice money stays free; when real money opens, you\'ll connect your own brokerage here.';
  else if (!b.pilot) status = 'Not set up on the server yet. Steps below (only you can see this).';
  else if (!b.connected) status = 'Connect your brokerage to use this switch.';
  else if (b.on) status = live ? 'ON: idea cards show real-money buttons. You approve every order.' : 'ON (Alpaca practice side): idea cards show buttons that trade your Alpaca practice account.';
  else status = 'OFF: practice mode only. You can still sell what you hold, and take-profit / max-loss exits keep working.';

  return (
    <>
    {b.owner && (
      <a href="/hq" className="mt-3 flex items-center justify-between rounded-2xl border border-blue-400/40 bg-blue-500/[0.07] px-4 py-3">
        <span><span className="block text-sm font-bold">Agent HQ</span><span className="block text-xs text-slate-400">All your agents at one table. Talk to them, see what they need.</span></span>
        <span className="text-blue-300" aria-hidden>→</span>
      </a>
    )}
    <Card className={`mt-3 ${b.on ? 'border-green-400/50 bg-green-500/5' : 'border-amber-300/30 bg-amber-400/5'}`}>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <div className="text-base font-bold">Real money</div>
            {b.pilot && <span className="text-[10px] font-bold uppercase rounded-full px-2 py-0.5 bg-amber-400/15 text-amber-200">{live ? 'Live' : 'Practice side'}</span>}
          </div>
          <p className="mt-0.5 text-sm text-slate-300 leading-snug">{status}</p>
        </div>
        <Toggle on={!!b.on} disabled={!b.can_switch || busy} onChange={flip} label="Real money" />
      </div>
      {flag === 'connected' && <p className="mt-2 text-sm text-green-300">✓ Connected.</p>}
      {flag === 'failed' && <p className="mt-2 text-sm text-red-300">That didn't work. Please try again.</p>}
      {err && <p className="mt-2 text-sm text-red-300">{err}</p>}

      {b.owner && b.setup && !b.pilot && (
        <div className="mt-3 rounded-2xl border border-slate-700 bg-slate-950/40 p-3">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-400">Owner setup · Render → marketplayground-backend → Environment</div>
          <Steps items={SETUP_ITEMS.map(([k, name, val, why]) => [b.setup[k], <><b className="text-white">{name}</b> = {val} <span className="text-slate-500">({why})</span></>])} />
          <p className="mt-2 text-[11px] text-slate-500">Save, wait a minute or two for the restart, then come back: this switch unlocks for your account only. Keys are never shown here.</p>
        </div>
      )}

      {b.pilot && !b.connected && (
        <div className="mt-3">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-400">Set up in 4 steps</div>
          <Steps items={[
            [false, <>Open an Alpaca brokerage account (free) and add money. <a href={b.signup_url} target="_blank" rel="noopener noreferrer" className="text-blue-300 underline">Open Alpaca ↗</a> Want options? Ask Alpaca for options approval in their app.</>],
            [false, 'Tap Connect Alpaca below and approve. You sign in on Alpaca\'s own page; we never see your password.'],
            [false, 'Pick your per-order limit (the most any single order can be).'],
            [false, 'Flip the Real money switch on. You still confirm every order, and you can switch off any time.'],
          ]} />
          {b.mode !== 'keys' && (
            <button onClick={() => connectBroker().catch((e) => setErr(e.message))} className="mt-3 w-full rounded-2xl bg-amber-400 hover:bg-amber-300 text-slate-950 py-3 font-bold">Connect Alpaca</button>
          )}
        </div>
      )}

      {b.connected && (
        <>
          <p className="mt-3 text-sm text-slate-300">
            {b.mode === 'keys' ? 'Your own Alpaca account is connected' : 'Alpaca account connected'}
            {b.account ? ` · buying power $${b.account.buying_power.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : ''}.
          </p>
          {b.account_error && <p className="mt-1 text-sm text-red-300">{b.account_error}</p>}
          <div className="mt-3 flex items-end gap-2">
            <label className="block flex-1">
              <span className="text-xs font-semibold text-slate-300">Per-order limit (up to ${Number(b.server_max_order_usd || b.max_order_usd).toLocaleString()})</span>
              <input type="number" inputMode="decimal" min="1" max={b.server_max_order_usd} value={cap} onChange={(e) => setCap(e.target.value)}
                className="mt-1 w-full rounded-2xl bg-slate-950/70 border border-slate-700 focus:border-blue-400 px-3.5 py-2.5 text-white focus:outline-none" />
            </label>
            <button onClick={saveCap} disabled={!(Number(cap) >= 1) || Number(cap) === b.max_order_usd} className="rounded-2xl border border-slate-600 px-4 py-2.5 font-bold disabled:opacity-40">Save</button>
          </div>
          {b.funding_url && (
            <a href={b.funding_url} target="_blank" rel="noopener noreferrer"
              className="mt-3 block w-full text-center rounded-2xl border border-amber-300/50 bg-amber-400/10 text-amber-100 py-3 font-bold">
              Deposit or withdraw in Alpaca ↗
            </a>
          )}
          <p className="mt-1.5 text-[11px] text-slate-500">Money moves in Alpaca's own app; MarketPlayground never touches it. Come back here and your balance updates.</p>
          <RealHoldings broker={b} />
          {b.mode !== 'keys' && <button onClick={() => disconnectBroker().catch((e) => setErr(e.message))} className="mt-3 text-xs text-slate-400 underline">Disconnect</button>}
        </>
      )}
    </Card>
    </>
  );
}

function SignedIn({ acc }) {
  const navigate = useNavigate();
  const [name, setName] = useState(acc.name || '');
  const [saved, setSaved] = useState(false);
  const [open, setOpen] = useState(null); // 'password' | 'delete'
  const [cur, setCur] = useState(''); const [nw, setNw] = useState('');
  const [msg, setMsg] = useState(null);

  const saveName = async () => { try { await updateName(name); setSaved(true); setTimeout(() => setSaved(false), 2000); } catch (e) { setMsg({ bad: true, text: e.message }); } };
  const doPassword = async (e) => {
    e.preventDefault(); setMsg(null);
    try { await changePassword(cur, nw); setMsg({ text: 'Password changed. Other devices were signed out.' }); setCur(''); setNw(''); setOpen(null); }
    catch (e2) { setMsg({ bad: true, text: e2.message }); }
  };
  const doDelete = async (e) => {
    e.preventDefault(); setMsg(null);
    try { await deleteAccount(cur); navigate('/select-tool'); } catch (e2) { setMsg({ bad: true, text: e2.message }); }
  };
  const since = new Date(acc.created_at).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });

  return (
    <>
      <Card className="mt-6 flex items-center gap-4">
        <div className="w-16 h-16 rounded-3xl bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center text-2xl font-extrabold shadow-lg shadow-blue-700/30">{initials(acc)}</div>
        <div className="min-w-0">
          <div className="text-lg font-bold truncate">{acc.name || 'Welcome!'}</div>
          <div className="text-sm text-slate-400 truncate">{acc.email}</div>
          <div className="text-xs text-slate-500">Member since {since}</div>
        </div>
      </Card>

      <div className="mt-3 grid grid-cols-2 gap-2.5">
        <button onClick={() => navigate('/my')} className="rounded-3xl border border-slate-700/70 bg-slate-900/70 p-4 text-left hover:border-blue-400/60">
          <div className="font-bold">My beliefs</div><div className="text-xs text-slate-400">On every device now</div>
        </button>
        <button onClick={() => navigate('/portfolio')} className="rounded-3xl border border-slate-700/70 bg-slate-900/70 p-4 text-left hover:border-blue-400/60">
          <div className="font-bold">Portfolio</div><div className="text-xs text-slate-400">Your practice trades</div>
        </button>
      </div>

      <Card className="mt-3">
        <div className="text-sm font-bold">Your name</div>
        <div className="mt-2 flex gap-2">
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={60} placeholder="First name"
            className="flex-1 min-w-0 rounded-2xl bg-slate-950/70 border border-slate-700 focus:border-blue-400 px-3.5 py-2.5 text-white focus:outline-none" />
          <button onClick={saveName} className="rounded-2xl bg-slate-800 border border-slate-700 px-4 text-sm font-bold hover:border-blue-400">{saved ? '✓ Saved' : 'Save'}</button>
        </div>
      </Card>

      <FaceIdCard />
      <div className="mt-3"><AlertsCard /></div>

      <Brokerage />

      {msg && <div className={`mt-3 rounded-2xl px-3.5 py-2.5 text-sm ${msg.bad ? 'bg-red-950/50 border border-red-500/40 text-red-200' : 'bg-green-950/40 border border-green-500/30 text-green-200'}`} role="status">{msg.text}</div>}

      <Card className="mt-3">
        <button onClick={() => { setOpen(open === 'password' ? null : 'password'); setCur(''); setNw(''); setMsg(null); }} className="w-full text-left text-sm font-bold">
          Change password <span className="float-right text-slate-500">{open === 'password' ? '−' : '+'}</span>
        </button>
        {open === 'password' && (
          <form onSubmit={doPassword} className="mt-3 space-y-3">
            <Field label="Current password" type="password" value={cur} onChange={setCur} autoComplete="current-password" reveal />
            <Field label="New password" type="password" value={nw} onChange={setNw} autoComplete="new-password" reveal placeholder="At least 8 characters" />
            <button className="w-full rounded-2xl bg-blue-600 hover:bg-blue-500 py-3 font-bold">Change password</button>
          </form>
        )}
      </Card>

      <button onClick={async () => { await logout(); navigate('/select-tool'); }} className="mt-3 w-full rounded-3xl border border-slate-700 bg-slate-900/70 py-3.5 font-bold hover:border-slate-500">
        Log out
      </button>

      <div className="mt-6">
        <button onClick={() => { setOpen(open === 'delete' ? null : 'delete'); setCur(''); setMsg(null); }} className="text-xs text-slate-500 underline hover:text-red-300">Delete my account</button>
        {open === 'delete' && (
          <form onSubmit={doDelete} className="mt-3 rounded-3xl border border-red-500/40 bg-red-950/30 p-4 space-y-3">
            <p className="text-sm text-red-100">This deletes your account and email. Your past beliefs stay in the shared learning without your name on them. This can't be undone.</p>
            <Field label="Type your password to confirm" type="password" value={cur} onChange={setCur} autoComplete="current-password" reveal />
            <button className="w-full rounded-2xl bg-red-600 hover:bg-red-500 py-3 font-bold">Delete my account</button>
          </form>
        )}
      </div>
    </>
  );
}

export default function AccountPage() {
  const acc = useAccount();
  useEffect(() => { refreshAccount(); }, []);
  return (
    <Page title={acc ? 'Your account' : 'Save your calls'} subtitle={acc ? null : 'A free account keeps everything in sync.'}>
      {acc ? <SignedIn acc={acc} /> : <SignedOut />}
    </Page>
  );
}
