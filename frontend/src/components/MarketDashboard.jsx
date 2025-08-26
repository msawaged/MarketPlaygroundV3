// frontend/src/components/MarketDashboard.jsx

import React, { useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';

// MarketDashboard
//
// This component renders a dark‑themed market overview page inspired by
// contemporary finance dashboards. It fetches live pricing for a set of
// well‑known symbols from the existing backend and surfaces several
// different views (top gainers, top losers, trending now). Each row
// includes a button to launch the strategy generator. The layout is
// responsive: on mobile devices only the most essential columns are
// shown, while larger screens reveal additional detail. All styling
// uses Tailwind CSS classes and micro interactions are animated
// through Framer Motion. Debugging can be toggled by setting
// `DEBUG_DASHBOARD` to `true`.

// Determine the backend URL.  We reuse the same heuristic as
// ChatInterface.jsx: if a VITE_BACKEND_URL environment variable is
// provided it takes precedence, otherwise we fall back to the origin.
const BACKEND_URL =
  import.meta.env?.VITE_BACKEND_URL ||
  `${window.location.protocol}//${window.location.hostname}${window.location.port ? `:${window.location.port}` : ''}`;

// Set to true to enable verbose debugging in the console.
const DEBUG_DASHBOARD = false;

// A starter set of tickers used to populate the dashboard.  These
// symbols represent some of the most actively traded U.S. equities
// and can be replaced or extended at runtime.
const DEFAULT_TICKERS = [
  'AAPL',
  'MSFT',
  'AMZN',
  'NVDA',
  'TSLA',
  'GOOGL',
  'META',
  'AMD',
  'INTC',
  'NFLX',
];

/**
 * MarketDashboard component
 *
 * Displays a configurable heat map of the market. Tabs allow the
 * user to switch between top gainers, top losers and a general
 * trending view. Data is refreshed on mount but could easily be
 * extended to poll periodically.
 */
function MarketDashboard() {
  const [activeTab, setActiveTab] = useState('gainers');
  const [stocksData, setStocksData] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Fetch data for the default set of tickers when the component
    // first mounts.  If additional tickers are desired they can be
    // concatenated onto DEFAULT_TICKERS before invoking this effect.
    async function fetchData() {
      setLoading(true);
      try {
        const tickersParam = DEFAULT_TICKERS.join(',');
        const response = await fetch(`${BACKEND_URL}/ticker/prices?tickers=${tickersParam}`);
        if (!response.ok) {
          throw new Error(`Backend responded with status ${response.status}`);
        }
        const payload = await response.json();
        // Transform the returned payload into a flat list of stock
        // entries.  The backend returns an object keyed on symbol,
        // which we turn into an array for easier sorting and rendering.
        const list = Object.entries(payload).map(([symbol, info]) => {
          const price = info?.price ?? info?.last ?? info?.mark ?? null;
          // Previous close may be named differently depending on the
          // Alpaca response.  We fall back through a handful of
          // plausible property names.
          const prev =
            info?.prev_close ??
            info?.prev_close_price ??
            info?.previousClose ??
            null;
          const change = price != null && prev != null ? price - prev : null;
          const changePct = price != null && prev != null ? ((price - prev) / prev) * 100 : null;
          return {
            symbol,
            name: info?.name || symbol,
            price,
            prev,
            change,
            changePct,
            volume: info?.volume ?? null,
          };
        });
        setStocksData(list);
        if (DEBUG_DASHBOARD) {
          console.debug('Fetched stock data:', list);
        }
      } catch (err) {
        if (DEBUG_DASHBOARD) {
          console.error('Failed to fetch stock data:', err);
        }
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  // Sort the stock list based on the active tab.  We avoid sorting
  // directly inside the render function to prevent unnecessary
  // computations on every render.
  const sortedStocks = useMemo(() => {
    const listCopy = [...stocksData];
    switch (activeTab) {
      case 'gainers':
        return listCopy
          .filter((s) => s.changePct != null)
          .sort((a, b) => b.changePct - a.changePct);
      case 'losers':
        return listCopy
          .filter((s) => s.changePct != null)
          .sort((a, b) => a.changePct - b.changePct);
      case 'trending':
      default:
        // For trending view we simply return the data as‑is.  In a
        // future iteration this could be replaced with an API call
        // against /ticker/search or similar to compute popularity.
        return listCopy;
    }
  }, [stocksData, activeTab]);

  // Handler invoked when the "Create Strategy" button is clicked.  In
  // a real application this would hook into the ML Loop to propose
  // algorithmic trading strategies.  For now it simply notifies the
  // user which symbol they selected.
  function handleCreateStrategy(symbol) {
    // eslint-disable-next-line no-alert
    alert(`Strategy generator coming soon for ${symbol || 'selected ticker'}`);
  }

  // Tab configuration.  If new tabs are added in the future simply
  // append to this array and ensure the `activeTab` state covers
  // them.
  const tabs = [
    { key: 'gainers', label: 'Top Gainers' },
    { key: 'losers', label: 'Top Losers' },
    { key: 'trending', label: 'Trending Now' },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 via-gray-800 to-black text-gray-200 p-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <h1 className="text-3xl font-bold mb-4">Market Dashboard</h1>
        {/* Tab bar */}
        <div className="flex space-x-2 mb-4 border-b border-gray-700 overflow-x-auto">
          {tabs.map((tab) => (
            <motion.button
              key={tab.key}
              className={`whitespace-nowrap px-4 py-2 rounded-t-lg font-medium focus:outline-none transition-colors duration-200 ${
                activeTab === tab.key
                  ? 'bg-gray-800 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
              onClick={() => setActiveTab(tab.key)}
              whileHover={{ scale: 1.05 }}
            >
              {tab.label}
            </motion.button>
          ))}
        </div>
        <div className="overflow-x-auto rounded-lg shadow-inner">
          <table className="min-w-full divide-y divide-gray-700">
            <thead>
              <tr>
                <th className="px-4 py-2 text-left">Symbol</th>
                <th className="px-4 py-2 text-left">Price</th>
                <th className="px-4 py-2 text-left">Change %</th>
                <th className="px-4 py-2 text-left hidden sm:table-cell">Change</th>
                <th className="px-4 py-2 text-left hidden md:table-cell">Volume</th>
                <th className="px-4 py-2 text-left">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {loading ? (
                <tr>
                  <td colSpan={6} className="text-center py-4">
                    Loading...
                  </td>
                </tr>
              ) : (
                sortedStocks.map((stock) => (
                  <motion.tr
                    key={stock.symbol}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                    className="hover:bg-gray-800"
                  >
                    <td className="px-4 py-2 font-semibold">{stock.symbol}</td>
                    <td className="px-4 py-2">
                      {stock.price != null ? stock.price.toFixed(2) : '—'}
                    </td>
                    <td
                      className={`px-4 py-2 ${
                        stock.changePct > 0
                          ? 'text-green-400'
                          : stock.changePct < 0
                          ? 'text-red-400'
                          : ''
                      }`}
                    >
                      {stock.changePct != null
                        ? `${stock.changePct.toFixed(2)}%`
                        : '—'}
                    </td>
                    <td
                      className={`px-4 py-2 hidden sm:table-cell ${
                        stock.change > 0
                          ? 'text-green-400'
                          : stock.change < 0
                          ? 'text-red-400'
                          : ''
                      }`}
                    >
                      {stock.change != null ? stock.change.toFixed(2) : '—'}
                    </td>
                    <td className="px-4 py-2 hidden md:table-cell">
                      {stock.volume != null ? stock.volume.toLocaleString() : '—'}
                    </td>
                    <td className="px-4 py-2">
                      <motion.button
                        whileHover={{ scale: 1.05 }}
                        className="px-3 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white focus:outline-none"
                        onClick={() => handleCreateStrategy(stock.symbol)}
                      >
                        Create Strategy
                      </motion.button>
                    </td>
                  </motion.tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </motion.div>
    </div>
  );
}

export default MarketDashboard;
