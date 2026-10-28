// Tap an underlined word to learn what it means. Plain English, no jargon in the answers.
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export const GLOSSARY = {
  'call': ['Call option', 'The right (not the obligation) to buy 100 shares at a set price before a set date. It gains value when the stock rises.'],
  'put': ['Put option', 'The right to sell 100 shares at a set price before a set date. It gains value when the stock falls.'],
  'strike': ['Strike price', 'The set price in an option. A $230 call lets you buy at $230, even if the stock is at $260.'],
  'expiration': ['Expiration', 'The last day the option exists. After that it is worth whatever the stock price says, or nothing.'],
  'spread': ['Spread', 'Buying one option and selling another at a different strike. It costs less, and caps both the gain and the loss.'],
  'breakeven': ['Breakeven', 'The stock price where you neither make nor lose money (before fees).'],
  'max gain': ['Max gain', 'The most this trade can make. Spreads have a ceiling; owning shares or a lone call does not.'],
  'contract': ['Contract', 'One option contract covers 100 shares, so a $7.50 option costs $750.'],
  'premium': ['Premium', 'The price of an option. You pay it to buy, or receive it when you sell.'],
  'bullish': ['Bullish', 'Expecting the price to go up.'],
  'bearish': ['Bearish', 'Expecting the price to go down.'],
  'paper trade': ['Paper trade', 'A practice trade with pretend money. Real prices, no real risk.'],
  'fit': ['Fit with your belief', "How directly this company or fund is tied to what you believe, according to the AI. It's not a prediction of returns."],
  'track record': ['Track record', 'How past picks for similar beliefs actually did against the S&P 500, graded automatically after 30 days.'],
  'vs s&p': ['vs S&P 500', 'How much better or worse a pick did than simply owning the S&P 500, in the direction the belief expected.'],
  'risk level': ['Careful · Balanced · Bold', 'Careful leans on shares, funds and capped-risk trades. Balanced mixes shares and spreads. Bold allows options that can move a lot, both ways. You can switch any time, or tap Safer/Bolder on a result.'],
  'straddle': ['Straddle', 'Buying a call and a put at the same strike. It pays when the stock makes a big move in either direction, and loses when it sits still.'],
  'strangle': ['Strangle', 'Like a straddle, but the call is above and the put below today\'s price. It costs less, and needs a bigger move to pay off.'],
  'big move': ['Big move', 'You expect a large swing but not which way: think a make-or-break earnings report or a court ruling.'],
  'covered call': ['Covered call', 'You own 100 shares and sell someone the right to buy them at a higher price. You get paid now; if the stock shoots past that price, your shares get sold there.'],
  'cash-secured put': ['Cash-secured put', 'You get paid now for agreeing to buy 100 shares at a lower price. The cash to buy them is set aside. If the stock stays up, you just keep the payment.'],
  'protective put': ['Protective put', 'Insurance for shares you own: a put lets you sell at a set price, so your loss has a floor.'],
  'collar': ['Collar', 'Shares plus a put below (your floor) and a call sold above (your ceiling). The call pays for most of the insurance.'],
  'bull put spread': ['Bull put spread', 'Sell a put and buy a lower one. You collect cash up front and keep it if the stock stays above your strike. Risk is capped.'],
  'bear call spread': ['Bear call spread', 'Sell a call and buy a higher one. You collect cash up front and keep it if the stock stays below your strike. Risk is capped.'],
  'iron butterfly': ['Iron butterfly', 'Like an iron condor, but betting the stock ends very close to today\'s price. Pays more, wins in a narrower range.'],
  'long call butterfly': ['Call butterfly', 'Three call strikes that pay the most if the stock lands right on your target price at expiration. Cheap, with capped risk.'],
  'long call': ['Long call', 'The right to buy 100 shares at a set price. Big upside if the stock rises; you can lose what you paid.'],
  'long put': ['Long put', 'The right to sell 100 shares at a set price. It pays if the stock falls; you can lose what you paid.'],
  'buy stock': ['Buying shares', 'Owning a piece of the company (or a fund). Simple: you make or lose what the price does.'],
  'iron condor': ['Iron condor', 'Four options that pay you if the stock stays inside a range. You collect money up front; you lose if it breaks out.'],
};

export default function Term({ k, children }) {
  const [open, setOpen] = useState(false);
  const entry = GLOSSARY[k?.toLowerCase()];
  if (!entry) return <>{children}</>;
  return (
    <>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setOpen(true); }}
        className="underline decoration-dotted decoration-blue-400/70 underline-offset-[3px] hover:text-blue-200 cursor-help"
        aria-label={`What does ${entry[0]} mean?`}
      >
        {children}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-0 z-[80] flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm p-3"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={() => setOpen(false)}
            role="dialog" aria-modal="true" aria-label={entry[0]}
          >
            <motion.div
              initial={{ y: 40, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 40, opacity: 0 }}
              transition={{ type: 'spring', damping: 26, stiffness: 320 }}
              className="w-full max-w-md rounded-3xl bg-slate-900 border border-slate-700 p-5 shadow-2xl text-left"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="text-[11px] uppercase tracking-wider text-blue-300 font-semibold">In plain English</div>
              <div className="mt-1 text-xl font-extrabold text-white">{entry[0]}</div>
              <p className="mt-2 text-slate-300 leading-relaxed">{entry[1]}</p>
              <button onClick={() => setOpen(false)} className="mt-5 w-full rounded-2xl bg-blue-600 hover:bg-blue-500 py-3 font-bold text-white">Got it</button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
