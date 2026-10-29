// "How it's learning": the shared learning loop, explained and shown live.
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import Page, { Card, pct } from './ui/Page';
import { getLearning } from '../lib/api';

function Stat({ value, label }) {
  return (
    <div className="rounded-2xl bg-slate-800/60 border border-slate-700/70 p-3 text-center">
      <div className="text-2xl font-extrabold text-white tabular-nums">{Number(value || 0).toLocaleString()}</div>
      <div className="text-[11px] text-slate-400 leading-tight mt-0.5">{label}</div>
    </div>
  );
}

const STEPS = [
  ['You share a belief', 'Claude finds the companies and funds it affects.'],
  ['Every pick gets graded', 'After 1 week, 1 month, 3 months and longer, against the S&P 500, with real prices.'],
  ['The scoreboard nudges future picks', 'Picks like the ones that worked move up; ones that missed move down.'],
  ['Our own network practices', "It studies every graded pick from everyone. It only gets a say once it beats Claude's picks on beliefs it has never seen."],
];

export default function LearningPage() {
  const navigate = useNavigate();
  const [s, setS] = useState({ loading: true });
  useEffect(() => {
    let alive = true;
    // Owner opens /learning?key=<MP_ADMIN_TOKEN> once on their device; regular users get a 'private' note.
    const k = new URLSearchParams(window.location.search).get('key');
    if (k) { try { localStorage.setItem('mp_owner_key', k); } catch { /* ignore */ } window.history.replaceState(null, '', '/learning'); }
    getLearning().then((d) => alive && setS({ data: d })).catch((e) => alive && setS({ error: e.message }));
    return () => { alive = false; };
  }, []);
  const d = s.data;

  return (
    <Page title="How it learns" subtitle="Owner view: the learning loop, the practice feed and the network.">
      {s.error && <Card className="mt-6 text-sm text-slate-300">This page is private.</Card>}
      {s.loading && <div className="mt-6 h-24 rounded-3xl bg-slate-800/50 animate-pulse" />}

      {d && (
        <>
          <div className="mt-6 grid grid-cols-3 gap-2">
            <Stat value={d.beliefs_from_people} label="beliefs from people" />
            <Stat value={d.practice_beliefs} label="practice beliefs" />
            <Stat value={d.graded_picks} label="picks graded" />
          </div>

          <div className="mt-4 space-y-2.5">
            {d.layers.map((l, i) => (
              <motion.div key={l.name} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.06 }}>
                <Card className="flex gap-3 items-start">
                  <span className={`mt-1 w-3 h-3 rounded-full shrink-0 ${l.on ? 'bg-green-400 shadow-[0_0_12px_rgba(74,222,128,0.7)]' : l.status === 'shadow' ? 'bg-amber-300' : 'bg-slate-600'}`} aria-hidden />
                  <div className="min-w-0">
                    <div className="font-bold">{l.name} <span className={`ml-1 text-[11px] font-semibold ${l.on ? 'text-green-300' : l.status === 'shadow' ? 'text-amber-200' : 'text-slate-400'}`}>
                      {l.on ? 'ON' : l.status === 'shadow' ? 'PRACTICING' : 'WAITING'}
                    </span></div>
                    <p className="text-sm text-slate-300 leading-relaxed">{l.what}</p>
                  </div>
                </Card>
              </motion.div>
            ))}
          </div>

          {d.scorecard && (
            <Card className="mt-4">
              <div className="text-sm font-bold">Two separate questions ({d.scorecard.checkpoint_days} days after each belief)</div>
              <p className="text-xs text-slate-400">Whether a belief comes true is the person's call. Our job is to turn it into the best trade.</p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <div className="rounded-2xl bg-slate-800/60 border border-slate-700/70 p-3">
                  <div className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">Their part</div>
                  <div className="mt-1 text-2xl font-extrabold">{Math.round(d.scorecard.calls.came_true_rate * 100)}%</div>
                  <div className="text-xs text-slate-300">of calls came true ({d.scorecard.calls.n} graded)</div>
                </div>
                <div className="rounded-2xl bg-blue-500/10 border border-blue-400/30 p-3">
                  <div className="text-[11px] uppercase tracking-wider text-blue-200 font-semibold">Our part</div>
                  <div className="mt-1 text-2xl font-extrabold">{Math.round(d.scorecard.picks.beat_rate * 100)}%</div>
                  <div className="text-xs text-slate-300">of shown picks beat the simple choice, avg {pct(d.scorecard.picks.avg_edge)} ({d.scorecard.picks.n} graded)</div>
                </div>
              </div>
              <div className="mt-2 text-xs text-slate-400 space-y-0.5">
                <div>When the call came true: picks beat the simple choice {Math.round(d.scorecard.picks_when_right.beat_rate * 100)}% of the time, avg {pct(d.scorecard.picks_when_right.avg_edge)}.</div>
                <div>Top pick only: {Math.round(d.scorecard.top_pick.beat_rate * 100)}%, avg {pct(d.scorecard.top_pick.avg_edge)}.</div>
                {d.scorecard_real && <div>Real people only: {d.scorecard_real.calls.n} calls graded, {d.scorecard_real.picks.n} picks graded.</div>}
                <div>"Simple choice" = the sector fund among the ideas, or the average of the ideas in the same direction.</div>
              </div>
            </Card>
          )}

          {d.versions.length > 0 && (
            <Card className="mt-4">
              <div className="text-sm font-bold">Network versions</div>
              <p className="text-xs text-slate-400">Each bar is one training run. Taller means its picks lined up better with what really happened.</p>
              <div className="mt-3 flex items-end gap-1.5 h-24">
                {d.versions.map((v, i) => {
                  const h = Math.max(6, Math.min(100, (v.accuracy + 0.05) * 400));
                  return (
                    <div key={i} className="flex-1 h-full flex flex-col justify-end" title={`${v.date}: ${v.status}, ${v.examples} examples`}>
                      <motion.div initial={{ height: 0 }} animate={{ height: `${h}%` }} transition={{ delay: i * 0.04 }}
                        className={`w-full rounded-t-md ${v.status === 'active' ? 'bg-green-400' : v.status === 'shadow' ? 'bg-amber-300/80' : 'bg-slate-600'}`} />
                    </div>
                  );
                })}
              </div>
              <div className="mt-2 flex gap-3 text-[11px] text-slate-400">
                <span><span className="inline-block w-2 h-2 rounded-sm bg-green-400 mr-1" />in use</span>
                <span><span className="inline-block w-2 h-2 rounded-sm bg-amber-300 mr-1" />practicing</span>
                <span><span className="inline-block w-2 h-2 rounded-sm bg-slate-600 mr-1" />retired</span>
              </div>
            </Card>
          )}
        </>
      )}

      <Card className="mt-4">
        <div className="text-sm font-bold">The loop</div>
        <ol className="mt-3 space-y-3">
          {STEPS.map(([t, b], i) => (
            <li key={t} className="flex gap-3">
              <span className="w-7 h-7 shrink-0 rounded-full bg-blue-600/25 text-blue-200 text-sm font-bold flex items-center justify-center">{i + 1}</span>
              <span>
                <span className="block text-sm font-semibold">{t}</span>
                <span className="block text-xs text-slate-400 leading-relaxed">{b}</span>
              </span>
            </li>
          ))}
        </ol>
      </Card>

      <Card className="mt-4 text-sm text-slate-300">
        👍 and 👎 on picks count too. Every vote nudges what everyone sees next.
        <button onClick={() => navigate('/chat')} className="mt-3 w-full rounded-2xl bg-blue-600 hover:bg-blue-500 py-3 font-bold text-white">Teach it a belief</button>
      </Card>
    </Page>
  );
}
