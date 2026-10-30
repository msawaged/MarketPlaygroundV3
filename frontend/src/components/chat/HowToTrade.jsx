// Asked before every belief (unless the person chose "remember"): how do you want to trade this?
import React, { useState } from 'react';
import { GOALS } from '../../lib/prefs';

const CHOICES = [
  { id: 'shares', icon: '📈', title: 'Shares', line: 'Own a piece of the company. You gain if it rises, lose if it falls.',
    bits: ['Any amount, even $10', 'No expiration', 'Best when you think something will grow'] },
  { id: 'options', icon: '🎯', title: 'Options', line: 'Bigger payoff for less money, but they expire and can go to zero.',
    bits: ['Win on a rise or a fall', 'Has an end date', 'One contract often costs $100+'] },
  { id: 'auto', icon: '✨', title: 'Let the AI decide', line: 'A mix: shares where they’re simplest, options where they fit better.',
    bits: ['Good if you’re not sure', 'You can switch on each idea'] },
];

export default function HowToTrade({ belief, onPick }) {
  const [remember, setRemember] = useState(false);
  const [goalStep, setGoalStep] = useState(false);
  const pick = (instrument, goal = '') => onPick({ instrument, goal, remember });
  return (
    <div className="rounded-2xl border border-blue-400/40 bg-blue-500/[0.08] p-3.5">
      <div className="text-sm font-bold">How do you want to trade “{belief.length > 60 ? belief.slice(0, 57) + '…' : belief}”?</div>
      {!goalStep ? (
        <div className="mt-2.5 grid gap-2">
          {CHOICES.map((c) => (
            <button key={c.id} onClick={() => (c.id === 'options' ? setGoalStep(true) : pick(c.id))}
              className="text-left rounded-xl bg-slate-900/80 border border-slate-700 hover:border-blue-400 px-3 py-2.5">
              <div className="text-sm font-bold">{c.icon} {c.title}</div>
              <div className="text-xs text-slate-300 mt-0.5">{c.line}</div>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {c.bits.map((b) => <span key={b} className="text-[10px] rounded-full bg-slate-800 border border-slate-700 px-2 py-0.5 text-slate-300">{b}</span>)}
              </div>
            </button>
          ))}
        </div>
      ) : (
        <div className="mt-2.5">
          <div className="text-xs text-slate-300">With options, what matters most?</div>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {GOALS.map((g) => (
              <button key={g.id} onClick={() => pick('options', g.id)}
                className="text-left rounded-xl bg-slate-900/80 border border-slate-700 hover:border-blue-400 px-3 py-2">
                <div className="text-sm font-semibold">{g.label}</div>
                <div className="text-[11px] text-slate-400 leading-snug">{g.hint}</div>
              </button>
            ))}
          </div>
          <div className="mt-2 flex gap-4">
            <button onClick={() => pick('options')} className="text-xs font-semibold text-blue-300">Any options strategy</button>
            <button onClick={() => setGoalStep(false)} className="text-xs text-slate-400">Back</button>
          </div>
        </div>
      )}
      <label className="mt-3 flex items-center gap-2 text-xs text-slate-400">
        <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="accent-blue-500" />
        Remember my choice (change it anytime on an idea card)
      </label>
    </div>
  );
}
