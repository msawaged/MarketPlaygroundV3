// Agent HQ (owner only): every agent at one table, and one meeting thread with Murad.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import Page, { Card } from './ui/Page';
import { hqBoard, hqPost } from '../lib/api';

const COLORS = { cto: 'bg-blue-500', chair: 'bg-white', health: 'bg-emerald-500', reel: 'bg-pink-500', scout: 'bg-amber-500', brain: 'bg-violet-500', polish: 'bg-cyan-500', growth: 'bg-lime-500' };
const ago = (iso) => {
  if (!iso) return 'not yet';
  const m = Math.round((Date.now() - new Date(iso)) / 60000);
  if (m < 60) return `${Math.max(1, m)} min ago`;
  const h = Math.round(m / 60);
  return h < 36 ? `${h} h ago` : `${Math.round(h / 24)} days ago`;
};
const when = (iso) => (iso ? new Date(iso).toLocaleString('en-US', { weekday: 'short', hour: 'numeric', minute: '2-digit' }) : '');
const initials = (n) => n.replace(/[^A-Za-z ]/g, '').split(' ').filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase();

function Avatar({ k, name, size = 'w-10 h-10' }) {
  return <div className={`${size} shrink-0 rounded-full ${COLORS[k] || 'bg-slate-500'} flex items-center justify-center text-xs font-black text-slate-950`}>{initials(name)}</div>;
}

export default function HQPage() {
  const [b, setB] = useState(null);
  const [err, setErr] = useState('');
  const [to, setTo] = useState('all');
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [open, setOpen] = useState(null);
  const end = useRef(null);

  const load = useCallback(() => {
    hqBoard().then((r) => { setB(r); setErr(''); }).catch((e) => setErr(e.message || 'Could not load.'));
  }, []);
  useEffect(() => { load(); const id = setInterval(load, 60000); return () => clearInterval(id); }, [load]);
  useEffect(() => { end.current?.scrollIntoView({ block: 'end' }); }, [b?.thread?.length]);

  const send = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    setSending(true);
    try { await hqPost(text.trim(), to); setText(''); load(); } catch (x) { setErr(x.message); }
    finally { setSending(false); }
  };

  if (err && !b) return <Page title="Agent HQ"><Card className="mt-6 text-sm text-amber-200">{/sign in/i.test(err) ? <>Sign in with your owner account, then come back. <a className="text-blue-300 underline" href="/account">Sign in</a></> : /owner/i.test(err) ? 'This account isn\'t the owner account. Sign out and sign in with your main email.' : err}</Card></Page>;
  if (!b) return <Page title="Agent HQ"><div className="mt-6 h-64 rounded-3xl bg-slate-800/50 animate-pulse" /></Page>;

  const name = (k) => (k === 'all' ? 'Everyone' : b.agents.find((a) => a.key === k)?.name || k);

  return (
    <Page title="Agent HQ" subtitle="Everyone at one table. Talk to all of them or one. They read it when they start and answer when they finish.">
      {b.needs.length > 0 && (
        <Card className="mt-6 border-amber-400/50 bg-amber-500/[0.07]">
          <div className="text-xs uppercase tracking-wider text-amber-300 font-bold">Needs you ({b.needs.length})</div>
          <ul className="mt-2 space-y-2 text-sm">
            {b.needs.map((n, i) => (
              <li key={i} className="flex gap-2"><Avatar k={n.agent} name={n.name} size="w-6 h-6" /><span><b>{n.name}:</b> {n.need}</span></li>
            ))}
          </ul>
        </Card>
      )}

      <div className="mt-6 text-xs uppercase tracking-wider text-slate-400 font-semibold">The table</div>
      <div className="mt-2 grid grid-cols-1 gap-3">
        {b.agents.map((a) => {
          const s = a.status || {};
          const isOpen = open === a.key;
          return (
            <button key={a.key} onClick={() => setOpen(isOpen ? null : a.key)} className="text-left rounded-2xl border border-slate-700 bg-slate-900/60 p-3 hover:border-blue-400/60">
              <div className="flex items-center gap-3">
                <Avatar k={a.key} name={a.name} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-bold truncate">{a.name}</span>
                    <span className="shrink-0 text-[11px] text-slate-400">{ago(s.updated_at)}</span>
                  </div>
                  <div className="text-xs text-slate-400 truncate">{s.working_on || a.role}</div>
                </div>
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
                <span className="px-2 py-0.5 rounded-full bg-slate-800 text-slate-300">{a.schedule}</span>
                {a.unread > 0 && <span className="px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-200">{a.unread} unread from you</span>}
                {(s.needs_from_murad || []).length > 0 && <span className="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-200">needs you</span>}
              </div>
              {isOpen && (
                <div className="mt-3 space-y-1.5 text-sm text-slate-300 border-t border-slate-800 pt-3">
                  <div><span className="text-slate-500">Job: </span>{a.role}</div>
                  <div><span className="text-slate-500">Last run: </span>{s.last_run || 'Hasn\'t checked in yet.'}</div>
                  {s.next && <div><span className="text-slate-500">Next: </span>{s.next}</div>}
                  <div className="pt-1"><span onClick={(e) => { e.stopPropagation(); setTo(a.key); document.getElementById('hq-input')?.focus(); }} className="text-blue-300 font-semibold">Message {a.name} →</span></div>
                </div>
              )}
            </button>
          );
        })}
      </div>

      <div className="mt-8 text-xs uppercase tracking-wider text-slate-400 font-semibold">Meeting</div>
      <Card className="mt-2 !p-3">
        <div className="max-h-[55vh] overflow-y-auto space-y-3 pr-1">
          {b.thread.length === 0 && <p className="text-sm text-slate-400">No messages yet. Say something to everyone below.</p>}
          {b.thread.map((t, i) => (t.kind === 'murad' ? (
            <div key={i} className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-br-md bg-blue-600 px-3 py-2 text-sm">
                <div className="text-[10px] text-blue-100/80 mb-0.5">You → {name(t.to)} · {when(t.at)}</div>
                <div className="whitespace-pre-wrap">{t.body}</div>
              </div>
            </div>
          ) : (
            <div key={i} className="flex gap-2">
              <Avatar k={t.agent} name={t.name} size="w-7 h-7" />
              <div className={`max-w-[85%] rounded-2xl rounded-bl-md px-3 py-2 text-sm ${t.kind === 'status' ? 'bg-slate-800/60 text-slate-300' : 'bg-slate-800'}`}>
                <div className="text-[10px] text-slate-400 mb-0.5">{t.name} · {t.kind === 'status' ? 'finished a run' : `re #${t.re}`} · {when(t.at)}</div>
                <div className="whitespace-pre-wrap">{t.body}</div>
              </div>
            </div>
          )))}
          <div ref={end} />
        </div>
        <form onSubmit={send} className="mt-3 border-t border-slate-800 pt-3">
          <div className="flex gap-1.5 overflow-x-auto pb-2">
            {[{ key: 'all', name: 'Everyone' }, ...b.agents].map((a) => (
              <button type="button" key={a.key} onClick={() => setTo(a.key)} className={`shrink-0 text-xs px-3 py-1.5 rounded-full border ${to === a.key ? 'border-blue-400 bg-blue-500/20 text-white' : 'border-slate-700 text-slate-300'}`}>{a.name}</button>
            ))}
          </div>
          <div className="flex gap-2">
            <textarea id="hq-input" rows={2} value={text} onChange={(e) => setText(e.target.value)} placeholder={`Message ${name(to)}…`}
              className="flex-1 min-w-0 resize-none rounded-2xl bg-slate-800/80 border border-slate-700 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-blue-400 outline-none" />
            <button disabled={sending || !text.trim()} className="rounded-2xl bg-blue-600 px-4 font-bold disabled:opacity-40">Send</button>
          </div>
          <p className="mt-2 text-[11px] text-slate-500">Agents pick this up on their next run. For something urgent, tell the CTO in the build chat.</p>
        </form>
      </Card>
    </Page>
  );
}
