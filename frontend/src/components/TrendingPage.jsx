// What people believe right now, across everyone using MarketPlayground.
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { getTrending } from '../lib/api';
import BottomNavigation from './BottomNavigation';
import { themeLabel } from '../lib/text';
import { useMovers, MoverCard, ago } from './MoversFeed';

function pct(v) {
  if (v == null) return null;
  return `${v >= 0 ? '+' : ''}${(v * 100).toFixed(1)}%`;
}

export default function TrendingPage() {
  const navigate = useNavigate();
  const [state, setState] = useState({ loading: true, error: null, data: null });

  useEffect(() => {
    let alive = true;
    getTrending(14)
      .then((data) => alive && setState({ loading: false, error: null, data }))
      .catch((e) => alive && setState({ loading: false, error: e.message, data: null }));
    return () => { alive = false; };
  }, []);

  const movers = useMovers();
  const items = movers.data?.items || [];
  const themes = state.data?.themes || [];
  const tryIt = (theme, example) => navigate(`/chat?b=${encodeURIComponent(example || `${theme} demand will grow`)}`);

  return (
    <div className="min-h-screen mp-bg text-white pb-28">
      <div className="max-w-lg mx-auto px-4 pt-8" style={{ paddingTop: 'max(2rem, env(safe-area-inset-top))' }}>
        <h1 className="text-3xl font-extrabold">Moving now</h1>
        <p className="mt-1 text-slate-300">Today's market news and the companies it touches.</p>
        {movers.data?.built_at && <p className="mt-1 text-[11px] text-slate-500">Updated {ago(movers.data.built_at)}</p>}
        {movers.loading && <div className="mt-6 text-slate-400">Reading today's news…</div>}
        {!movers.loading && items.length === 0 && (
          <div className="mt-6 rounded-2xl border border-slate-700 bg-slate-900 p-4 text-sm text-slate-400">The news feed is quiet right now. Check back soon.</div>
        )}
        <div className="mt-4 space-y-3">
          {items.map((it, i) => <MoverCard key={it.headline} item={it} i={i} />)}
        </div>

        <h2 className="mt-10 text-2xl font-extrabold">What people believe</h2>
        <p className="mt-1 text-slate-300">
          The hunches MarketPlayground users are backing, and the picks that keep coming up.
          {state.data?.window ? <span className="text-slate-500"> ({state.data.window})</span> : null}
        </p>

        {state.loading && <div className="mt-8 text-slate-400">Loading…</div>}
        {state.error && (
          <div className="mt-8 rounded-xl border border-red-500/40 bg-red-950/40 p-4 text-sm text-red-200">
            Couldn't load trending beliefs: {state.error}
          </div>
        )}
        {!state.loading && !state.error && themes.length === 0 && (
          <div className="mt-8 rounded-2xl border border-slate-700 bg-slate-900 p-5">
            <div className="font-semibold">No shared beliefs yet</div>
            <p className="mt-1 text-sm text-slate-400">Be the first: pick a hunch above, or type your own.</p>
            <button onClick={() => navigate('/chat')} className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold">Share a belief</button>
          </div>
        )}

        <div className="mt-6 space-y-3">
          {themes.map((t, i) => (
            <motion.div
              key={t.theme}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
              className="rounded-2xl border border-slate-700 bg-slate-900/90 p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-lg font-bold">{themeLabel(t.theme)}</span>
                    <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${t.direction === 'bearish' ? 'bg-red-500/15 text-red-400' : t.direction === 'bullish' ? 'bg-green-500/15 text-green-400' : t.direction === 'volatile' ? 'bg-violet-500/15 text-violet-300' : 'bg-slate-700 text-slate-300'}`}>
                      {t.direction === 'bearish' ? 'Bearish' : t.direction === 'bullish' ? 'Bullish' : t.direction === 'volatile' ? 'Big move' : 'Neutral'}
                    </span>
                  </div>
                  {t.example && <p className="mt-1 text-sm text-slate-300">{t.example}</p>}
                </div>
                <div className="text-right shrink-0">
                  <div className="text-xl font-extrabold text-blue-400">{t.people ?? t.beliefs}</div>
                  <div className="text-[11px] text-slate-500">{(t.people ?? t.beliefs) === 1 ? 'person' : 'people'}</div>
                </div>
              </div>

              {t.tickers?.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {t.tickers.map((k) => (
                    <span key={k.ticker} className="rounded-lg bg-slate-800 border border-slate-700 px-2.5 py-1 text-sm">
                      <span className="font-bold">{k.ticker}</span>
                      {k.graded > 0 && k.avg_vs_spy != null && (
                        <span className={`ml-1.5 text-xs ${k.avg_vs_spy >= 0 ? 'text-green-400' : 'text-red-400'}`}>{pct(k.avg_vs_spy)} vs S&amp;P</span>
                      )}
                    </span>
                  ))}
                </div>
              )}

              <button onClick={() => tryIt(t.theme, t.example)} className="mt-3 text-sm font-semibold text-blue-300 hover:text-blue-200">
                Try this belief →
              </button>
            </motion.div>
          ))}
        </div>



        <p className="mt-6 text-[11px] text-slate-500">
          "vs S&amp;P" is how a pick did against the S&amp;P 500, in the direction people expected, 30 days after it was suggested. Past results don't predict future ones.
        </p>
      </div>
      <BottomNavigation />
    </div>
  );
}
