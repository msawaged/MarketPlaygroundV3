// "Put it on your home screen": one card. One tap on Android / Chrome / Edge; Safari's two steps on iPhone.
// Hidden once installed. `ask` = the Home-page version (has "Not now", remembered 30 days, counted as shown).
import React, { useEffect, useState } from 'react';
import { Share, SquarePlus, Smartphone } from 'lucide-react';
import { installOffer, isIOSSafari, onInstallChange, promptInstall, snooze, snoozed, track } from '../lib/install';

export function useInstallOffer({ respectSnooze = false } = {}) {
  const [, setTick] = useState(0);
  useEffect(() => onInstallChange(() => setTick((t) => t + 1)), []);
  const offer = installOffer();
  return respectSnooze && snoozed() ? null : offer;
}

export default function InstallCard({ ask = false, onDone }) {
  const offer = useInstallOffer({ respectSnooze: ask });
  const [msg, setMsg] = useState('');
  useEffect(() => { if (offer && ask) track('shown'); }, [offer, ask]);
  if (!offer && !msg) return null;
  const notNow = () => { snooze(); onDone && onDone(); };
  const safari = isIOSSafari();
  return (
    <div className="rounded-2xl border border-blue-500/30 bg-blue-500/[0.07] p-4">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 rounded-xl bg-blue-600/20 p-2 text-blue-300"><Smartphone className="h-5 w-5" aria-hidden /></div>
        <div className="min-w-0 flex-1">
          <div className="font-bold">Put it on your home screen</div>
          <p className="mt-0.5 text-sm text-slate-300">
            MarketPlayground opens full screen like an app, one tap from your home screen.
            {offer === 'ios' ? ' On iPhone, that’s also where Market’s open alerts work.' : ' Free, nothing to download from a store.'}
          </p>
          {offer === 'prompt' && (
            <button onClick={async () => { const r = await promptInstall(); if (r === 'accepted') { setMsg('Added. Look for MarketPlayground on your home screen.'); setTimeout(() => onDone && onDone(), 2500); } }}
              className="mt-3 rounded-xl bg-blue-600 px-4 py-2 text-sm font-bold hover:bg-blue-500">Add to home screen</button>
          )}
          {offer === 'ios' && (
            <ol className="mt-3 space-y-1.5 text-sm text-slate-200">
              <li className="flex items-center gap-2">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-800 text-[11px] font-bold">1</span>
                <span>Tap <Share className="inline h-4 w-4 -mt-0.5 text-blue-300" aria-label="Share" /> <b>Share</b> <span className="text-slate-400">(on newer iPhones it’s under <b>•••</b>)</span></span>
              </li>
              <li className="flex items-center gap-2">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-800 text-[11px] font-bold">2</span>
                <span>Scroll down, tap <SquarePlus className="inline h-4 w-4 -mt-0.5 text-blue-300" aria-hidden /> <b>Add to Home Screen</b></span>
              </li>
              {!safari && <li className="text-xs text-slate-400">Don’t see it? Open this page in Safari and try there.</li>}
            </ol>
          )}
          {msg && <p className="mt-2 text-xs text-slate-300">{msg}</p>}
        </div>
      </div>
      {ask && !msg && <button onClick={notNow} className="mt-2 w-full text-center text-xs text-slate-500 hover:text-slate-300">Not now</button>}
    </div>
  );
}
