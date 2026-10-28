// Basket builder: describe a goal in plain words, get a simple mix of funds.
import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { generateBasket } from './lib/api';
import BottomNavigation from './components/BottomNavigation';

const EXAMPLES = [
  '70% stocks and 30% bonds for moderate growth',
  'Something safe for a house down payment in 3 years',
  'Aggressive growth with a tilt to AI and chips',
  'Income from dividends with low ups and downs',
];

const COLORS = ['#3b82f6', '#60a5fa', '#22c55e', '#f59e0b', '#a78bfa', '#f472b6'];

function Donut({ items }) {
  const R = 52, C = 2 * Math.PI * R;
  let offset = 0;
  return (
    <svg viewBox="0 0 140 140" className="w-32 h-32 shrink-0" role="img" aria-label="Allocation chart">
      <circle cx="70" cy="70" r={R} fill="none" stroke="#1e293b" strokeWidth="20" />
      {items.map((it, i) => {
        const pct = parseFloat(it.allocation) || 0;
        const len = (pct / 100) * C;
        const el = (
          <circle key={it.ticker} cx="70" cy="70" r={R} fill="none" stroke={COLORS[i % COLORS.length]} strokeWidth="20"
            strokeDasharray={`${len} ${C - len}`} strokeDashoffset={-offset} transform="rotate(-90 70 70)" />
        );
        offset += len;
        return el;
      })}
    </svg>
  );
}

export default function BasketBuilderPage() {
  const [goal, setGoal] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [listening, setListening] = useState(false);

  const submit = async (text) => {
    const g = (text ?? goal).trim();
    if (!g) { setError('Describe your goal first.'); return; }
    setGoal(g); setError(null); setLoading(true); setResult(null);
    try {
      setResult(await generateBasket(g));
    } catch (e) {
      setError(e instanceof TypeError ? "Can't reach the MarketPlayground server. Try again in a moment." : e.message);
    } finally {
      setLoading(false);
    }
  };

  const speak = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { setError("Voice input isn't supported in this browser."); return; }
    const rec = new SR();
    rec.lang = 'en-US';
    rec.onresult = (e) => setGoal(e.results[0][0].transcript);
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    setListening(true);
    rec.start();
  };

  const items = result?.basket || [];

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-white pb-28">
      <div className="max-w-lg mx-auto px-4" style={{ paddingTop: 'max(2rem, env(safe-area-inset-top))' }}>
        <h1 className="text-3xl font-extrabold">Build a basket</h1>
        <p className="mt-1 text-slate-300">Describe what you want your money to do. You'll get a simple mix of funds.</p>

        <label htmlFor="goal" className="sr-only">Your goal</label>
        <textarea
          id="goal" rows={3} value={goal} onChange={(e) => { setGoal(e.target.value); setError(null); }}
          placeholder="e.g. 70% stocks and 30% bonds for moderate growth"
          className="mt-5 w-full p-4 rounded-xl bg-slate-900 text-white border border-slate-700 focus:border-blue-500 focus:outline-none"
        />
        {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
        <div className="mt-3 flex gap-2">
          <button onClick={speak} className={`px-4 py-3 rounded-xl text-sm font-semibold ${listening ? 'bg-red-600' : 'bg-slate-800 border border-slate-700'}`}>
            {listening ? 'Listening…' : 'Speak'}
          </button>
          <button onClick={() => submit()} disabled={loading} className="flex-1 px-4 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 font-bold disabled:opacity-60">
            {loading ? 'Building…' : 'Build my basket'}
          </button>
        </div>

        {!result && !loading && (
          <div className="mt-6">
            <div className="text-xs uppercase tracking-wider text-slate-500">Try one</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {EXAMPLES.map((ex) => (
                <button key={ex} onClick={() => submit(ex)} className="text-sm px-3 py-2 rounded-full bg-slate-800 border border-slate-700 text-slate-200 hover:border-blue-400">
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        {items.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mt-6 rounded-2xl border border-slate-700 bg-slate-900 p-4">
            <div className="flex items-center gap-4">
              <Donut items={items} />
              <div className="min-w-0">
                <div className="text-xs uppercase tracking-wider text-slate-500">Goal</div>
                <div className="font-semibold">{result.goal}</div>
                <div className="mt-2 text-xs uppercase tracking-wider text-slate-500">Risk</div>
                <div className="font-semibold capitalize">{result.risk_profile}</div>
              </div>
            </div>
            <ul className="mt-4 space-y-2">
              {items.map((it, i) => (
                <li key={it.ticker} className="flex items-start gap-3 rounded-xl bg-slate-800/70 p-3">
                  <span className="mt-1.5 w-3 h-3 rounded-full shrink-0" style={{ background: COLORS[i % COLORS.length] }} />
                  <div className="min-w-0 flex-1">
                    <div className="flex justify-between gap-2">
                      <span className="font-bold">{it.ticker} <span className="text-xs font-normal text-slate-400">{it.type}</span></span>
                      <span className="font-bold text-blue-300">{it.allocation}</span>
                    </div>
                    <p className="text-sm text-slate-400">{it.rationale}</p>
                  </div>
                </li>
              ))}
            </ul>
            {result.estimated_return && <p className="mt-3 text-xs text-slate-400 leading-relaxed">{result.estimated_return}</p>}
          </motion.div>
        )}

        <p className="mt-6 text-[11px] text-slate-500">For education, not investment advice. Check each fund's fees and details before investing.</p>
      </div>
      <BottomNavigation />
    </div>
  );
}
