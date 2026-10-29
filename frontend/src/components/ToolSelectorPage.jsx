// Home: start with a belief, see what's hot, jump to your calls and tools.
import { LogoMark, Wordmark } from './ui/Logo';
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Flame, ShoppingBasket, TrendingUp, ArrowRight, Target } from 'lucide-react';
import BottomNavigation from './BottomNavigation';
import { getTrending } from '../lib/api';
import { recentBeliefs } from '../lib/recent';
import { themeLabel } from '../lib/text';
import { useMovers, believeUrl } from './MoversFeed';
import { useAccount, initials } from '../lib/auth';

const ROTATE = [
  'plumbing demand is about to boom',
  'potatoes are in demand',
  'everyone is getting a pet',
  'air travel slows down next year',
  'AI needs way more electricity',
  'people are eating out less',
];

const TOOLS = [
  { path: '/trending', icon: Flame, title: 'Trending', body: 'Today’s news, as hunches', tint: 'text-amber-300 bg-amber-400/10' },
  { path: '/my', icon: Target, title: 'My calls', body: 'How your picks are doing', tint: 'text-blue-300 bg-blue-400/10' },
  { path: '/basket-builder', icon: ShoppingBasket, title: 'Baskets', body: 'A goal → a simple fund mix', tint: 'text-sky-300 bg-sky-400/10' },
  { path: '/portfolio', icon: TrendingUp, title: 'Practice', body: 'Paper trades, no real money', tint: 'text-green-300 bg-green-400/10' },
];

export default function ToolSelectorPage() {
  const navigate = useNavigate();
  const [text, setText] = useState('');
  const [i, setI] = useState(0);
  const [hot, setHot] = useState([]);
  const moving = useMovers().data?.items || [];
  const recent = recentBeliefs();
  const acc = useAccount();

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
            <LogoMark size={36} />
            <div>
              <div className="leading-tight"><Wordmark /></div>
              <div className="text-[10px] font-bold tracking-wider uppercase text-blue-300">Free beta</div>
            </div>
          </div>
          {acc ? (
            <button onClick={() => navigate('/account')} aria-label="Your account" className="w-10 h-10 rounded-2xl bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center font-extrabold shadow-lg shadow-blue-700/30">
              {initials(acc)}
            </button>
          ) : (
            <button onClick={() => navigate('/account?mode=login')} className="text-sm font-bold text-white bg-slate-800/80 border border-slate-600 rounded-full px-4 py-2 hover:border-blue-400">
              Log in
            </button>
          )}
        </div>

        <h1 className="mt-8 text-[2.6rem] leading-[1.05] font-extrabold tracking-tight">
          Your hunch.<br /><span className="mp-gradient-text">Real stocks.</span>
        </h1>
        <p className="mt-3 text-slate-300">Type what you think will happen. We find the companies it affects and show you which shares to buy. Options are there too, if you want them.</p>

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

        {/* Moving now: today's news as hunches */}
        {moving.length > 0 && (
          <div className="mt-6">
            <div className="flex items-center justify-between">
              <div className="text-xs uppercase tracking-wider text-slate-400 font-semibold">📰 Moving now</div>
              <button onClick={() => navigate('/trending')} className="text-xs text-blue-300">See all</button>
            </div>
            <div className="mt-2 flex gap-2 overflow-x-auto pb-1 -mx-4 px-4 snap-x">
              {moving.slice(0, 5).map((m) => (
                <button key={m.headline} onClick={() => navigate(believeUrl(m.hunch))}
                  className="snap-start shrink-0 w-60 text-left rounded-2xl border border-slate-700/70 bg-slate-900/70 p-3 hover:border-blue-400/60">
                  <div className="font-bold leading-snug line-clamp-2">{m.hunch}</div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {m.companies.slice(0, 3).map((c) => (
                      <span key={c.ticker} className="text-[11px] rounded-md bg-slate-800 px-1.5 py-0.5">
                        <span className="font-bold text-white">{c.ticker}</span>
                        {c.change != null && <span className={c.change >= 0 ? 'text-green-400' : 'text-red-400'}> {c.change >= 0 ? '+' : ''}{(c.change * 100).toFixed(1)}%</span>}
                      </span>
                    ))}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

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



        <div className="mt-8 flex items-center justify-between text-[11px] text-slate-500">
          <span>For education, not investment advice. MarketPlayground is a MuLabs product.</span>
        </div>
      </div>
      <BottomNavigation />
    </div>
  );
}
