// backend/routes/playFusion.js

/**
 * @fileoverview
 * POST /api/play-fusion
 * Simulates a “Futures Fusion” game round by:
 *   1) AI‑picking an options contract
 *   2) AI‑picking a futures setup
 *   3) Generating mock price data
 *   4) Running game logic to determine win/loss
 */

const express = require('express');
const router = express.Router();

const OptionScanner = require('../ai_trade_engine/OptionScanner');
const FuturesScanner = require('../ai_trade_engine/FuturesScanner');
const FuturesFusionLogic = require('../game_engine/FuturesFusionLogic');

/**
 * Generate an array of mock price updates over time.
 * @param {number} optionStrike  - entry strike price for option
 * @param {number} futuresLevel  - breakout threshold for futures
 * @returns {Array<{ option: number, futures: number }>}
 */
function generateMockPrices({ optionStrike, futuresLevel }) {
  const updates = [];
  for (let i = 0; i < 10; i++) {
    updates.push({
      option: optionStrike + (Math.random() - 0.5) * 10,
      futures: futuresLevel + (Math.random() - 0.5) * 80,
    });
  }
  return updates;
}

/**
 * @route   POST /api/play-fusion
 * @returns { 
 *   message: string, 
 *   result: { optionHit: boolean, futuresHit: boolean, result: 'win'|'loss' },
 *   optionTrade: object,
 *   futuresTrade: object
 * }
 */
router.post('/play-fusion', async (req, res) => {
  try {
    // 1) AI selects an options contract
    const optionTrade = await OptionScanner.getTopOptions().then(list => list[0]);

    // 2) AI selects a futures setup
    const futuresTrade = await FuturesScanner.getTopFutures().then(list => list[0]);

    // 3) Mock real-time price updates
    const priceUpdates = generateMockPrices({
      optionStrike: optionTrade.symbol.includes('_')
        ? Number(optionTrade.symbol.split('_')[1].slice(0, -1)) // crude parse
        : 0,
      futuresLevel: futuresTrade.score * 10 // placeholder logic
    });

    // 4) Run the FuturesFusionLogic engine
    const result = FuturesFusionLogic({
      optionEntry: optionTrade,
      futuresEntry: futuresTrade,
      priceUpdates,
    });

    // 5) Return the full round details
    return res.status(200).json({
      message: 'Game round completed',
      result,
      optionTrade,
      futuresTrade,
      priceUpdates,
    });
  } catch (error) {
    console.error('Error in /play-fusion:', error);
    return res.status(500).json({ error: 'Internal server error' });
  }
});

module.exports = router;
