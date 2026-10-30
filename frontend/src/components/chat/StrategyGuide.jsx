// "How do you want to trade this?" — guides people to the right kind of strategy.
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { INSTRUMENTS, GOALS, getPrefs, setPrefs, prefsLabel } from '../../lib/prefs';

export default function StrategyGuide({ current, onTune }) {
  const saved = getPrefs();
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState('instrument');
  const choose = (p) => { setPrefs(p); setOpen(false); setStep('instrument'); onTune?.(p); };

  return (
    <div className={`rounded-2xl border p-3 ${open ? 'border-blue-400/50 bg-blue-500/10' : 'border-slate-700 bg-slate-800/40'}`}>
      {!open ? (
        <div className="flex items-center justify-between gap-2 text-sm">
          <span className="text-slate-300">Strategy: <span className="font-semibold text-white">{prefsLabel(current || saved)}</span></span>
          <button onClick={() => setOpen(true)} className="text-xs font-semibold text-blue-300 hover:text-blue-200">Change</button>
        </div>
      ) : (
        <AnimatePresence mode="wait">
          {step === 'instrument' ? (
            <motion.div key="i" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
              <div className="text-sm font-bold text-white">Quick question: how do you want to trade this?</div>
              <div className="mt-2 grid gap-2">
                {INSTRUMENTS.map((o) => (
                  <button key={o.id} onClick={() => (o.id === 'options' ? setStep('goal') : choose({ instrument: o.id, goal: '' }))}
                    className="text-left rounded-xl bg-slate-900/80 border border-slate-700 hover:border-blue-400 px-3 py-2">
                    <div className="text-sm font-semibold text-white">{o.label}</div>
                    <div className="text-[11px] text-slate-400">{o.hint}</div>
                  </button>
                ))}
              </div>
              {saved && <button onClick={() => setOpen(false)} className="mt-2 text-xs text-slate-400">Keep {prefsLabel(saved).toLowerCase()}</button>}
            </motion.div>
          ) : (
            <motion.div key="g" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
              <div className="text-sm font-bold text-white">With options, what matters most to you?</div>
              <div className="mt-2 grid grid-cols-2 gap-2">
                {GOALS.map((g) => (
                  <button key={g.id} onClick={() => choose({ instrument: 'options', goal: g.id })}
                    className="text-left rounded-xl bg-slate-900/80 border border-slate-700 hover:border-blue-400 px-3 py-2">
                    <div className="text-sm font-semibold text-white">{g.label}</div>
                    <div className="text-[11px] text-slate-400 leading-snug">{g.hint}</div>
                  </button>
                ))}
              </div>
              <button onClick={() => choose({ instrument: 'options', goal: '' })} className="mt-2 text-xs text-blue-300">Any options strategy is fine</button>
              <button onClick={() => setStep('instrument')} className="mt-2 ml-4 text-xs text-slate-400">Back</button>
            </motion.div>
          )}
        </AnimatePresence>
      )}
    </div>
  );
}
