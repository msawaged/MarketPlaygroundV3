// "Watch the brain learn": a public, live view of the real learning system. Every number comes from /v4/brain.
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { request, API_BASE } from '../lib/api';
import { useAccount } from '../lib/auth';
import { themeLabel } from '../lib/text';
import BottomNavigation from './BottomNavigation';

const STATUS = {
  active: { label: 'Trusted', color: '#4ade80', note: 'Beat the baseline on beliefs it had never seen, so it gets a vote.' },
  shadow: { label: 'On probation', color: '#fbbf24', note: 'Promising, but not clear of luck yet. Watching, no vote.' },
  rejected: { label: 'Rejected', color: '#f87171', note: 'Did not beat the baseline. Thrown out.' },
  retired: { label: 'Replaced', color: '#64748b', note: 'Was trusted until a better version passed the test.' },
};

function ago(iso, now) {
  const t = Date.parse(iso || ''); if (!t) return '';
  const s = Math.max(0, Math.round((now - t) / 1000));
  if (s < 60) return `${s}s ago`; const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`; const h = Math.round(m / 60);
  return h < 48 ? `${h}h ago` : `${Math.round(h / 24)}d ago`;
}

function CountUp({ value, dur = 1.4 }) {
  const [v, setV] = useState(0);
  const from = useRef(0);
  useEffect(() => {
    const start = performance.now(), a = from.current, b = Number(value) || 0;
    let raf;
    const step = (t) => {
      const k = Math.min(1, (t - start) / (dur * 1000)), e = 1 - Math.pow(1 - k, 3);
      setV(Math.round(a + (b - a) * e));
      if (k < 1) raf = requestAnimationFrame(step); else from.current = b;
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value, dur]);
  return <>{v.toLocaleString()}</>;
}

// The network: inputs are the themes it has learned most about; signals keep firing through it.
function Network({ themes, firing }) {
  const W = 360, H = 300;
  const layers = useMemo(() => {
    const ins = (themes.length ? themes.slice(0, 6) : [{ theme: '…' }]).map((t) => themeLabel(t.theme));
    return [ins, Array(7).fill(''), Array(7).fill(''), Array(5).fill(''), ['Playing out', 'Not yet']];
  }, [themes]);
  const pos = layers.map((col, li) => col.map((label, ni) => ({
    x: 92 + li * ((W - 170) / (layers.length - 1)),
    y: (H / (col.length + 1)) * (ni + 1), label,
  })));
  const edges = [];
  for (let l = 0; l < pos.length - 1; l++) for (const a of pos[l]) for (const b of pos[l + 1]) edges.push([a, b, l]);
  const hot = useMemo(() => {
    const set = new Set();
    let seed = firing * 9301 + 49297;
    for (let i = 0; i < 26; i++) { seed = (seed * 9301 + 49297) % 233280; set.add(Math.floor((seed / 233280) * edges.length)); }
    return set;
  }, [firing, edges.length]);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="The learning network firing">
      <defs>
        <radialGradient id="glow"><stop offset="0%" stopColor="#60a5fa" stopOpacity="0.9" /><stop offset="100%" stopColor="#60a5fa" stopOpacity="0" /></radialGradient>
      </defs>
      {edges.map(([a, b], i) => (
        <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={hot.has(i) ? '#60a5fa' : '#1e293b'} strokeWidth={hot.has(i) ? 1.4 : 0.6}
          strokeOpacity={hot.has(i) ? 0.9 : 0.8} className={hot.has(i) ? 'mp-fire' : ''} />
      ))}
      {pos.flat().map((n, i) => (
        <g key={i}>
          <circle cx={n.x} cy={n.y} r="11" fill="url(#glow)" className="mp-pulse" style={{ animationDelay: `${(i % 7) * 0.23}s` }} />
          <circle cx={n.x} cy={n.y} r="4.5" fill={n.label === 'Playing out' ? '#4ade80' : n.label === 'Not yet' ? '#f87171' : '#93c5fd'} />
        </g>
      ))}
      {pos[0].map((n, i) => <text key={`i${i}`} x={n.x - 10} y={n.y + 3.5} textAnchor="end" fontSize="9.5" fill="#cbd5e1">{n.label.length > 13 ? n.label.slice(0, 12) + '…' : n.label}</text>)}
      {pos[pos.length - 1].map((n, i) => <text key={`o${i}`} x={n.x + 10} y={n.y + 3.5} fontSize="9.5" fill="#cbd5e1">{n.label}</text>)}
    </svg>
  );
}

function Growth({ data }) {
  if (!data?.length) return null;
  const W = 340, H = 110, max = Math.max(1, ...data.map((d) => d.beliefs), ...data.map((d) => d.graded));
  const path = (k) => data.map((d, i) => `${i ? 'L' : 'M'}${(i / (data.length - 1)) * W},${H - (d[k] / max) * (H - 8)}`).join(' ');
  const area = (k) => `${path(k)} L${W},${H} L0,${H} Z`;
  return (
    <svg viewBox={`0 0 ${W} ${H + 16}`} className="w-full h-auto" role="img" aria-label="Beliefs learned and picks graded over the last 30 days">
      <path d={area('beliefs')} fill="#2563eb" fillOpacity="0.18" />
      <path d={path('beliefs')} fill="none" stroke="#60a5fa" strokeWidth="2" />
      <path d={path('graded')} fill="none" stroke="#4ade80" strokeWidth="2" strokeDasharray="4 3" />
      <text x="0" y={H + 14} fontSize="9" fill="#64748b">30 days ago</text>
      <text x={W} y={H + 14} fontSize="9" fill="#64748b" textAnchor="end">today</text>
    </svg>
  );
}

function Feed({ items, render, every = 2600 }) {
  const [k, setK] = useState(0);
  useEffect(() => { if (items.length < 2) return undefined; const id = setInterval(() => setK((x) => x + 1), every); return () => clearInterval(id); }, [items.length, every]);
  if (!items.length) return <p className="text-sm text-slate-500">Nothing yet. It fills in as the brain works.</p>;
  const shown = Array.from({ length: Math.min(4, items.length) }, (_, i) => items[(k + i) % items.length]);
  return (
    <div className="space-y-2">
      <AnimatePresence initial={false} mode="popLayout">
        {shown.map((it, i) => (
          <motion.div key={`${k + i}`} layout initial={{ opacity: 0, y: -12 }} animate={{ opacity: i === 0 ? 1 : 0.75 - i * 0.12, y: 0 }} exit={{ opacity: 0, y: 12 }} transition={{ duration: 0.35 }}>
            {render(it)}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

function until(iso, now) {
  const t = Date.parse(iso || ''); if (!t) return '';
  let sec = Math.max(0, Math.round((t - now) / 1000));
  const h = Math.floor(sec / 3600); sec -= h * 3600;
  const m = Math.floor(sec / 60), s = sec % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}:${String(s).padStart(2, '0')}`;
}

function eventText(e) {
  if (e.kind === 'person') return { title: `Someone shared a belief${e.topic ? ` about ${themeLabel(e.topic)}` : ''}`, sub: e.direction === 'bearish' ? 'Expecting a fall' : e.direction === 'volatile' ? 'Expecting a big move' : 'Expecting a rise' };
  if (e.kind === 'news') return { title: `Learned ${e.n} belief${e.n === 1 ? '' : 's'} from today's news`, sub: 'Both sides of each story' };
  if (e.kind === 'practice') return { title: `Practiced on ${e.n} belief${e.n === 1 ? '' : 's'}`, sub: 'Past dates, graded right away' };
  if (e.kind === 'graded') return { title: `The market graded ${e.n.toLocaleString()} picks`, sub: `${e.right.toLocaleString()} beat the S&P 500` };
  if (e.kind === 'trained') return { title: 'Trained a new brain', sub: (STATUS[e.status] || STATUS.retired).label };
  return { title: '', sub: '' };
}

export default function BrainPage({ viewOnly = false }) {
  const navigate = useNavigate();
  const account = useAccount();
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const [now, setNow] = useState(Date.now());
  const [firing, setFiring] = useState(0);
  useEffect(() => {
    let alive = true;
    const load = () => request('/v4/brain').then((x) => alive && (setD(x), setErr(null))).catch((e) => alive && setErr(e.message));
    load();
    const a = setInterval(load, 15000), b = setInterval(() => setNow(Date.now()), 1000), c = setInterval(() => setFiring((f) => f + 1), 700);
    return () => { alive = false; clearInterval(a); clearInterval(b); clearInterval(c); };
  }, []);
  const seenRef = React.useRef(null);
  const [fresh, setFresh] = useState(new Set());
  useEffect(() => {
    if (!d?.activity) return;
    const keys = d.activity.map((e) => `${e.kind}|${e.at}`);
    if (seenRef.current) setFresh(new Set(keys.filter((k) => !seenRef.current.has(k))));
    seenRef.current = new Set(keys);
  }, [d]);
  const c = d?.counts || {};
  const rightPct = c.graded ? Math.round((c.graded_right / c.graded) * 100) : null;
  const versions = d?.versions || [];
  const latest = versions[versions.length - 1];

  return (
    <div className="min-h-screen mp-bg text-white pb-28">
      <style>{`
        @keyframes mpPulse { 0%,100% { opacity:.25; transform:scale(.8) } 50% { opacity:.9; transform:scale(1.25) } }
        .mp-pulse { transform-box: fill-box; transform-origin: center; animation: mpPulse 2.2s ease-in-out infinite; }
        @keyframes mpFire { from { stroke-dashoffset: 24 } to { stroke-dashoffset: 0 } }
        .mp-fire { stroke-dasharray: 6 6; animation: mpFire .7s linear infinite; }
      `}</style>
      <div className="max-w-lg mx-auto px-4" style={{ paddingTop: 'max(2rem, env(safe-area-inset-top))' }}>
        <div className="flex items-center gap-2 text-xs font-bold tracking-wider uppercase">
          <span className="relative flex h-2.5 w-2.5"><span className="absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75 animate-ping" /><span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-green-400" /></span>
          <span className="text-green-300">Live</span>
          {d?.now && <span className="text-slate-500 normal-case font-medium tracking-normal">· updated {ago(d.now, now)}</span>}
        </div>
        {viewOnly && <div className="mt-3 text-sm font-bold text-slate-300">Market<span className="text-blue-400">Playground</span></div>}
        <h1 className="mt-2 text-4xl font-extrabold tracking-tight">The brain, learning</h1>
        <p className="mt-2 text-slate-300">Every belief teaches it which companies really move. Then the market grades it. Nothing here is staged: these are the real numbers, right now.</p>
        {err && <p className="mt-4 text-sm text-red-300">Couldn't load the live data: {err}</p>}

        <div className="mt-5 rounded-3xl border border-blue-500/25 bg-slate-950/60 p-3 shadow-2xl shadow-blue-900/30">
          <Network themes={d?.themes || []} firing={firing} />
          <p className="px-2 pb-1 text-[11px] text-slate-500">Left: the topics it knows best. Right: whether a belief is playing out in the market.</p>
        </div>

        {d?.health && (() => {
          const h = d.health.learning, g = d.health.grading;
          const age = h?.at ? (now - Date.parse(h.at)) / 3600000 : null;
          const good = h && h.ok && age < 2.5;
          return (
            <div className={`mt-3 rounded-2xl border px-3.5 py-2.5 text-xs ${good ? 'border-green-500/30 bg-green-500/[0.06] text-green-100' : 'border-amber-300/40 bg-amber-400/10 text-amber-100'}`}>
              <span className="font-bold">{good ? 'Healthy.' : h ? (h.ok ? 'Learning round overdue.' : 'Last learning round didn’t finish.') : 'No learning round recorded yet.'}</span>{' '}
              {h?.at && <>Last learning round {ago(h.at, now)}.</>}{' '}
              {g?.at && <>Last market grading {ago(g.at, now)}{g.ok ? '' : ' (didn’t finish)'}.</>}
            </div>
          );
        })()}

        {d?.next && (
          <div className="mt-3 grid grid-cols-2 gap-2.5">
            <div className="rounded-2xl border border-blue-400/30 bg-blue-500/10 p-3">
              <div className="text-[11px] uppercase tracking-wider text-blue-200 font-semibold">Next learning round</div>
              <div className="mt-0.5 text-2xl font-extrabold tabular-nums">{until(d.next.learning, now)}</div>
              <div className="text-[11px] text-slate-400">Every hour: reads the news, practices</div>
            </div>
            <div className="rounded-2xl border border-green-400/25 bg-green-500/[0.07] p-3">
              <div className="text-[11px] uppercase tracking-wider text-green-200 font-semibold">Next market grading</div>
              <div className="mt-0.5 text-2xl font-extrabold tabular-nums">{until(d.next.grading, now)}</div>
              <div className="text-[11px] text-slate-400">{new Date(d.next.grading).toLocaleString(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' })}, after the close</div>
            </div>
          </div>
        )}

        <h2 className="mt-8 text-xl font-extrabold">Live activity</h2>
        <div className="mt-2 space-y-2">
          {(d?.activity || []).length === 0 && <p className="text-sm text-slate-500">Quiet right now. The next round starts on the clock above.</p>}
          <AnimatePresence initial={false}>
            {(d?.activity || []).slice(0, 8).map((e) => {
              const k = `${e.kind}|${e.at}`; const t = eventText(e);
              return (
                <motion.div key={k} layout initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
                  className={`rounded-2xl border px-3.5 py-2.5 flex items-center justify-between gap-3 ${fresh.has(k) ? 'border-blue-400/60 bg-blue-500/10' : 'border-slate-700/70 bg-slate-900/70'}`}>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold leading-snug">{t.title}</div>
                    <div className="text-[11px] text-slate-400">{t.sub}</div>
                  </div>
                  <div className="shrink-0 text-right">
                    {fresh.has(k) && <div className="text-[10px] font-extrabold text-blue-300">NEW</div>}
                    <div className="text-[11px] text-slate-500">{ago(e.at, now)}</div>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2.5">
          {[['Beliefs learned', c.beliefs, `${(c.beliefs_today || 0).toLocaleString()} today`],
            ['Companies it knows', c.companies, `${(c.picks || 0).toLocaleString()} ideas built`],
            ['Graded by the market', c.graded, `vs the S&P 500`],
            ['Brains trained', c.versions, latest ? `last ${ago(latest.at, now)}` : 'first one soon']].map(([k, v, sub]) => (
            <div key={k} className="rounded-2xl border border-slate-700/70 bg-slate-900/70 p-3.5">
              <div className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">{k}</div>
              <div className="mt-1 text-3xl font-extrabold tabular-nums"><CountUp value={v || 0} /></div>
              <div className="text-[11px] text-slate-500">{sub}</div>
            </div>
          ))}
        </div>

        {rightPct != null && (
          <div className="mt-2.5 rounded-2xl border border-slate-700/70 bg-slate-900/70 p-4 flex items-center gap-4">
            <svg viewBox="0 0 36 36" className="w-16 h-16 shrink-0 -rotate-90"><circle cx="18" cy="18" r="15.9" fill="none" stroke="#1e293b" strokeWidth="3.5" />
              <circle cx="18" cy="18" r="15.9" fill="none" stroke="#4ade80" strokeWidth="3.5" strokeDasharray={`${rightPct} 100`} strokeLinecap="round" /></svg>
            <div>
              <div className="text-2xl font-extrabold">{rightPct}% <span className="text-base font-bold text-slate-300">beat the market</span></div>
              <div className="text-xs text-slate-400">Of {c.graded?.toLocaleString()} graded picks, in the direction the belief expected. Includes practice beliefs.</div>
            </div>
          </div>
        )}

        <h2 className="mt-8 text-xl font-extrabold">Just learned</h2>
        <div className="mt-2">
          <Feed items={d?.learned || []} render={(x) => (
            <div className="rounded-2xl border border-slate-700/70 bg-slate-900/70 px-3.5 py-2.5">
              <div className="text-[11px] text-slate-500">{x.from_news ? 'From today\'s news' : 'Practice belief'} · {ago(x.at, now)}</div>
              <div className="text-sm font-semibold leading-snug">“{x.text}”</div>
              {x.picks?.length > 0 && <div className="mt-1 text-xs text-slate-300">→ {x.picks.map((p) => `${p.ticker} ${p.direction === 'bearish' ? '▼' : '▲'}`).join('  ·  ')}</div>}
            </div>
          )} />
        </div>

        <h2 className="mt-8 text-xl font-extrabold">Just graded by the market</h2>
        <div className="mt-2">
          <Feed every={2100} items={d?.graded || []} render={(x) => (
            <div className="rounded-2xl border border-slate-700/70 bg-slate-900/70 px-3.5 py-2.5 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm font-bold">{x.ticker} <span className="text-xs font-semibold text-slate-400">{x.direction} · after {x.days} days</span></div>
                <div className="text-[11px] text-slate-500">{ago(x.at, now)}</div>
              </div>
              <div className={`text-right font-extrabold ${x.right ? 'text-green-300' : 'text-red-300'}`}>
                {x.right ? '✓' : '✗'} {x.vs_market >= 0 ? '+' : ''}{(x.vs_market * 100).toFixed(1)}%
                <div className="text-[10px] font-medium text-slate-500">vs S&amp;P 500</div>
              </div>
            </div>
          )} />
        </div>

        <h2 className="mt-8 text-xl font-extrabold">Growing every day</h2>
        <div className="mt-2 rounded-2xl border border-slate-700/70 bg-slate-900/70 p-3.5">
          <Growth data={d?.growth} />
          <div className="mt-1 flex gap-4 text-[11px] text-slate-400"><span><span className="text-blue-300">━</span> beliefs learned</span><span><span className="text-green-300">┅</span> picks graded</span></div>
        </div>

        <h2 className="mt-8 text-xl font-extrabold">It grades itself, honestly</h2>
        <p className="mt-1 text-sm text-slate-300">Each new brain is tested on beliefs it has never seen. If it can't beat the simple baseline, it gets no vote. Here's every version:</p>
        <div className="mt-3 space-y-2">
          {versions.length === 0 && <p className="text-sm text-slate-500">The first brain trains once enough picks are graded.</p>}
          {[...versions].reverse().slice(0, 8).map((v, i) => {
            const st = STATUS[v.status] || STATUS.retired;
            return (
              <div key={i} className="rounded-2xl border border-slate-700/70 bg-slate-900/70 px-3.5 py-2.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-bold rounded-full px-2 py-0.5" style={{ color: st.color, background: `${st.color}22` }}>{st.label}</span>
                  <span className="text-[11px] text-slate-500">{ago(v.at, now)} · trained on {v.n_train.toLocaleString()}, tested on {v.n_test.toLocaleString()}</span>
                </div>
                <div className="mt-1.5 h-1.5 rounded-full bg-slate-800 overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${Math.max(3, Math.min(100, 50 + v.score * 250))}%`, background: st.color }} />
                </div>
                <div className="mt-1 text-[11px] text-slate-400">{v.reason || st.note}</div>
              </div>
            );
          })}
        </div>

        {viewOnly ? (
          <div className="mt-8 rounded-2xl border border-slate-700/70 bg-slate-900/70 p-4 text-sm text-slate-300">
            <div className="font-bold text-white">This page only watches.</div>
            Nothing here can be changed by a viewer. It shows exactly what the live server reports and refreshes every 15 seconds.
            Want to check the numbers yourself? <a href={`${API_BASE}/v4/brain`} target="_blank" rel="noopener noreferrer" className="text-blue-300 underline">See the raw live data</a>.
          </div>
        ) : (
        <div className="mt-8 rounded-3xl border border-blue-400/30 bg-blue-500/10 p-5 text-center">
          <div className="text-lg font-extrabold">Teach it something.</div>
          <p className="mt-1 text-sm text-slate-300">Type a hunch. The market will grade it, and the brain learns from it.</p>
          <button onClick={() => navigate(account ? '/chat' : '/account')} className="mt-3 rounded-2xl bg-blue-600 hover:bg-blue-500 px-5 py-3 font-bold">{account ? 'Type a belief →' : 'Create a free account →'}</button>
        </div>
        )}
        <p className="mt-4 text-[11px] text-slate-500">Practice money only. Past results don't predict future ones. Not investment advice.</p>
      </div>
      {account && !viewOnly && <BottomNavigation />}
    </div>
  );
}
