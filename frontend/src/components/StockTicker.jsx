// ~/Documents/MarketPlayground_CleanMain/frontend/src/components/StockTicker.jsx
// Live Alpaca-powered ticker bar with search, add/remove, persistence, and refresh.

import React, { useState, useEffect, useRef } from 'react';

const REFRESH_INTERVAL_MS = 30_000; // 30s
const STORAGE_KEY = 'mp_top_tickers';

const StockTicker = ({ backendUrl = '' }) => {
  const [tickers, setTickers] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
      return Array.isArray(saved) ? saved : [];
    } catch {
      return [];
    }
  });
  const [tickerData, setTickerData] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  const [searchInput, setSearchInput] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const abortRef = useRef(null);

  // Persist tickers
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(tickers));
  }, [tickers]);

  const fetchPrices = async (symbols) => {
    if (!symbols?.length) return [];
    try {
      const url = `${backendUrl}/ticker/prices?tickers=${encodeURIComponent(symbols.join(','))}`;
      const resp = await fetch(url);
      return await resp.json();
    } catch (err) {
      console.error('Price fetch error:', err);
      return [];
    }
  };

  const fetchSuggestions = async (query) => {
    if (!query) {
      setSuggestions([]);
      return;
    }
    try {
      if (abortRef.current) abortRef.current.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      const url = `${backendUrl}/ticker/search?query=${encodeURIComponent(query)}&limit=10`;
      const resp = await fetch(url, { signal: ctrl.signal });
      const data = await resp.json();
      setSuggestions(Array.isArray(data) ? data : []);
    } catch (err) {
      // ignore abort errors
      setSuggestions([]);
    }
  };

  // immediate load on tickers change
  useEffect(() => {
    let alive = true;
    (async () => {
      setIsLoading(true);
      const data = await fetchPrices(tickers);
      if (alive) {
        setTickerData(data);
        setIsLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [tickers]);

  // scheduled refresh
  useEffect(() => {
    if (!tickers.length) return;
    const id = setInterval(async () => {
      const data = await fetchPrices(tickers);
      setTickerData(data);
    }, REFRESH_INTERVAL_MS);
    return () => clearInterval(id);
  }, [tickers]);

  // debounce search
  useEffect(() => {
    const id = setTimeout(() => fetchSuggestions(searchInput.trim()), 250);
    return () => clearTimeout(id);
  }, [searchInput]);

  const addTicker = (symbol) => {
    const sym = (symbol || '').toUpperCase().trim();
    if (!sym) return;
    if (!tickers.includes(sym)) {
      setTickers(prev => [...prev, sym]);
    }
    setSearchInput('');
    setSuggestions([]);
  };

  const removeTicker = (symbol) => {
    setTickers(prev => prev.filter(t => t !== symbol)); // strict equality fix
  };

  const onInputKeyDown = (e) => {
    if (e.key === 'Enter') {
      if (suggestions.length > 0) addTicker(suggestions[0]);
      else addTicker(searchInput);
    }
  };

  return (
    <div className="relative bg-slate-900 text-white p-2 border-b border-slate-700">
      {/* Search + Add */}
      <div className="flex flex-wrap items-center gap-3 mb-2">
        <input
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          onKeyDown={onInputKeyDown}
          placeholder="Search ticker…"
          className="flex-grow border px-2 py-1 bg-slate-800 text-white rounded"
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
          <div className="absolute top-12 left-2 z-50 w-64 bg-slate-800 border border-slate-700 rounded shadow max-h-64 overflow-auto">
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
      {!isLoading && tickerData?.length > 0 && (
        <div className="overflow-x-auto flex gap-8">
          {tickerData.map(({ symbol, price, change, changePercent }) => {
            const up = (change ?? 0) >= 0;
            return (
              <div key={symbol} className="flex items-center gap-2 whitespace-nowrap">
                <span className="font-bold text-blue-400">{symbol}</span>
                <span className="font-semibold">
                  {price != null ? `$${Number(price).toFixed(2)}` : '--'}
                </span>
                <span className={up ? 'text-green-400' : 'text-red-400'}>
                  {change != null ? (up ? '▲' : '▼') : ''}{' '}
                  {change != null ? Math.abs(Number(change)).toFixed(2) : '--'}
                  {changePercent != null ? ` (${Math.abs(Number(changePercent)).toFixed(2)}%)` : ''}
                </span>
                <button
                  onClick={() => removeTicker(symbol)}
                  className="ml-2 text-slate-400 hover:text-red-400"
                  aria-label={`Remove ${symbol}`}
                >
                  ×
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && (!tickerData || tickerData.length === 0) && (
        <div className="text-center text-slate-400">No tickers selected. Add one above.</div>
      )}
    </div>
  );
};

export default StockTicker;
