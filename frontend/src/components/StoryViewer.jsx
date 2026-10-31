// Story mode: one news story as full-screen cards you tap through, like a finance explainer reel.
// Hook -> what happened -> why it matters -> the twist -> who moves -> your call.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { X } from 'lucide-react';
import { getStory } from '../lib/api';
import { ago, believeUrl, doubtUrl } from './MoversFeed';

const CARD_MS = 7000;
const _stories = new Map(); // headline -> story response, for this page load

const MULT = { k: 1e3, thousand: 1e3, m: 1e6, million: 1e6, b: 1e9, bn: 1e9, billion: 1e9, t: 1e12, trillion: 1e12 };
function amount(s) {
  const m = String(s || '').replace(/,/g, '').match(/(-?\d+(?:\.\d+)?)\s*(k|thousand|m|million|bn|b|billion|t|trillion)?/i);
  if (!m) return null;
  return parseFloat(m[1]) * (MULT[(m[2] || '').toLowerCase()] || 1);
}
function change(a, b) {
  if (!a || b == null) return null;
  const r = b / a;
  if (r >= 1.95) return `${r.toFixed(r >= 10 ? 0 : 1)}x`;
  const p = (r - 1) * 100;
  return `${p >= 0 ? '+' : ''}${p.toFixed(Math.abs(p) < 10 ? 1 : 0)}%`;
}

function Label({ children, tone = 'text-blue-400' }) {
  return <div className={`text-xs font-bold uppercase tracking-[0.2em] ${tone}`}>{children}</div>;
}

function Figure({ f, i }) {
  const a = amount(f.before), b = amount(f.after);
  const max = Math.max(a || 0, b || 0) || 1;
  const chg = change(a, b);
  const up = a != null && b != null && b >= a;
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 + i * 0.2 }}
      className="rounded-2xl bg-white text-slate-900 p-4 shadow-xl">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-black uppercase tracking-wider">{f.label}</div>
        {chg && <div className={`rounded-lg px-2 py-0.5 text-lg font-black text-white ${up ? 'bg-green-600' : 'bg-red-600'}`}>{chg}</div>}
      </div>
      {[[f.before_label, f.before, a, 'bg-slate-300'], [f.after_label, f.after, b, 'bg-blue-600']].map(([lab, txt, v, color], j) => (
        <div key={j} className="mt-3">
          <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">{lab}</div>
          <div className="mt-1 flex items-center gap-3">
            <div className="h-5 flex-1 rounded-full bg-slate-100 overflow-hidden">
              <motion.div className={`h-full rounded-full ${color}`} initial={{ width: 0 }}
                animate={{ width: `${Math.max(6, ((v || 0) / max) * 100)}%` }} transition={{ delay: 0.4 + i * 0.2 + j * 0.25, duration: 0.7 }} />
            </div>
            <div className={`w-20 text-right text-lg font-black tabular-nums ${j ? 'text-blue-700' : ''}`}>{txt}</div>
          </div>
        </div>
      ))}
    </motion.div>
  );
}

function Pct({ v }) {
  if (v == null) return null;
  return <span className={`text-lg font-black tabular-nums ${v >= 0 ? 'text-green-400' : 'text-red-400'}`}>{v >= 0 ? '+' : ''}{(v * 100).toFixed(1)}%</span>;
}

function cards(data, navigate, reel = false) {
  const { story: s, item } = data;
  const big = 'text-[1.7rem] leading-snug font-bold text-white';
  const out = [
    <div key="hook" className="flex h-full flex-col justify-center">
      <Label>Moving now</Label>
      <motion.div initial={{ scale: 0.85, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: 'spring', stiffness: 160 }}
        className="mt-4 text-6xl font-black leading-[0.95] tracking-tight bg-gradient-to-br from-white to-blue-400 bg-clip-text text-transparent">
        {s.hook_big}
      </motion.div>
      <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.35 }} className="mt-5 text-xl text-slate-200">{s.hook_line}</motion.p>
      <div className="mt-8 text-xs text-slate-500">{[item.source, ago(item.created_at)].filter(Boolean).join(' · ')}</div>
    </div>,
    <div key="happened" className="flex h-full flex-col justify-center gap-5">
      <Label>What happened</Label>
      <p className={big}>{s.happened}</p>
      {s.figures.map((f, i) => <Figure key={i} f={f} i={i} />)}
    </div>,
    <div key="why" className="flex h-full flex-col justify-center gap-5">
      <Label>Why it matters</Label>
      <p className={big}>{s.why}</p>
    </div>,
    <div key="twist" className="flex h-full flex-col justify-center">
      <div className="text-3xl font-black uppercase text-white">But here's the</div>
      <motion.div initial={{ rotate: -4, scale: 0.6, opacity: 0 }} animate={{ rotate: -2, scale: 1, opacity: 1 }} transition={{ type: 'spring', stiffness: 200, delay: 0.15 }}
        className="mt-2 self-start bg-amber-400 px-3 py-1 text-6xl font-black uppercase text-slate-950">Twist</motion.div>
      <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }} className={`mt-8 ${big}`}>{s.twist}</motion.p>
    </div>,
  ];
  if (item.companies?.length) {
    out.push(
      <div key="who" className="flex h-full flex-col justify-center">
        <Label>Who it moves</Label>
        <ul className="mt-5 space-y-3">
          {item.companies.map((c, i) => (
            <motion.li key={c.ticker} initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 + i * 0.12 }}
              className="flex items-center gap-4 rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3">
              <div className="min-w-0 flex-1">
                <div className="text-2xl font-black text-white">{c.ticker}</div>
                {c.why && <div className="text-sm text-slate-400 truncate">{c.why}</div>}
              </div>
              <div className="text-right leading-tight">
                {c.direction && <div className={`text-xs font-semibold ${c.direction === 'up' ? 'text-green-300' : 'text-red-300'}`}>{c.direction === 'up' ? 'could gain' : 'could lose'}</div>}
                <Pct v={c.change} />
                {c.change != null && <div className="text-[10px] text-slate-500">today</div>}
              </div>
            </motion.li>
          ))}
        </ul>
      </div>,
    );
  }
  if (reel) {
    out.push(
      <div key="cta" className="flex h-full flex-col justify-center">
        <Label>Your call</Label>
        <p className="mt-5 text-3xl font-black leading-tight text-white">“{item.hunch.replace(/\.$/, '')}.”</p>
        <motion.div initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay: 0.4, type: 'spring', stiffness: 180 }}
          className="mt-8 text-4xl font-black text-white">Believe it<span className="text-slate-500"> or </span>doubt it?</motion.div>
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.9 }}
          className="mt-8 rounded-2xl bg-blue-600 px-5 py-4 text-center">
          <div className="text-lg font-black">Make your call free</div>
          <div className="text-sm text-blue-100">MarketPlayground · link in bio</div>
        </motion.div>
        <p className="mt-4 text-center text-xs text-slate-500">Practice money only. Not investment advice.</p>
      </div>,
    );
    return out;
  }
  out.push(
    <div key="call" className="flex h-full flex-col justify-center">
      <Label>Your call</Label>
      <p className="mt-5 text-3xl font-black leading-tight text-white">“{item.hunch.replace(/\.$/, '')}.”</p>
      <p className="mt-3 text-slate-400">Believe it or doubt it. Either way, we'll show you the smartest way to play it.</p>
      <button onClick={(e) => { e.stopPropagation(); navigate(believeUrl(item.hunch)); }}
        className="mt-8 w-full rounded-2xl bg-blue-600 py-4 text-lg font-black text-white hover:bg-blue-500">I believe it →</button>
      <button onClick={(e) => { e.stopPropagation(); navigate(doubtUrl(item.hunch)); }}
        className="mt-3 w-full rounded-2xl border border-slate-600 py-4 text-lg font-bold text-slate-200 hover:bg-slate-800">I doubt it</button>
      <p className="mt-4 text-center text-xs text-slate-500">Practice money only. Not investment advice.</p>
    </div>,
  );
  return out;
}

export default function StoryViewer({ headline, onClose, reel = false, cardMs = CARD_MS }) {
  const navigate = useNavigate();
  const [data, setData] = useState(() => _stories.get(headline) || null);
  const [err, setErr] = useState('');
  const [idx, setIdx] = useState(0);
  const [paused, setPaused] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const downAt = useRef(0);

  useEffect(() => {
    if (data) return undefined;
    let alive = true;
    getStory(headline)
      .then((d) => { _stories.set(headline, d); if (alive) setData(d); })
      .catch((e) => alive && setErr(e?.message || "Couldn't load this story."));
    return () => { alive = false; };
  }, [headline, data]);

  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => { document.body.style.overflow = prev; window.removeEventListener('keydown', onKey); };
  }, [onClose]);

  const list = data ? cards(data, navigate, reel) : [];
  const last = list.length - 1;
  const go = useCallback((d) => {
    setElapsed(0);
    setIdx((i) => {
      const n = i + d;
      if (n < 0) return 0;
      if (n > last) { onClose(); return i; }
      return n;
    });
  }, [last, onClose]);

  // auto-advance like a story; hold to pause; the last card waits for a choice
  useEffect(() => {
    if (!data || paused || (idx >= last && !reel)) return undefined;
    const t = setInterval(() => setElapsed((e) => {
      if (e + 100 >= cardMs) {
        if (reel && idx >= last) { window.__reelDone = true; return cardMs; } // recording: stop on the last card
        go(1); return 0;
      }
      return e + 100;
    }), 100);
    return () => clearInterval(t);
  }, [data, paused, idx, last, go, reel, cardMs]);
  useEffect(() => { if (reel && data) window.__reelStart = performance.now(); }, [reel, data]);

  const onDown = () => { downAt.current = Date.now(); setPaused(true); };
  const onUp = (e) => {
    setPaused(false);
    if (e.target.closest?.('button,a')) return; // buttons on a card do their own thing
    if (Date.now() - downAt.current > 350) return; // that was a hold, not a tap
    const x = e.clientX ?? e.changedTouches?.[0]?.clientX ?? 0;
    go(x < window.innerWidth * 0.3 ? -1 : 1);
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950 text-white select-none" role="dialog" aria-label="Story">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(37,99,235,0.25),transparent_60%)]" />
      <div className="relative mx-auto flex h-full max-w-md flex-col px-5 pt-[max(env(safe-area-inset-top),12px)] pb-[max(env(safe-area-inset-bottom),16px)]">
        <div className="flex gap-1.5 pt-2">
          {(list.length ? list : [0]).map((_, i) => (
            <div key={i} className="h-1 flex-1 overflow-hidden rounded-full bg-white/20">
              <div className="h-full bg-white" style={{ width: i < idx ? '100%' : i === idx ? `${idx >= last && !reel ? 100 : Math.min(100, (elapsed / cardMs) * 100)}%` : '0%' }} />
            </div>
          ))}
        </div>
        <div className="mt-3 flex items-center justify-between">
          <div className="text-sm font-bold">Market<span className="text-blue-400">Playground</span></div>
          {reel ? <div className="text-xs font-semibold text-slate-400">Moving now</div>
            : <button onClick={onClose} aria-label="Close story" className="rounded-full p-2 hover:bg-white/10"><X className="h-5 w-5" /></button>}
        </div>
        <div className="relative flex-1" {...(reel ? {} : { onPointerDown: onDown, onPointerUp: onUp, onPointerLeave: () => setPaused(false) })}>
          {!data && !err && (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-slate-400">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
              <div>Writing the story…</div>
            </div>
          )}
          {err && <div className="flex h-full items-center justify-center text-center text-slate-300">{err}</div>}
          <AnimatePresence mode="wait">
            {data && (
              <motion.div key={idx} className="absolute inset-0" initial={{ opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -30 }} transition={{ duration: 0.22 }}>
                {list[idx]}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
