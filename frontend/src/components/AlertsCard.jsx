// "Market's open" alerts: one tap to turn on. On iPhone, explains the Add to Home Screen step first.
import React, { useEffect, useState } from 'react';
import { Bell, BellOff } from 'lucide-react';
import { currentSubscription, disableAlerts, enableAlerts, needsHomeScreen, pushSupported, testAlert } from '../lib/push';

export default function AlertsCard({ compact = false, onDone }) {
  const [on, setOn] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  useEffect(() => { currentSubscription().then((s) => setOn(!!s)).catch(() => setOn(false)); }, []);
  if (!pushSupported() && !needsHomeScreen()) return null;
  const go = async (fn, ok) => {
    setBusy(true); setMsg('');
    let good = false;
    try { await fn(); ok && setMsg(ok); good = true; } catch (e) { setMsg(e?.message || 'Something went wrong.'); }
    setBusy(false); setOn(!!(await currentSubscription().catch(() => null)));
    return good;
  };
  return (
    <div className="rounded-2xl border border-blue-500/30 bg-blue-500/[0.07] p-4">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 rounded-xl bg-blue-600/20 p-2 text-blue-300">{on ? <Bell className="h-5 w-5" /> : <BellOff className="h-5 w-5" />}</div>
        <div className="min-w-0 flex-1">
          <div className="font-bold">Market's open alerts</div>
          <p className="mt-0.5 text-sm text-slate-300">
            {on ? 'On. Around 9:35 am Eastern on trading days you get the top story and the stocks it moves, plus "You called it" alerts and big new features.'
              : 'The top story and the stocks it moves, around 9:35 am Eastern on trading days. Plus a heads-up when one of your calls is playing out.'}
          </p>
          {needsHomeScreen() && !on && (
            <p className="mt-2 text-xs text-amber-200">On iPhone: tap the Share button, then <b>Add to Home Screen</b>. Open MarketPlayground from your home screen and turn alerts on there.</p>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            {!on && !needsHomeScreen() && (
              <button disabled={busy} onClick={async () => { if (await go(enableAlerts, "You're set. A test alert is on its way.")) { testAlert().catch(() => {}); setTimeout(() => onDone && onDone(), 2500); } }}
                className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-bold hover:bg-blue-500 disabled:opacity-60">{busy ? 'One moment…' : 'Turn on alerts'}</button>
            )}
            {on && !compact && (
              <>
                <button disabled={busy} onClick={() => go(testAlert, 'Test sent.')} className="rounded-xl border border-slate-600 px-3 py-2 text-sm font-semibold hover:bg-slate-800">Send a test</button>
                <button disabled={busy} onClick={() => go(disableAlerts, 'Alerts are off.')} className="rounded-xl px-3 py-2 text-sm text-slate-400 hover:text-slate-200">Turn off</button>
              </>
            )}
          </div>
          {msg && <p className="mt-2 text-xs text-slate-300">{msg}</p>}
        </div>
      </div>
    </div>
  );
}
