// First screen for anyone who isn't logged in.
import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { LogoMark, Wordmark } from './ui/Logo';

export default function WelcomePage() {
  const navigate = useNavigate();
  const loc = useLocation();
  const next = new URLSearchParams(loc.search).get('next') || '/select-tool';
  const go = (mode) => navigate(`/account?${mode ? `mode=${mode}&` : ''}next=${encodeURIComponent(next)}`);
  return (
    <div className="min-h-screen mp-bg text-white flex flex-col">
      <div className="max-w-sm w-full mx-auto px-6 flex-1 flex flex-col" style={{ paddingTop: 'max(3rem, env(safe-area-inset-top))', paddingBottom: 'max(2rem, env(safe-area-inset-bottom))' }}>
        <div className="text-center text-lg"><Wordmark /></div>
        <div className="flex-1 flex flex-col items-center justify-center gap-6 py-8">
          <LogoMark size={96} title="MarketPlayground" className="drop-shadow-[0_16px_40px_rgba(37,99,235,0.35)]" />
          {/* An example, so nobody mistakes this for a yes/no betting app */}
          <div className="w-full rounded-3xl bg-slate-900/80 border border-slate-700/70 p-4 text-left" aria-label="Example">
            <div className="text-[11px] font-bold tracking-wider uppercase text-slate-400">You type</div>
            <div className="mt-1 font-semibold">“People will travel more next summer”</div>
            <div className="mt-3 text-[11px] font-bold tracking-wider uppercase text-slate-400">You get real stocks to buy</div>
            <div className="mt-2 flex flex-col gap-2">
              <div className="flex items-center justify-between rounded-2xl bg-slate-950/70 px-3 py-2.5"><span className="font-bold">Delta Air Lines <span className="text-slate-400 font-semibold">DAL</span></span><span className="text-sm text-blue-300 font-semibold">Buy shares</span></div>
              <div className="flex items-center justify-between rounded-2xl bg-slate-950/70 px-3 py-2.5"><span className="font-bold">Booking <span className="text-slate-400 font-semibold">BKNG</span></span><span className="text-sm text-blue-300 font-semibold">Buy shares</span></div>
            </div>
            <div className="mt-2 text-xs text-slate-400">Shares by default. Options if you want them.</div>
          </div>
        </div>
        <div className="text-center">
          <h1 className="text-[28px] leading-[1.15] font-extrabold">Got a hunch?<br />Turn it into a <span className="whitespace-nowrap">stock trade.</span></h1>
          <p className="mt-3 text-slate-300">Practice free today.<br />Real money coming soon.</p>
        </div>
        <div className="mt-8 flex flex-col gap-3">
          <button onClick={() => go('')} className="h-14 rounded-2xl bg-blue-600 hover:bg-blue-500 font-extrabold">Create a free account</button>
          <button onClick={() => go('login')} className="h-14 rounded-2xl bg-slate-900/80 border border-slate-700 hover:border-slate-500 font-bold">I already have an account</button>
        </div>
        <button onClick={() => navigate('/trending')} className="mt-4 w-full text-center text-sm font-semibold text-blue-300 hover:text-blue-200">See today's news first →</button>
        <p className="mt-3 text-center text-xs text-slate-400">Free beta</p>
      </div>
    </div>
  );
}
