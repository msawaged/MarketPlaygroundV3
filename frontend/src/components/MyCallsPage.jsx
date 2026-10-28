// "My calls": every belief you've shared on this device and how its picks are doing vs the S&P 500.
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import Page, { Card, pct } from './ui/Page';
import Term from './ui/Term';
import { getMyBeliefs } from '../lib/api';

function ago(iso) {
  const d = (Date.now() - new Date(iso).getTime()) / 86400000;
  if (d < 1) return 'today';
  if (d < 2) return 'yesterday';
  if (d < 30) return `${Math.floor(d)} days ago`;
  return `${Math.floor(d / 30)} mo ago`;
}

function Ring({ ahead, total }) {
  const r = 34, c = 2 * Math.PI * r, f = total ? ahead / total : 0;
  return (
    <svg viewBox="0 0 80 80" className="w-20 h-20 -rotate-90" aria-hidden>
      <circle cx="40" cy="40" r={r} fill="none" stroke="#1e293b" strokeWidth="8" />
      <motion.circle cx="40" cy="40" r={r} fill="none" stroke="#4DA3FF" strokeWidth="8" strokeLinecap="round"
        strokeDasharray={c} initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - f) }} transition={{ duration: 0.9 }} />
    </svg>
  );
}

export default function MyCallsPage() {
  const navigate = useNavigate();
  const [s, setS] = useState({ loading: true });

  useEffect(() => {
    let alive = true;
    getMyBeliefs().then((d) => alive && setS({ data: d })).catch((e) => alive && setS({ error: e.message }));
    return () => { alive = false; };
  }, []);

  const beliefs = s.data?.beliefs || [];
  const sum = s.data?.summary;

  return (
    <Page title="My calls" subtitle="Every belief you've shared, and how its picks are doing.">
      {s.loading && <div className="mt-8 space-y-3">{[0, 1, 2].map((i) => <div key={i} className="h-28 rounded-3xl bg-slate-800/50 animate-pulse" />)}</div>}
      {s.error && <Card className="mt-6 border-red-500/40 text-red-200 text-sm">Couldn't load your calls: {s.error}</Card>}

      {!s.loading && !s.error && beliefs.length === 0 && (
        <Card className="mt-6 text-center py-8">
          <div className="text-4xl" aria-hidden>🌱</div>
          <div className="mt-2 text-lg font-bold">No calls yet</div>
          <p className="mt-1 text-sm text-slate-400 max-w-xs mx-auto">Share a belief and its picks show up here, scored against the S&amp;P 500 as time goes by.</p>
          <button onClick={() => navigate('/chat')} className="mt-5 rounded-2xl bg-blue-600 hover:bg-blue-500 px-5 py-3 font-bold">Share a belief</button>
        </Card>
      )}

      {sum && (
        <Card className="mt-6 flex items-center gap-4 bg-gradient-to-br from-blue-600/25 to-slate-900/70 border-blue-400/30">
          <div className="relative">
            <Ring ahead={sum.ahead} total={sum.tracked} />
            <div className="absolute inset-0 flex items-center justify-center text-lg font-extrabold">{sum.ahead}/{sum.tracked}</div>
          </div>
          <div className="min-w-0">
            <div className="font-bold text-lg leading-tight">
              {sum.ahead === 0 ? 'Early days' : sum.ahead / sum.tracked >= 0.5 ? 'Nice instincts so far' : 'Still playing out'}
            </div>
            <p className="text-sm text-slate-300">
              {sum.ahead} of {sum.tracked} picks are ahead of the S&amp;P 500 in the direction you called.
            </p>
          </div>
        </Card>
      )}

      <div className="mt-4 space-y-3">
        {beliefs.map((b, i) => (
          <motion.div key={b.belief_id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}>
            <Card>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="font-semibold leading-snug">“{b.text}”</div>
                  <div className="mt-0.5 text-xs text-slate-500">{ago(b.created_at)}{b.horizon_days ? ` · plays out over ~${b.horizon_days >= 60 ? `${Math.round(b.horizon_days / 30)} months` : `${b.horizon_days} days`}` : ''}</div>
                </div>
                <button onClick={() => navigate(`/chat?b=${encodeURIComponent(b.text)}&go=1`)} className="shrink-0 text-xs font-semibold text-blue-300 hover:text-blue-200">Run again</button>
              </div>
              {b.picks.length > 0 && (
                <div className="mt-3 grid grid-cols-3 gap-2">
                  {b.picks.map((p) => {
                    const v = p.vs_spy;
                    const tone = v == null ? 'border-slate-700 bg-slate-800/60' : v >= 0 ? 'border-green-500/30 bg-green-500/10' : 'border-red-500/30 bg-red-500/10';
                    return (
                      <div key={p.pick_id} className={`rounded-2xl border p-2.5 ${tone}`}>
                        <div className="font-bold text-sm">{p.ticker}</div>
                        <div className="text-[10px] text-slate-400 truncate">{p.structure}</div>
                        <div className={`mt-1 text-sm font-extrabold ${v == null ? 'text-slate-400' : v >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                          {v == null ? 'new' : pct(v)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </Card>
          </motion.div>
        ))}
      </div>

      {beliefs.length > 0 && (
        <p className="mt-5 text-[11px] text-slate-500 leading-relaxed">
          Numbers are each stock's move since the idea, compared with the S&amp;P 500 (<Term k="vs s&p">vs S&amp;P</Term>), flipped for bearish calls. Options would have moved differently. Saved on this device only.
        </p>
      )}
    </Page>
  );
}
