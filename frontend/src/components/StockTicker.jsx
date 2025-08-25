// ~/Documents/MarketPlayground_CleanMain/frontend/src/components/StockTicker.jsx
// Dynamic ticker bar with search, add/remove controls, and Alpaca-driven price updates.
// Users can type to search tickers (calls backend for suggestions), add them to the display,
// remove tickers individually, and the component refreshes prices at a regular interval.

import React, { useState, useEffect } from 'react';

const REFRESH_INTERVAL_MS = 30_000; // refresh prices every 30 seconds

const StockTicker = ({ backendUrl }) => {
  // List of tickers currently displayed
  const [tickers, setTickers] = useState([]);
  // Market data for those tickers (price, change)
  const [tickerData, setTickerData] = useState([]);
  // Loading indicator
  const [isLoading, setIsLoading] = useState(false);
  // User input for searching/adding a ticker
  const [searchInput, setSearchInput] = useState('');
  // Suggestions returned by backend for partial searchInput
  const [suggestions, setSuggestions] = useState([]);

  /**
   * Fetch current prices for the given array of symbols.
   * Returns: [{ symbol, price, change, changePercent }, ...]
   */
  const fetchPrices = async (symbols) => {
    if (symbols.length === 0) return [];
    try {
      const resp = await fetch(
        `${backendUrl}/market_data/get_prices?tickers=${symbols.join(',')}`
      );
      return await resp.json();
    } catch (err) {
      console.error('Price fetch error:', err);
      return [];
    }
  };

  /**
   * Fetch autocomplete suggestions for the user’s search input.
   * Assumes you expose an endpoint like /market_data/search_tickers?query=...
   * which returns an array of matching ticker symbols.
   */
  const fetchSuggestions = async (query) => {
    if (!query) {
      setSuggestions([]);
      return;
    }
    try {
      const resp = await fetch(
        `${backendUrl}/market_data/search_tickers?query=${encodeURIComponent(query)}`
      );
      const data = await resp.json();
      setSuggestions(data);
    } catch (err) {
      console.error('Suggestion fetch error:', err);
      setSuggestions([]);
    }
  };

  // When the tickers list changes, load fresh prices immediately.
  useEffect(() => {
    let isMounted = true;
    const loadData = async () => {
      setIsLoading(true);
      const prices = await fetchPrices(tickers);
      if (isMounted) {
        setTickerData(prices);
        setIsLoading(false);
      }
    };
    loadData();
    return () => {
      isMounted = false;
    };
  }, [tickers]);

  // Set up an interval to refresh prices on a timer.
  useEffect(() => {
    const intervalId = setInterval(async () => {
      const prices = await fetchPrices(tickers);
      setTickerData(prices);
    }, REFRESH_INTERVAL_MS);
    return () => clearInterval(intervalId);
  }, [tickers]);

  // Update suggestions when the user types.
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      fetchSuggestions(searchInput);
    }, 300); // debounce calls by 300 ms
    return () => clearTimeout(timeoutId);
  }, [searchInput]);

  // Add a selected symbol to our tickers list, if not already present
  const addTicker = (symbol) => {
    const sym = symbol.toUpperCase();
    if (!tickers.includes(sym)) {
      setTickers((prev) => [...prev, sym]);
    }
    setSearchInput('');
    setSuggestions([]);
  };

  // Remove a ticker from the list
  const removeTicker = (symbol) => {
    setTickers((prev) => prev.filter((t) != symbol));
  };

  return (
    <div className="bg-slate-900 text-white p-2 border-b border-slate-700">
      {/* Search and Add controls */}
      <div className="flex flex-wrap items-center gap-3 mb-2">
        <input
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder="Search ticker…"
          className="flex-grow border px-2 py-1 bg-slate-800 text-white"
        />
        <button
          onClick={() => addTicker(searchInput)}
          disabled={!searchInput.trim()}
          className="bg-blue-600 px-3 py-1 rounded disabled:opacity-50"
        >
          Add
        </button>
        {/* Suggestion dropdown */}
        {suggestions.length > 0 && (
          <div className="absolute mt-10 z-50 w-64 bg-slate-800 border border-slate-700 rounded shadow">
            {suggestions.map((sym) => (
              <div
                key={sym}
                onClick={() => addTicker(sym)}
                className="px-3 py-2 hover:bg-slate-700 cursor-pointer"
              >
                {sym}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Loading state */}
      {isLoading && <div className="text-center text-slate-400">Loading market data…</div>}

      {/* Ticker strip */}
      {!isLoading && tickerData.length > 0 && (
        <div className="overflow-x-auto flex gap-8 animate-pulse">
          {tickerData.map(({ symbol, price, change }) => (
            <div key={symbol} className="flex items-center gap-2 whitespace-nowrap">
              <span className="font-bold text-blue-400">{symbol}</span>
              <span className="font-semibold">${price.toFixed(2)}</span>
              <span className={change >= 0 ? 'text-green-400' : 'text-red-400'}>
                {change >= 0 ? '▲' : '▼'} {Math.abs(change).toFixed(2)}
              </span>
              {/* Remove button */}
              <button
                onClick={() => removeTicker(symbol)}
                className="ml-2 text-slate-400 hover:text-red-400"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Empty state message */}
      {!isLoading && tickerData.length === 0 && (
        <div className="text-center text-slate-400">
          No tickers selected. Add one above.
        </div>
      )}
    </div>
  );
};

export default StockTicker;
