// backend/routes/fusionScan.js

/**
 * @fileoverview
 * GET /api/fusion-scan
 * Combines the top AI‑picked options and futures trades
 * into a single sorted “fusion” list.
 */

const express = require('express');
const router = express.Router();

// Mock AI modules
const OptionScanner = require('../ai_trade_engine/OptionScanner');
const FuturesScanner = require('../ai_trade_engine/FuturesScanner');

/**
 * @route   GET /api/fusion-scan
 * @returns { fusion: Array<{ symbol: string, score: number }> }
 */
router.get('/', async (req, res) => {
  try {
    // 1) Fetch top options from OptionScanner
    const options = await OptionScanner.getTopOptions();

    // 2) Fetch top futures from FuturesScanner
    const futures = await FuturesScanner.getTopFutures();

    // 3) Merge & sort by descending score, then take top 5
    const fusion = [...options, ...futures]
      .sort((a, b) => b.score - a.score)
      .slice(0, 5);

    // 4) Send the fusion list back to client
    return res.status(200).json({ fusion });
  } catch (err) {
    console.error('Fusion scan failed:', err);
    return res.status(500).json({ error: 'Fusion engine error' });
  }
});

module.exports = router;
