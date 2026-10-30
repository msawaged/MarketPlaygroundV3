// Landing pages for email links: /verify?token=... (confirm email) and /reset?token=... (new password).
import React, { useEffect, useRef, useState } from 'react';
import { CheckCircle2 } from 'lucide-react';
import { useAccount } from '../lib/auth';
import { useNavigate, useLocation } from 'react-router-dom';
import Page, { Card } from './ui/Page';
import { verifyEmail, resetPassword } from '../lib/auth';

export function VerifyPage() {
  const navigate = useNavigate(); const loc = useLocation();
  const [s, setS] = useState({ busy: true });
  const account = useAccount();
  const tried = useRef(null);
  useEffect(() => {
    const t = new URLSearchParams(loc.search).get('token');
    if (!t) { setS({ error: 'This link is missing its code.' }); return; }
    if (tried.current === t) return;   // never spend the same link twice
    tried.current = t;
    verifyEmail(t).then(() => setS({ ok: true })).catch((e) => setS(e.status === 409 ? { already: true } : { error: e.message }));
  }, [loc.search]);
  return (
    <Page title="Confirm email">
      <Card className="mt-6 text-center py-8">
        {s.busy && <div className="text-slate-300">Confirming…</div>}
        {s.ok && (<>
          <CheckCircle2 className="mx-auto w-10 h-10 text-blue-400" aria-hidden />
          <div className="mt-2 text-xl font-extrabold">You're in!</div>
          <p className="mt-1 text-sm text-slate-300">Your email is confirmed and you're logged in.</p>
          <button onClick={() => navigate('/chat')} className="mt-5 rounded-2xl bg-blue-600 px-5 py-3 font-bold">Share your first belief</button>
        </>)}
        {s.already && (<>
          <CheckCircle2 className="mx-auto w-10 h-10 text-blue-400" aria-hidden />
          <div className="mt-2 text-xl font-extrabold">Your email is confirmed</div>
          <p className="mt-1 text-sm text-slate-300">{account ? "You're all set." : 'Log in with your email and password to continue.'}</p>
          <button onClick={() => navigate(account ? '/chat' : '/account?mode=login')} className="mt-5 rounded-2xl bg-blue-600 px-5 py-3 font-bold">{account ? 'Share a belief' : 'Log in'}</button>
        </>)}
        {s.error && (<>
          <div className="text-lg font-bold">That didn't work</div>
          <p className="mt-1 text-sm text-slate-300">{s.error}</p>
          <button onClick={() => navigate('/account?mode=login')} className="mt-5 rounded-2xl bg-slate-800 border border-slate-600 px-5 py-3 font-bold">Go to log in</button>
        </>)}
      </Card>
    </Page>
  );
}

export function ResetPage() {
  const navigate = useNavigate(); const loc = useLocation();
  const [pw, setPw] = useState(''); const [s, setS] = useState({});
  const token = new URLSearchParams(loc.search).get('token');
  const submit = async (e) => {
    e.preventDefault();
    if (pw.length < 8) { setS({ error: 'Use at least 8 characters.' }); return; }
    setS({ busy: true });
    try { await resetPassword(token, pw); setS({ ok: true }); } catch (e2) { setS({ error: e2.message }); }
  };
  return (
    <Page title="New password">
      <Card className="mt-6">
        {s.ok ? (
          <div className="text-center py-4">
            <div className="text-lg font-bold">Password changed. You're logged in.</div>
            <button onClick={() => navigate('/select-tool')} className="mt-4 rounded-2xl bg-blue-600 px-5 py-3 font-bold">Continue</button>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-3">
            <label className="block">
              <span className="text-xs font-semibold text-slate-300">New password</span>
              <input type="password" value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="new-password" placeholder="At least 8 characters"
                className="mt-1 w-full rounded-2xl bg-slate-950/70 border border-slate-700 focus:border-blue-400 px-3.5 py-3 text-white focus:outline-none" />
            </label>
            {s.error && <p className="text-sm text-red-300">{s.error}</p>}
            <button disabled={s.busy || !token} className="w-full rounded-2xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 py-3 font-bold">{s.busy ? 'Saving…' : 'Save new password'}</button>
          </form>
        )}
      </Card>
    </Page>
  );
}
