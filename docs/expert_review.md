# Built for an expert reviewer

Prof. Daniel Brown reviews MarketPlayground in late December / early January. He worked on exotic contracts at
Credit Suisse. Assume he will price-check anything with an option in it. Every agent: hold the app to that bar.

What a derivatives desk will check first (fix or label honestly; never hide):
- **Close Call is a digital option.** Its odds must come from the market (call-spread price = skew included), not a
  single-vol N(d2). Done 2026-11-13: `yesno.digital_from_spread`, flat-vol only as a labelled fallback.
- **Risk-neutral vs real-world.** Option-implied odds are risk-neutral. Say so where they're shown.
- **Replication.** A call spread approximates a digital: partial payoff between strikes, wider strikes = blurrier
  line. Show strikes and the in-between zone (already on the screen).
  Done 2026-11-21 (Builder): a line on a listed strike trades the strikes either side of it (NVDA $185 on $2.50
  strikes: $182.50/$187.50, not $185/$187.50, which was a digital at $186.25 priced at 44% beside "50% odds").
  The spread is now the same pair the odds are read from, so YES's price is the odds and both breakevens sit at the line.
  Done 2026-11-21 later (Builder): uneven strike grids too. Live SPY Nov 27 listed $699/$700/$705 (nothing $701-704),
  so the nearest pair for a $700 line was $699/$705 (a digital at $702: YES 41% of payout beside 43% odds). Now it
  takes listed strikes the same distance either side ($695/$705), up to 2x the nearest pair's width; otherwise the
  nearest pair, and the spread note names the close it really bets on (the middle of the strikes).
  Done 2026-11-21 afternoon (Builder): thin $1 strikes. SPY's $695 line read 78% / 51% one $1 step apart (bid/ask
  blurs a $1 spread by ~9 pts), fell back to one-vol 48% beside a skew-included 50% at $700. Now a fine reading that
  is inverted or >10 pts off steps out to the narrowest centred pair whose quotes blur it by <= 3 pts ($690/$700).
  Note for reviewers: $700 at 50% with SPY $693.89 is skew, not an error (digital = N(d2) - vega * dsigma/dK).
  Also a put-call parity guard: if the quotes imply a stock price over 0.1 sd from the last price, one-vol is shown.
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
  every strike". Done 2026-11-18 (polish): a practice trade opened from a card reads each strike's vol the
  card's way (`practice_options._strike_vols`, same OTM-side / 1% / 3-day / half-to-twice rule), stores it on the
  leg (marks keep it) and opens at the card's debit; it used the AVERAGE of the legs' IVs (AAPL $350/$370 with a
  26%/23% smile: card $809, opened at $703).
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
