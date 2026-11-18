# Built for an expert reviewer

Prof. Daniel Brown reviews MarketPlayground in late December / early January. He worked on exotic contracts at
Credit Suisse. Assume he will price-check anything with an option in it. Every agent: hold the app to that bar.

What a derivatives desk will check first (fix or label honestly; never hide):
- **Close Call is a digital option.** Its odds must come from the market (call-spread price = skew included), not a
  single-vol N(d2). Done 2026-11-13: `yesno.digital_from_spread`, flat-vol only as a labelled fallback.
- **Risk-neutral vs real-world.** Option-implied odds are risk-neutral. Say so where they're shown.
- **Replication.** A call spread approximates a digital: partial payoff between strikes, wider strikes = blurrier
  line. Show strikes and the in-between zone (already on the screen).
- **Costs and fills.** Practice prices use mid / model vol. Say "before bid/ask costs"; real orders use the
  natural/mid limit (`real_money_order`).
  Done 2026-11-18 (Builder): Close Call shows the listed bid/ask of the same YES/NO spreads beside the practice price
  (`yesno.listed_costs`), the odds needed to break even at the ask, the round-trip cost, and an amber note when the
  quotes are too wide to trade (ask at/above the payout, no bid, or gap over 20% of the payout).
  Done 2026-11-18 (Builder): option idea cards' Price check shows the card's own leg price beside the listed mid and
  bid/ask (`pricecheck.card_vs_listed`), says why they differ (one ATM vol for every strike = no skew; the stock moved
  since the card was priced; strike not listed), and totals the whole trade: card / listed mids / natural.
  Done 2026-11-18 (Builder): live idea cards price each strike at its own listed implied vol
  (`strategy.price_at_strike_vols`, OTM side per strike: puts below spot, calls at/above; all legs or none, within
  1% strike / 3 days expiry / half-to-twice the ATM vol), and premiums, max loss/gain, breakevens and Greeks follow.
  Checked first: grading never read card premiums (`grader` re-marks every pick at the stock's realized vol), so this
  is display pricing only. Cards without a full set of listed strikes keep one ATM vol, labelled "one number for
  every strike". Still open: a practice trade opened from a card prices at the AVERAGE of its legs' IVs
  (`practice_options.quote`), so its entry can differ a little from the card.
- **American exercise, dividends, early assignment, pin risk** on short legs of spreads near expiry: mention in the
  options explainer; never claim European payoffs where they aren't.
  Done 2026-11-14 (Builder): every option card has an "Early exercise, assignment and pin risk" panel from
  `library.exercise_notes` (per short leg: who can assign, when, what covers it; pin risk; auto-exercise; prices
  assume no dividends).
- **Statistics.** Out-of-sample only, embargoed, risk-matched; overlapping 90-day windows inflate t-stats (see the
  Newey-West proposal in feature_ideas.md). Never round a coin-flip into an "edge".
- **Greeks and payoff diagrams** on option ideas must match the numbers on the card (max loss, max gain, breakeven).
  Done 2026-11-14 (Builder): every option card has a "Greeks today" panel (`strategy.position_greeks`: delta in
  shares, gamma, theta $/day, vega $/vol pt, Black-Scholes at the card's own vol and expiry, scaled to the contract
  count); tested against finite differences of the same `bs_price` the card's premiums use.
- Plain words for users, but nothing a professional would call wrong.
