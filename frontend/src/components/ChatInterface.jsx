// MarketPlayground chat: type (or say) a belief, get trade ideas that express it.
import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useLocation } from 'react-router-dom';

import { API_BASE, processBelief } from '../lib/api';
import BottomNavigation from './BottomNavigation';
import { PortfolioModal } from './PortfolioComponents';
import TickerStrip from './chat/TickerStrip';
import StrategyCard from './chat/StrategyCard';

const EXAMPLES = [
  'Plumbing demand is about to boom',
  'Potatoes are in demand',
  'Air travel slows down next year',
  'Everyone is getting a pet',
  'AI chip demand keeps growing',
  'People are eating out less',
];

const RISK = [
  { id: 'conservative', label: 'Careful' },
  { id: 'moderate', label: 'Balanced' },
  { id: 'aggressive', label: 'Bold' },
];

const STAGES = ['Reading your belief', 'Finding who it affects', 'Checking live prices', 'Building strategies'];

function loadRisk() {
  try { return localStorage.getItem('mp_risk') || 'moderate'; } catch { return 'moderate'; }
}

export default function ChatInterface() {
  const location = useLocation();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState(0);
  const [risk, setRisk] = useState(loadRisk);
  const [showPortfolio, setShowPortfolio] = useState(false);
  const [listening, setListening] = useState(false);
  const endRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => { try { localStorage.setItem('mp_risk', risk); } catch { /* private mode */ } }, [risk]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [messages, loading]);

  // Prefill from a link like /chat?b=potatoes%20are%20in%20demand (Trending page uses this)
  useEffect(() => {
    const b = new URLSearchParams(location.search).get('b');
    if (b) { setInput(b); inputRef.current?.focus(); }
  }, [location.search]);

  useEffect(() => {
    if (!loading) return undefined;
    setStage(0);
    const id = setInterval(() => setStage((s) => Math.min(s + 1, STAGES.length - 1)), 2200);
    return () => clearInterval(id);
  }, [loading]);

  const send = async (text) => {
    const belief = (text ?? input).trim();
    if (!belief || loading) return;
    setInput('');
    setMessages((m) => [...m, { id: Date.now(), role: 'user', text: belief }]);
    setLoading(true);
    try {
      const data = await processBelief(belief, { riskProfile: risk });
      if (!data?.strategy || !data?.picks?.length) {
        setMessages((m) => [...m, { id: Date.now() + 1, role: 'ai', text: data?.reason || "I couldn't turn that into a trade idea. Try saying what you think will grow, shrink, or change." }]);
      } else {
        setMessages((m) => [...m, { id: Date.now() + 1, role: 'ai', text: "Here's how you could trade that.", data, belief }]);
      }
    } catch (e) {
      const offline = e instanceof TypeError; // fetch network failure
      setMessages((m) => [...m, {
        id: Date.now() + 1, role: 'error',
        text: offline ? `Can't reach the MarketPlayground server (${API_BASE}). Check your connection and try again.` : e.message,
        retry: belief,
      }]);
    } finally {
      setLoading(false);
    }
  };

  const speak = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      setMessages((m) => [...m, { id: Date.now(), role: 'ai', text: "Voice input isn't supported in this browser. Try Chrome or Safari." }]);
      return;
    }
    const rec = new SR();
    rec.lang = 'en-US';
    rec.interimResults = false;
    rec.onresult = (ev) => setInput(ev.results[0][0].transcript);
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    setListening(true);
    rec.start();
  };

  const empty = messages.length === 0;

  return (
    <div className="h-screen flex flex-col bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-white">
      <div className="shrink-0" style={{ paddingTop: 'env(safe-area-inset-top)' }}>
        <TickerStrip />
        <header className="px-4 py-3 border-b border-slate-800 bg-slate-900/80 backdrop-blur flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center font-black">M</div>
          <div className="min-w-0">
            <h1 className="font-bold leading-tight truncate">MarketPlayground</h1>
            <p className="text-[11px] text-blue-300 truncate">Your belief. The right strategy.</p>
          </div>
          <div className="ml-auto flex rounded-lg bg-slate-800 p-0.5" role="radiogroup" aria-label="Risk level">
            {RISK.map((r) => (
              <button
                key={r.id}
                role="radio"
                aria-checked={risk === r.id}
                onClick={() => setRisk(r.id)}
                className={`px-2 py-1 text-[11px] font-semibold rounded-md ${risk === r.id ? 'bg-blue-600 text-white' : 'text-slate-300'}`}
              >
                {r.label}
              </button>
            ))}
          </div>
        </header>
      </div>

      <main className="flex-1 overflow-y-auto px-4 pt-4 pb-40" style={{ WebkitOverflowScrolling: 'touch' }}>
        {empty && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="max-w-lg mx-auto pt-4">
            <h2 className="text-2xl font-extrabold leading-tight">What do you believe about the world?</h2>
            <p className="mt-2 text-slate-300">
              Type it in your own words. A hunch is enough. You'll get the companies and funds it affects and a strategy for each.
            </p>
            <div className="mt-5 text-xs uppercase tracking-wider text-slate-500">Try one</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  onClick={() => send(ex)}
                  className="text-sm px-3 py-2 rounded-full bg-slate-800 border border-slate-700 text-slate-200 hover:border-blue-400 hover:text-white"
                >
                  {ex}
                </button>
              ))}
            </div>
          </motion.div>
        )}

        <div className="max-w-lg mx-auto space-y-4">
          <AnimatePresence initial={false}>
            {messages.map((m) => (
              <motion.div key={m.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
                {m.role === 'user' ? (
                  <div className="flex justify-end">
                    <div className="max-w-[85%] rounded-2xl rounded-br-md bg-blue-600 px-4 py-3 text-sm">{m.text}</div>
                  </div>
                ) : m.role === 'error' ? (
                  <div className="rounded-2xl border border-red-500/40 bg-red-950/40 px-4 py-3 text-sm text-red-200">
                    {m.text}
                    {m.retry && (
                      <button onClick={() => send(m.retry)} className="block mt-2 text-xs font-semibold text-white underline">Try again</button>
                    )}
                  </div>
                ) : (
                  <div>
                    <div className="max-w-[85%] rounded-2xl rounded-bl-md bg-slate-800 border border-slate-700 px-4 py-3 text-sm text-slate-100">{m.text}</div>
                    {m.data && <StrategyCard data={m.data} belief={m.belief} />}
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>

          {loading && (
            <div className="rounded-2xl rounded-bl-md bg-slate-800 border border-slate-700 px-4 py-3 text-sm text-slate-300 inline-flex items-center gap-3" role="status">
              <span className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <motion.span key={i} className="w-2 h-2 rounded-full bg-blue-400" animate={{ y: [0, -5, 0] }} transition={{ repeat: Infinity, duration: 0.8, delay: i * 0.15 }} />
                ))}
              </span>
              {STAGES[stage]}…
            </div>
          )}
          <div ref={endRef} />
        </div>
      </main>

      <div className="fixed left-0 right-0 bottom-16 z-30 px-3" style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}>
        <form
          onSubmit={(e) => { e.preventDefault(); send(); }}
          className="max-w-lg mx-auto flex items-center gap-2 bg-slate-800/95 backdrop-blur border border-slate-700 rounded-full px-3 py-2 shadow-xl"
        >
          <button
            type="button"
            onClick={speak}
            aria-label={listening ? 'Listening' : 'Speak your belief'}
            className={`w-9 h-9 rounded-full flex items-center justify-center ${listening ? 'bg-red-500 animate-pulse' : 'bg-slate-700 hover:bg-slate-600'}`}
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
              <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
            </svg>
          </button>
          <label htmlFor="belief-input" className="sr-only">Your belief</label>
          <input
            id="belief-input"
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="What do you believe?"
            maxLength={1000}
            className="flex-1 min-w-0 bg-transparent text-base text-white placeholder-slate-400 focus:outline-none"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={!input.trim() || loading}
            aria-label="Send"
            className="w-9 h-9 rounded-full flex items-center justify-center bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500"
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" /></svg>
          </button>
        </form>
      </div>

      {showPortfolio && <PortfolioModal isOpen={showPortfolio} onClose={() => setShowPortfolio(false)} BACKEND_URL={API_BASE} />}
      <BottomNavigation onPortfolioClick={() => setShowPortfolio(true)} />
    </div>
  );
}
