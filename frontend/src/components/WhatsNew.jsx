// "What's new" on the welcome and login screens. Newest first; keep each line short and plain.
// To update: add a line at the top of UPDATES and bump the date.
import React from 'react';

export const UPDATED = 'Nov 21';
export const UPDATES = [
  "New: the Brain page's luck check splits the research into four stretches of time and says whether the #1 pick's lead held in each, not just on average",
  "Fixed: Close Call's odds now include the option smile (skew), checked across many strikes, so they fall steadily as the line rises, even on weekend quotes (SPY Nov 27: $690 had read 55% beside 57% for $695)",
  "Fixed: Close Call reads the odds from a wider spread when the nearest strikes are quoted too loosely to read (SPY's $1 strikes on weekends), so odds no longer rise with the line",
  "Fixed: a Close Call now trades a spread centred on the line, even where the listed strikes are uneven (SPY $700: $695/$705), so YES costs the market's odds, and YES and NO break even at about the same price, between the strikes",
  "New: the Brain page's luck check says whether the strongest research rule picks the same #1 as the app, and how it does where it doesn't",
  "New: option idea cards price each strike at its own implied volatility from listed options, so the skew is in the card's price, max loss and Greeks",
  "New: an option idea's Price check puts the card's own price next to the listed bid/ask for each leg, says why they differ, and totals the whole trade three ways",
  "New: Moving now says when a stock's move came before the news (overnight and weekend stories), so it isn't read as the reaction",
  "New: Close Call shows the listed bid and ask for the same spreads next to the practice price, and the odds you need to break even at the ask",
  "New: Close Call lists the brain's own daily questions, its odds beside the market's, and marks where it took the other side",
  "New: Moving now shows the S&P 500's move, and each stock's move against it, so a market-wide day isn't read as the story",
  "New: the Brain page's luck check shows whether the #1 pick's lead survives without the few giant wins and losses",
  "New: Close Call answers placed as practice trades show what the trade made or lost, and say when that differs from right or wrong",
  "New: Close Call shows how far the stock could move by that date, and flags when options expect a bigger move than usual",
  'New: Portfolio puts each practice trade next to the same money in the S&P 500 over the same days',
  'New: Closed trades on Portfolio: what you put in, what came back, and the gain; expired options settle at the expiration-day close',
  "New: Close Call keeps your record: how often you picked the right side, next to what the market's odds expected",
  'New: "How sure are you?" on your calls, beside how often similar calls came true; later, a score of how well your confidence matched',
  'New: "I\'m wrong if...": write your own test for a call, then mark whether it happened',
  'New: Close Call. Yes or no: will a stock close above a price by a date? Real option odds, the brain\'s lean, fixed-risk practice trades',
  'New: Price check on option ideas: cheap or expensive vs how much the stock moves',
  'New: a confidence badge on the #1 pick, checked on past calls the AI never saw',
  'New: MuLine, our own trend line, on every pick: uptrend or downtrend at a glance',
  "Market's open alerts: the day's top story at 9:35 am ET",
  'Live forward test on the Brain page: real-time calls only, no hindsight',
  'Watch any news story in 30 seconds with Story mode',
  'AI strategists compete daily: only the strong survive',
  'An honest scorecard on the brain page, real numbers only',
  'The brain now learns from 90-day results, not 30',
  'Log in with Face ID',
  'Practice options trades, priced live',
];

export default function WhatsNew({ max = 4, className = '' }) {
  return (
    <div className={`rounded-2xl border border-slate-700/70 bg-slate-900/70 px-4 py-3 text-left ${className}`}>
      <div className="flex items-center justify-between">
        <div className="text-[11px] font-bold uppercase tracking-wider text-blue-300">What's new</div>
        <div className="text-[11px] text-slate-500">Updated {UPDATED}</div>
      </div>
      <ul className="mt-2 space-y-1.5">
        {UPDATES.slice(0, max).map((u) => (
          <li key={u} className="flex gap-2 text-sm text-slate-200">
            <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-blue-400" />
            <span>{u}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
