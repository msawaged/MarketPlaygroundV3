// Home: start with a belief, see what's hot, jump to your calls and tools.
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Flame, ShoppingBasket, TrendingUp, Brain, ArrowRight, Target } from 'lucide-react';
import BottomNavigation from './BottomNavigation';
import { getTrending } from '../lib/api';
import { recentBeliefs } from '../lib/recent';
import { themeLabel } from '../lib/text';

const ROTATE = [
  'plumbing demand is about to boom',
  'potatoes are in demand',
  'everyone is getting a pet',
  'air travel slows down next year',
  'AI needs way more electricity',
  'people are eating out less',
];

const TOOLS = [
  { path: '/trending', icon: Flame, title: 'Trending', body: 'What people believe now', tint: 'text-amber-300 bg-amber-400/10' },
  { path: '/my', icon: Target, title: 'My calls', body: 'How your picks are doing', tint: 'text-blue-300 bg-blue-400/10' },
  { path: '/basket-builder', icon: ShoppingBasket, title: 'Baskets', body: 'A goal → a simple fund mix', tint: 'text-sky-300 bg-sky-400/10' },
  { path: '/portfolio', icon: TrendingUp, title: 'Practice', body: 'Paper trades, no real money', tint: 'text-green-300 bg-green-400/10' },
];

export default function ToolSelectorPage() {
  const navigate = useNavigate();
  const [text, setText] = useState('');
  const [i, setI] = useState(0);
  const [hot, setHot] = useState([]);
  const recent = recentBeliefs();

  useEffect(() => {
    const id = setInterval(() => setI((x) => (x + 1) % ROTATE.length), 2600);
    return () => clearInterval(id);
  }, []);
  useEffect(() => {
    getTrending(14).then((d) => setHot((d?.themes || []).slice(0, 4))).catch(() => {});
  }, []);

  const go = (b) => {
    const belief = (b ?? text).trim();
    navigate(belief ? `/chat?b=${encodeURIComponent(belief)}&go=1` : '/chat');
  };

  return (
    <div className="min-h-screen mp-bg text-white pb-28 overflow-x-hidden">
      <div className="max-w-lg mx-auto px-4" style={{ paddingTop: 'max(2rem, env(safe-area-inset-top))' }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center font-black shadow-lg shadow-blue-600/30">M</div>
            <div className="font-bold">MarketPlayground</div>
          </div>
          <span className="text-[10px] font-bold tracking-wider uppercase text-blue-200 bg-blue-500/15 border border-blue-400/30 rounded-full px-2.5 py-1">Free beta</span>
        </div>

        <h1 className="mt-8 text-[2.6rem] leading-[1.05] font-extrabold tracking-tight">
          Your belief.<br /><span className="mp-gradient-text">The right strategy.</span>
        </h1>
        <p className="mt-3 text-slate-300">Prediction apps hand you someone else's question. Start with yours.</p>

        {/* The belief box */}
        <form onSubmit={(e) => { e.preventDefault(); go(); }} className="mt-6 rounded-3xl p-[1.5px] bg-gradient-to-br from-blue-400/70 via-blue-600/40 to-slate-700/40 shadow-2xl shadow-blue-900/40">
          <div className="rounded-[22px] bg-slate-950/90 p-4">
            <label htmlFor="home-belief" className="text-xs uppercase tracking-wider text-blue-300 font-semibold">I believe…</label>
            <div className="relative mt-1">
              <input
                id="home-belief"
                value={text}
                onChange={(e) => setText(e.target.value)}
                maxLength={1000}
                className="w-full bg-transparent text-xl font-semibold text-white focus:outline-none py-1.5"
                autoComplete="off"
              />
              {!text && (
                <div className="pointer-events-none absolute inset-0 flex items-center text-xl font-semibold text-slate-500 overflow-hidden">
                  <AnimatePresence mode="wait">
                    <motion.span key={i} initial={{ y: 14, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -14, opacity: 0 }} transition={{ duration: 0.3 }} className="truncate">
                      {ROTATE[i]}
                    </motion.span>
                  </AnimatePresence>
                </div>
              )}
            </div>
            <button type="submit" className="mt-3 w-full rounded-2xl bg-blue-600 hover:bg-blue-500 active:scale-[0.99] transition py-3.5 font-bold flex items-center justify-center gap-2">
              Show me how to trade it <ArrowRight className="w-4 h-4" aria-hidden />
            </button>
          </div>
        </form>

        {/* Hot themes */}
        {hot.length > 0 && (
          <div className="mt-6">
            <div className="flex items-center justify-between">
              <div className="text-xs uppercase tracking-wider text-slate-400 font-semibold">🔥 Hot right now</div>
              <button onClick={() => navigate('/trending')} className="text-xs text-blue-300">See all</button>
            </div>
            <div className="mt-2 flex gap-2 overflow-x-auto pb-1 -mx-4 px-4 snap-x">
              {hot.map((t) => (
                <button key={t.theme} onClick={() => go(t.example || `${t.theme} demand will grow`)}
                  className="snap-start shrink-0 w-44 text-left rounded-2xl border border-slate-700/70 bg-slate-900/70 p-3 hover:border-blue-400/60">
                  <div className="font-bold truncate">{themeLabel(t.theme)}</div>
                  <div className="text-[11px] text-slate-400">{t.beliefs} belief{t.beliefs === 1 ? '' : 's'} · {t.direction}</div>
                  {t.tickers?.[0] && <div className="mt-1.5 text-xs text-slate-300">Top pick: <span className="font-semibold text-white">{t.tickers[0].ticker}</span></div>}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Recent */}
        {recent.length > 0 && (
          <div className="mt-6">
            <div className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Pick up where you left off</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {recent.slice(0, 3).map((r) => (
                <button key={r} onClick={() => go(r)} className="text-sm px-3 py-2 rounded-full bg-slate-800/80 border border-slate-700 text-slate-200 hover:border-blue-400 max-w-full truncate">↻ {r}</button>
              ))}
            </div>
          </div>
        )}

        {/* Tools */}
        <div className="mt-6 grid grid-cols-2 gap-2.5">
          {TOOLS.map((t, k) => {
            const Icon = t.icon;
            return (
              <motion.button key={t.path} onClick={() => navigate(t.path)}
                initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 * k }}
                className="text-left rounded-3xl border border-slate-700/70 bg-slate-900/70 p-4 hover:border-slate-500 active:scale-[0.98] transition">
                <span className={`w-10 h-10 rounded-2xl flex items-center justify-center ${t.tint}`}><Icon className="w-5 h-5" aria-hidden /></span>
                <span className="block mt-3 font-bold">{t.title}</span>
                <span className="block text-xs text-slate-400 leading-snug">{t.body}</span>
              </motion.button>
            );
          })}
        </div>

        <button onClick={() => navigate('/learning')} className="mt-2.5 w-full text-left rounded-3xl border border-slate-700/70 bg-gradient-to-r from-blue-600/20 to-slate-900/70 p-4 flex items-center gap-3 hover:border-blue-400/50">
          <span className="w-10 h-10 rounded-2xl flex items-center justify-center text-blue-200 bg-blue-400/15"><Brain className="w-5 h-5" aria-hidden /></span>
          <span className="min-w-0">
            <span className="block font-bold">How it learns</span>
            <span className="block text-xs text-slate-400">Every belief from everyone makes the next pick smarter</span>
          </span>
          <ArrowRight className="w-4 h-4 ml-auto text-slate-400 shrink-0" aria-hidden />
        </button>

        <div className="mt-8 flex items-center justify-between text-[11px] text-slate-500">
          <span>For education, not investment advice.</span>
          <button onClick={() => navigate('/generator')} className="underline hover:text-slate-300">Classic generator</button>
        </div>
      </div>
      <BottomNavigation />
    </div>
  );
}
