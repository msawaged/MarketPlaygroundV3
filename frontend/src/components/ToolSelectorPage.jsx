// Home: pick what you want to do.
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Zap, Flame, ShoppingBasket, TrendingUp } from 'lucide-react';
import BottomNavigation from './BottomNavigation';

const TOOLS = [
  { path: '/chat', icon: Zap, title: 'Trade a belief', body: 'Say what you think will happen. Get 3 ways to trade it.', primary: true },
  { path: '/trending', icon: Flame, title: 'Trending beliefs', body: 'What other people believe right now, and how their picks are doing.' },
  { path: '/basket-builder', icon: ShoppingBasket, title: 'Build a basket', body: 'Describe a goal and get a simple mix of funds.' },
  { path: '/portfolio', icon: TrendingUp, title: 'Practice portfolio', body: 'Your paper trades. No real money.' },
];

export default function ToolSelectorPage() {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-white pb-28">
      <div className="max-w-lg mx-auto px-4" style={{ paddingTop: 'max(2.5rem, env(safe-area-inset-top))' }}>
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center font-black text-lg">M</div>
          <div className="text-sm text-blue-300 font-semibold">MarketPlayground</div>
        </div>
        <h1 className="mt-6 text-4xl font-extrabold leading-tight">Your belief.<br /><span className="text-blue-400">The right strategy.</span></h1>
        <p className="mt-3 text-slate-300">Prediction apps hand you someone else's question. Start with yours.</p>

        <div className="mt-8 space-y-3">
          {TOOLS.map((t, i) => {
            const Icon = t.icon;
            return (
              <motion.button
                key={t.path}
                onClick={() => navigate(t.path)}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className={`w-full text-left rounded-2xl p-4 flex items-start gap-4 border transition-colors ${
                  t.primary ? 'bg-blue-600 border-blue-400 hover:bg-blue-500' : 'bg-slate-900 border-slate-700 hover:border-slate-500'
                }`}
              >
                <span className={`mt-0.5 w-10 h-10 shrink-0 rounded-xl flex items-center justify-center ${t.primary ? 'bg-white/15' : 'bg-slate-800'}`}>
                  <Icon className="w-5 h-5" aria-hidden="true" />
                </span>
                <span className="min-w-0">
                  <span className="block font-bold text-lg">{t.title}</span>
                  <span className={`block text-sm ${t.primary ? 'text-blue-100' : 'text-slate-400'}`}>{t.body}</span>
                </span>
              </motion.button>
            );
          })}
        </div>

        <button onClick={() => navigate('/generator')} className="mt-6 text-xs text-slate-500 hover:text-slate-300 underline">
          Classic strategy generator
        </button>
        <p className="mt-6 text-[11px] text-slate-500 leading-relaxed">
          For education, not investment advice. Trading involves risk, including loss of what you invest.
        </p>
      </div>
      <BottomNavigation />
    </div>
  );
}
