// MarketPlayground chat: type (or say) a belief, get trade ideas that express it.
import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useLocation } from 'react-router-dom';

import { processBelief, getHeadlines } from '../lib/api';
import BottomNavigation from './BottomNavigation';
import TickerStrip from './chat/TickerStrip';
import StrategyCard from './chat/StrategyCard';
import Term from './ui/Term';
import { recentBeliefs, rememberBelief, seen, markSeen } from '../lib/recent';
import { getPrefs } from '../lib/prefs';

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
const MORE_LESS = ['more', 'less'];
const WHEN = [['next few months', 'over the next few months'], ['next year', 'over the next year'], ['next 5 years', 'over the next five years']];
const THINGS = ['electric cars', 'pet food', 'air travel', 'home repairs', 'AI chips', 'streaming', 'fast food', 'solar panels'];

function Builder({ onGo }) {
  const [ml, setMl] = useState('more');
  const [thing, setThing] = useState('');
  const [when, setWhen] = useState(WHEN[1]);
  const go = () => thing.trim() && onGo(`People will buy ${ml} ${thing.trim()} ${when[1]}`);
  return (
    <div className="mt-5 rounded-3xl border border-slate-700/80 bg-slate-900/70 p-4">
      <div className="text-xs uppercase tracking-wider text-blue-300 font-semibold">Not sure how to say it? Build one</div>
      <div className="mt-3 text-lg font-semibold leading-relaxed text-white">
        People will buy{' '}
        <span className="inline-flex rounded-xl bg-slate-800 p-0.5 align-middle">
          {MORE_LESS.map((o) => (
            <button key={o} onClick={() => setMl(o)} className={`px-2.5 py-0.5 rounded-lg text-sm font-bold ${ml === o ? 'bg-blue-600 text-white' : 'text-slate-300'}`}>{o}</button>
          ))}
        </span>{' '}
        <input value={thing} onChange={(e) => setThing(e.target.value)} placeholder="what?" maxLength={60} aria-label="What will people buy?"
          onKeyDown={(e) => e.key === 'Enter' && go()}
          className="w-36 bg-transparent border-b-2 border-blue-400/60 focus:border-blue-300 focus:outline-none text-white placeholder-slate-500 px-1" />
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {THINGS.map((t) => <button key={t} onClick={() => setThing(t)} className="text-xs px-2.5 py-1 rounded-full bg-slate-800 border border-slate-700 text-slate-300 hover:border-blue-400">{t}</button>)}
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {WHEN.map((w) => (
          <button key={w[0]} onClick={() => setWhen(w)} className={`text-xs px-2.5 py-1 rounded-full border ${when[0] === w[0] ? 'bg-blue-600 border-blue-400 text-white' : 'bg-slate-800 border-slate-700 text-slate-300'}`}>{w[0]}</button>
        ))}
      </div>
      <button onClick={go} disabled={!thing.trim()} className="mt-4 w-full rounded-2xl bg-blue-600 hover:bg-blue-500 disabled:opacity-40 py-3 font-bold">Show me how to trade it</button>
    </div>
  );
}

const RISK_LABEL = { conservative: 'Careful', moderate: 'Balanced', aggressive: 'Bold' };

const HOW = [
  ['💭', 'Say what you believe', 'Any hunch about the world. "Pet adoptions keep rising" works.'],
  ['🔎', 'We find who it affects', 'Companies and funds tied to it, checked against live prices.'],
  ['📈', 'Pick a way to trade it', 'Shares or options, sized to your budget, with a chart you can drag.'],
];

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
  const [listening, setListening] = useState(false);
  const [recent, setRecent] = useState(recentBeliefs);
  const [showHow, setShowHow] = useState(() => !seen('how'));
  const autoSent = useRef(false);
  const [news, setNews] = useState([]);
  useEffect(() => { getHeadlines(4).then((d) => setNews(d?.headlines || [])).catch(() => {}); }, []);
  const endRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => { try { localStorage.setItem('mp_risk', risk); } catch { /* private mode */ } }, [risk]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [messages, loading]);

  // Prefill from a link like /chat?b=potatoes%20are%20in%20demand (Trending page uses this)
  useEffect(() => {
    const q = new URLSearchParams(location.search);
    const b = q.get('b');
    if (!b) return;
    if (q.get('go') === '1') { if (!autoSent.current) { autoSent.current = true; send(b); } return; }
    setInput(b); inputRef.current?.focus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search]);

  useEffect(() => {
    if (!loading) return undefined;
    setStage(0);
    const id = setInterval(() => setStage((s) => Math.min(s + 1, STAGES.length - 1)), 2200);
    return () => clearInterval(id);
  }, [loading]);

  const send = async (text, riskOverride, prefsOverride) => {
    const belief = (text ?? input).trim();
    if (!belief || loading) return;
    const useRisk = riskOverride || risk;
    const usePrefs = prefsOverride || getPrefs();
    setInput('');
    if (showHow) { setShowHow(false); markSeen('how'); }
    rememberBelief(belief);
    setRecent(recentBeliefs());
    setMessages((m) => [...m, { id: Date.now(), role: 'user', text: belief, risk: riskOverride ? useRisk : null }]);
    setLoading(true);
    try {
      const data = await processBelief(belief, { riskProfile: useRisk, prefs: usePrefs });
      if (!data?.strategy || !data?.picks?.length) {
        setMessages((m) => [...m, { id: Date.now() + 1, role: 'ai', suggest: true, text: data?.reason || "I couldn't turn that into a trade idea. Try saying what you think will grow, shrink, or change." }]);
      } else {
        setMessages((m) => [...m, {
          id: Date.now() + 1, role: 'ai', data, belief, risk: useRisk, prefs: usePrefs,
          text: prefsOverride ? "Here it is with the strategy you picked." : riskOverride ? `Here's a ${RISK_LABEL[useRisk].toLowerCase()} version.` : "Here's how you could trade that.",
        }]);
      }
    } catch (e) {
      const offline = e instanceof TypeError; // fetch network failure
      setMessages((m) => [...m, {
        id: Date.now() + 1, role: 'error',
        text: offline ? "Can't reach MarketPlayground right now. Check your connection and try again." : e.message,
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
    <div className="h-screen flex flex-col mp-bg text-white">
      <div className="shrink-0" style={{ paddingTop: 'env(safe-area-inset-top)' }}>
        <TickerStrip />
        <header className="px-4 py-3 border-b border-slate-800 bg-slate-900/80 backdrop-blur flex items-center gap-3">
          <a href="/select-tool" aria-label="Home" className="w-9 h-9 shrink-0 rounded-xl bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center font-black">M</a>
          <div className="min-w-0">
            <h1 className="font-bold leading-tight truncate">Believe</h1>
            <p className="text-[11px] text-blue-300 truncate">MarketPlayground</p>
          </div>
          <span className="ml-auto text-[11px] text-slate-400 hidden min-[380px]:inline"><Term k="risk level">Risk</Term></span>
          <div className="flex rounded-lg bg-slate-800 p-0.5" role="radiogroup" aria-label="Risk level">
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
            {showHow && (
              <div className="mt-5 rounded-3xl border border-slate-700/80 bg-slate-900/70 p-4">
                <div className="flex items-center justify-between">
                  <div className="text-xs uppercase tracking-wider text-blue-300 font-semibold">How it works</div>
                  <button onClick={() => { setShowHow(false); markSeen('how'); }} className="text-xs text-slate-400 hover:text-white">Got it</button>
                </div>
                <ol className="mt-3 space-y-3">
                  {HOW.map(([icon, title, body], i) => (
                    <li key={title} className="flex gap-3">
                      <span className="w-9 h-9 shrink-0 rounded-2xl bg-slate-800 flex items-center justify-center text-lg" aria-hidden>{icon}</span>
                      <span>
                        <span className="block font-semibold text-white text-sm">{i + 1}. {title}</span>
                        <span className="block text-xs text-slate-400 leading-relaxed">{body}</span>
                      </span>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {recent.length > 0 && (
              <>
                <div className="mt-6 text-xs uppercase tracking-wider text-slate-500">Your recent beliefs</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {recent.map((r) => (
                    <button key={r} onClick={() => send(r)} className="text-sm px-3 py-2 rounded-full bg-blue-500/10 border border-blue-400/30 text-blue-100 hover:border-blue-300 max-w-full truncate">
                      ↻ {r}
                    </button>
                  ))}
                </div>
              </>
            )}

            {news.length > 0 && (
              <>
                <div className="mt-6 text-xs uppercase tracking-wider text-slate-500">📰 In the news: what do you believe?</div>
                <div className="mt-2 space-y-2">
                  {news.map((n) => (
                    <button key={n.headline} onClick={() => { setInput(`${n.headline}. I think this means `); inputRef.current?.focus(); }}
                      className="w-full text-left rounded-2xl bg-slate-900/70 border border-slate-700/80 px-3.5 py-2.5 hover:border-blue-400/60">
                      <div className="text-sm text-slate-100 leading-snug">{n.headline}</div>
                      <div className="text-[11px] text-slate-500 mt-0.5">{n.source}{n.symbols?.length ? ` · ${n.symbols.join(', ')}` : ''} · tap to add your take</div>
                    </button>
                  ))}
                </div>
              </>
            )}

            <Builder onGo={(b) => send(b)} />

            <div className="mt-6 text-xs uppercase tracking-wider text-slate-500">Try one</div>
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
                    <div className="max-w-[85%] rounded-2xl rounded-br-md bg-blue-600 px-4 py-3 text-sm">
                      {m.text}
                      {m.risk && <span className="ml-2 text-[10px] font-bold uppercase tracking-wide bg-white/20 rounded-full px-2 py-0.5">{RISK_LABEL[m.risk]}</span>}
                    </div>
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
                    {m.suggest && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {EXAMPLES.slice(0, 3).map((ex) => (
                          <button key={ex} onClick={() => send(ex)} className="text-xs px-3 py-1.5 rounded-full bg-slate-800 border border-slate-700 text-slate-200 hover:border-blue-400">Try: {ex}</button>
                        ))}
                      </div>
                    )}
                    {m.data && (
                      <StrategyCard data={m.data} belief={m.belief} riskProfile={m.risk || risk} onRerun={(r) => send(m.belief, r)} onRefine={(o) => send(`${m.belief} (${o})`, m.risk || undefined)}
                        prefs={m.prefs} onTune={(p) => send(m.belief, m.risk || undefined, p)} />
                    )}
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>

          {loading && (
            <div className="rounded-2xl rounded-bl-md bg-slate-800/90 border border-slate-700 px-4 py-3 text-sm max-w-xs" role="status" aria-live="polite">
              <ul className="space-y-1.5">
                {STAGES.map((label, i) => (
                  <li key={label} className={`flex items-center gap-2.5 ${i < stage ? 'text-slate-400' : i === stage ? 'text-white' : 'text-slate-600'}`}>
                    {i < stage ? (
                      <span className="w-4 h-4 rounded-full bg-green-500/20 text-green-400 text-[10px] flex items-center justify-center">✓</span>
                    ) : i === stage ? (
                      <motion.span className="w-4 h-4 rounded-full border-2 border-blue-400 border-t-transparent" animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 0.8, ease: 'linear' }} />
                    ) : (
                      <span className="w-4 h-4 rounded-full border border-slate-600" />
                    )}
                    {label}
                  </li>
                ))}
              </ul>
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

      <BottomNavigation />
    </div>
  );
}
