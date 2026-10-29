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
        <div className="flex-1 flex items-center justify-center py-10">
          <LogoMark size={176} title="MarketPlayground" className="drop-shadow-[0_20px_50px_rgba(37,99,235,0.35)]" />
        </div>
        <div className="text-center">
          <h1 className="text-[34px] leading-[1.1] font-extrabold">Got a hunch?<br />Trade it.</h1>
          <p className="mt-3 text-slate-300">Practice free today.<br />Real money coming soon.</p>
        </div>
        <div className="mt-8 flex flex-col gap-3">
          <button onClick={() => go('')} className="h-14 rounded-2xl bg-blue-600 hover:bg-blue-500 font-extrabold">Create a free account</button>
          <button onClick={() => go('login')} className="h-14 rounded-2xl bg-slate-900/80 border border-slate-700 hover:border-slate-500 font-bold">I already have an account</button>
        </div>
        <p className="mt-5 text-center text-xs text-slate-400">Free beta</p>
      </div>
    </div>
  );
}
