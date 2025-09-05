// 🚀 COMPLETE ELITE MOBILE TRADING INTERFACE - FULL FEATURED
// 📱 Interactive charts, touch controls, premium animations, ALL YOUR FEATURES + MORE!

import ChatInterface from "./components/ChatInterface.jsx";
export default ChatInterface;
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

import { API_BASE, processBelief } from "../lib/api";
// ADD THIS IMPORT WITH YOUR OTHER IMPORTS
import DebugDashboard from './DebugDashboard';
import BottomNavigation from './BottomNavigation'; // ← ADD THIS LINE
import { PortfolioModal } from './PortfolioComponents';

// Sentiment Validation Error Component
const SentimentErrorMessage = ({ error, onRetry, originalBelief }) => {
  const getSuggestions = (error) => {
    if (error.detected_sentiment === 'bullish') {
      return [
        `${originalBelief.split(' ')[0]} will rally strongly`,
        `${originalBelief.split(' ')[0]} is going to moon`,
        `Very bullish on ${originalBelief.split(' ')[0]} - strong upside`
      ];
    } else if (error.detected_sentiment === 'bearish') {
      return [
        `${originalBelief.split(' ')[0]} will crash`,
        `${originalBelief.split(' ')[0]} is heading down fast`,
        `Very bearish on ${originalBelief.split(' ')[0]} - strong downside`
      ];
    }
    return [
      `Try being more specific about direction`,
      `Add words like "rally", "surge", "crash", or "tank"`
    ];
  };

  const suggestions = getSuggestions(error);

  return (
    <div className="mb-4 p-4 bg-gradient-to-r from-red-900/50 to-orange-900/50 rounded-xl border border-red-500/30">
      {/* Error Header */}
      <div className="flex items-start gap-3 mb-3">
        <div className="w-8 h-8 bg-red-500 rounded-full flex items-center justify-center flex-shrink-0">
          <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
          </svg>
        </div>
        <div className="flex-1">
          <h4 className="text-red-400 font-semibold text-sm mb-1">
            Strategy Blocked for Your Protection
          </h4>
          <p className="text-red-300 text-xs leading-relaxed">
            {error.message}
          </p>
        </div>
      </div>

      {/* Suggestions */}
      <div className="mb-4">
        <h5 className="text-orange-400 font-medium text-xs mb-2">
          Try rephrasing with stronger language:
        </h5>
        <div className="space-y-2">
          {suggestions.map((suggestion, index) => (
            <button
              key={index}
              onClick={() => onRetry(suggestion)}
              className="w-full text-left p-2 bg-orange-900/30 hover:bg-orange-800/40 rounded-lg border border-orange-700/30 text-orange-200 text-xs transition-colors"
            >
              "{suggestion}"
            </button>
          ))}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-2">
        <button
          onClick={() => onRetry(originalBelief)}
          className="flex-1 bg-orange-600 hover:bg-orange-700 text-white text-xs py-2 px-3 rounded-lg font-medium transition-colors"
        >
          Try Again
        </button>
      </div>
    </div>
  );
};

// 🌐 BACKEND URL CONFIGURATION - Now uses centralized API base from Vite env
// Configured via VITE_API_BASE environment variable
const BACKEND_URL = API_BASE;

// 📊 LIVE ELITE STOCK TICKER – FINAL VERSION
const EliteLiveSymbolsKey = 'mp_elite_symbols';

const EliteStockTicker = () => {
  const [position, setPosition] = useState(0);
  const [symbols, setSymbols] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(EliteLiveSymbolsKey) || '["SPY","AAPL","TSLA","NVDA"]');
      return Array.isArray(saved) && saved.length ? saved : ["SPY","AAPL","TSLA","NVDA"];
    } catch { return ["SPY","AAPL","TSLA","NVDA"]; }
  });
  const [tickerData, setTickerData] = useState([]);
  const [searchInput, setSearchInput] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);

  // Step 1: new state for the add‑ticker modal and its search
  const [showAddModal, setShowAddModal] = useState(false);
  const [modalSearchInput, setModalSearchInput] = useState('');
  const [modalSuggestions, setModalSuggestions] = useState([]);

  const abortRef = useRef(null);

  // persist symbols
  useEffect(() => {
    localStorage.setItem(EliteLiveSymbolsKey, JSON.stringify(symbols));
  }, [symbols]);

  const fetchPrices = async (list) => {
    if (!list?.length) { setTickerData([]); return; }
    try {
      setLoading(true);
      const url = `${BACKEND_URL}/ticker/prices?tickers=${encodeURIComponent(list.join(','))}`;
      const resp = await fetch(url);
      const data = await resp.json();
      
      const norm = (data || []).map((d) => ({
        symbol: d.symbol,
        price: typeof d.price === 'number' ? d.price : null,
        change: typeof d.change === 'number' ? d.change : 0,
        changePercent: typeof d.changePercent === 'number' ? d.changePercent : 0,
      }));

      const bySym = Object.fromEntries(norm.map(r => [r.symbol, r]));
      const ordered = (list || []).map(s => bySym[s]).filter(Boolean);

      setTickerData(ordered);

    } catch (e) {
      console.error('EliteTicker fetch error:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchPrices(symbols); }, [symbols]);

  useEffect(() => {
    if (!symbols.length) return;
    const id = setInterval(() => fetchPrices(symbols), 30_000);
    return () => clearInterval(id);
  }, [symbols]);

  // simple marquee
  useEffect(() => {
    const id = setInterval(() => {
      setPosition(prev => prev <= -100 ? 100 : prev - 0.4);
    }, 50);
    return () => clearInterval(id);
  }, []);

  // suggestions (debounced)
  useEffect(() => {
    const q = searchInput.trim();
    if (!q) { setSuggestions([]); return; }
    const id = setTimeout(async () => {
      try {
        if (abortRef.current) abortRef.current.abort();
        const ctrl = new AbortController();
        abortRef.current = ctrl;
        const url = `${BACKEND_URL}/ticker/search?query=${encodeURIComponent(q)}&limit=10`;
        const r = await fetch(url, { signal: ctrl.signal });
        const s = await r.json();
        setSuggestions(Array.isArray(s) ? s : []);
      } catch { setSuggestions([]); }
    }, 250);
    return () => clearTimeout(id);
  }, [searchInput]);

  // Modal search suggestions
  useEffect(() => {
    const q = modalSearchInput.trim();
    if (!q) {
      setModalSuggestions([]);
      return;
    }
    const id = setTimeout(async () => {
      try {
        const url = `${BACKEND_URL}/ticker/search?query=${encodeURIComponent(q)}&limit=10`;
        const resp = await fetch(url);
        const results = await resp.json();
        setModalSuggestions(Array.isArray(results) ? results : []);
      } catch {
        setModalSuggestions([]);
      }
    }, 250);
    return () => clearTimeout(id);
  }, [modalSearchInput]);

  const addSymbol = (sym) => {
    const S = (sym || '').toUpperCase().trim();
    if (!S) return;

    // Allowable shapes: e.g., AAPL, BRK.B, RDS-A, MSFT, SPY
    const VALID = /^[A-Z0-9.\-]{1,6}$/;
    if (!VALID.test(S)) {
      setSearchInput('');
      setSuggestions([]);
      setModalSearchInput('');
      return;
    }

    if (!symbols.includes(S)) {
      setSymbols((prev) => [...prev, S]);
    }

    setSearchInput('');
    setSuggestions([]);
    setModalSearchInput('');
    setShowAddModal(false);
  };

  const removeSymbol = (sym) => setSymbols(prev => prev.filter(s => s !== sym));

  return (
    <div className="relative z-50 bg-gradient-to-r from-slate-900 via-indigo-900 to-slate-900 text-white py-3 overflow-hidden border-b-2 border-blue-400/40 shadow-xl">
      {/* background tint */}
      <div className="absolute inset-0 bg-gradient-to-r from-blue-500/10 via-purple-500/10 to-pink-500/10 pointer-events-none z-0" />



      {/* Search/Add row removed – we now use only the floating "+ Add" button + modal */}

      {/* Ticker management modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60">
          <div className="bg-slate-800 p-4 rounded-lg w-80 max-h-[80vh] overflow-y-auto">
            <h3 className="text-lg font-bold text-white mb-3">Manage Tickers</h3>
            
            {/* Search for new tickers in the modal */}
            <input
              value={modalSearchInput}
              onChange={(e) => setModalSearchInput(e.target.value)}
              placeholder="Search ticker…"
              className="w-full mb-2 bg-slate-700 border border-slate-600 rounded px-3 py-2 text-sm text-white placeholder-slate-400"
            />
            
            {/* Modal suggestions */}
            {modalSuggestions.length > 0 && (
              <div className="mb-3 max-h-32 overflow-y-auto bg-slate-700 border border-slate-600 rounded">
                {modalSuggestions.map((s) => (
                  <div
                    key={s}
                    onClick={() => addSymbol(s)}
                    className="px-3 py-2 hover:bg-slate-600 cursor-pointer text-white text-sm"
                  >
                    {s}
                  </div>
                ))}
              </div>
            )}
            
            {/* List current tickers with remove buttons */}
            <div className="space-y-2 mb-3">
              <h4 className="text-sm font-semibold text-white">Current Tickers</h4>
              {symbols.map((sym) => (
                <div key={sym} className="flex items-center justify-between text-white bg-slate-700 px-3 py-2 rounded">
                  <span>{sym}</span>
                  <button
                    onClick={() => removeSymbol(sym)}
                    className="px-2 py-1 text-sm text-red-400 hover:text-red-500"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
            
            {/* Modal close button */}
            <div className="text-right">
              <button
                onClick={() => setShowAddModal(false)}
                className="px-3 py-2 bg-blue-600 hover:bg-blue-700 rounded text-white text-sm"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Scrolling ticker strip - double tap to manage */}
      <div
        className="relative z-20 flex space-x-8 whitespace-nowrap transition-transform duration-75 ease-linear px-3 cursor-pointer"
        style={{ transform: `translateX(${position}%)` }}
        onDoubleClick={() => setShowAddModal(true)}
        title="Double-click to manage tickers"
      >
        {[...tickerData, ...tickerData, ...tickerData].map((stock, index) => {
          const up = (stock.change ?? 0) >= 0;
          return (
            <div key={`${stock.symbol}-${index}`} className="flex items-center space-x-3 whitespace-nowrap">
              <span className="font-bold text-blue-400">{stock.symbol}</span>
              <span className="font-semibold">
                {stock.price != null ? `$${Number(stock.price).toLocaleString(undefined, {maximumFractionDigits: 2})}` : '--'}
              </span>
              <span className={up ? 'text-green-400' : 'text-red-400'}>
                {stock.change != null ? (up ? '▲' : '▼') : ''}{' '}
                {stock.change != null ? Math.abs(Number(stock.change)).toFixed(2) : '--'}
              </span>
              <span
                className={`text-xs px-3 py-1 rounded-full font-semibold border ${
                  up ? 'bg-green-500/30 text-green-300 border-green-400/50'
                     : 'bg-red-500/30 text-red-300 border-red-400/50'
                }`}
              >
                {stock.changePercent != null ? `(${up ? '+' : ''}${Number(stock.changePercent).toFixed(2)}%)` : '(--%)'}
              </span>
              <button
                onClick={()=>removeSymbol(stock.symbol)}
                className="ml-1 text-slate-400 hover:text-red-400"
                aria-label={`Remove ${stock.symbol}`}
              >
                ×
              </button>
            </div>
          );
        })}
      </div>

      {/* Loading badge */}
      {loading && (
        <div className="absolute right-3 top-3 text-xs text-slate-300 bg-slate-800/70 rounded px-2 py-1 z-20">
          updating…
        </div>
      )}
    </div>
  );
};

// INTERACTIVE P&L CHART WITH TOUCH CONTROLS + ALL YOUR ORIGINAL CHART TYPES
const InteractivePnLChart = ({ ticker, strategyType, price, confidence, assetClass, strikePrice, direction }) => {
  const [touchStrike, setTouchStrike] = useState(parseFloat(strikePrice) || 700);
  const [showTooltip, setShowTooltip] = useState(false);
  const [tooltipData, setTooltipData] = useState(null);
  const [animationFrame, setAnimationFrame] = useState(0);

  const currentPrice = parseFloat(price) || 637;
  const premium = currentPrice * 0.05;

  // ANIMATION LOOP FOR DYNAMIC EFFECTS (from your original)
  useEffect(() => {
    const interval = setInterval(() => {
      setAnimationFrame(prev => (prev + 1) % 360);
    }, 100);
    return () => clearInterval(interval);
  }, []);

  // Generate P&L curve with touch strike (ENHANCED)
  const generatePnLCurve = useCallback(() => {
    const points = [];
    for (let i = 0; i <= 100; i++) {
      const stockPrice = currentPrice * 0.5 + (currentPrice * 1.0 * i / 100);
      let pnl;
      
      if (strategyType.toLowerCase().includes('put')) {
        pnl = stockPrice < touchStrike ? (touchStrike - stockPrice - premium) : -premium;
      } else {
        pnl = stockPrice > touchStrike ? (stockPrice - touchStrike - premium) : -premium;
      }
      
      points.push({ x: i, price: stockPrice, pnl: Math.max(pnl, -premium * 2) });
    }
    return points;
  }, [touchStrike, currentPrice, premium, strategyType]);

  // Handle touch interactions
  const handleChartTouch = (event) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = ((event.touches?.[0]?.clientX || event.clientX) - rect.left) / rect.width;
    const newStrike = currentPrice * 0.5 + (currentPrice * 1.0 * x);
    setTouchStrike(newStrike);
    
    // Show tooltip
    const pointIndex = Math.floor(x * 100);
    const pnlPoints = generatePnLCurve();
    if (pnlPoints[pointIndex]) {
      const maxPnl = Math.max(...pnlPoints.map(p => p.pnl));
      const minPnl = Math.min(...pnlPoints.map(p => p.pnl));
      const pnlRange = maxPnl - minPnl || 1;
      
      setTooltipData({
        x: x * 100,
        y: ((maxPnl - pnlPoints[pointIndex].pnl) / pnlRange) * 80 + 10,
        price: pnlPoints[pointIndex].price,
        pnl: pnlPoints[pointIndex].pnl
      });
      setShowTooltip(true);
    }
  };

  // OPTIONS CHART: P&L DIAGRAM (ENHANCED FROM YOUR ORIGINAL)
  const renderOptionsChart = () => {
    const pnlPoints = generatePnLCurve();
    const maxPnl = Math.max(...pnlPoints.map(p => p.pnl));
    const minPnl = Math.min(...pnlPoints.map(p => p.pnl));
    const pnlRange = maxPnl - minPnl || 1;

    return (
      <div className="h-48 bg-slate-700/50 rounded-lg relative overflow-hidden">
        <svg 
          width="100%" 
          height="100%" 
          className="absolute inset-0 cursor-crosshair"
          onMouseMove={handleChartTouch}
          onTouchMove={handleChartTouch}
          onMouseLeave={() => setShowTooltip(false)}
          onTouchEnd={() => setShowTooltip(false)}
        >
          {/* GRADIENT BACKGROUND */}
          <defs>
            <linearGradient id="pnlGradient" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#22c55e" stopOpacity="0.3"/>
              <stop offset="50%" stopColor="#3b82f6" stopOpacity="0.1"/>
              <stop offset="100%" stopColor="#ef4444" stopOpacity="0.3"/>
            </linearGradient>
            <filter id="glow">
              <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
              <feMerge> 
                <feMergeNode in="coloredBlur"/>
                <feMergeNode in="SourceGraphic"/>
              </feMerge>
            </filter>
          </defs>

          {/* P&L CURVE WITH GLOW */}
          <motion.polyline
            fill="none"
            stroke={strategyType.toLowerCase().includes('put') ? "#ef4444" : "#22c55e"}
            strokeWidth="3"
            filter="url(#glow)"
            points={pnlPoints.map((point, index) => {
              const x = (index / (pnlPoints.length - 1)) * 100;
              const y = ((maxPnl - point.pnl) / pnlRange) * 80 + 10;
              return `${x},${y}`;
            }).join(' ')}
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 1, ease: "easeInOut" }}
          />

          {/* BREAKEVEN LINE */}
          <line x1="0" y1="50%" x2="100%" y2="50%" stroke="#94a3b8" strokeWidth="1" strokeDasharray="4,4" />
          
          {/* ADJUSTABLE STRIKE PRICE INDICATOR */}
          <motion.line 
            x1={((touchStrike - currentPrice * 0.5) / (currentPrice * 0.5)) * 100 + "%"} 
            y1="0" 
            x2={((touchStrike - currentPrice * 0.5) / (currentPrice * 0.5)) * 100 + "%"} 
            y2="100%" 
            stroke="#fbbf24" 
            strokeWidth="3"
            filter="url(#glow)"
            animate={{ x1: `${((touchStrike - currentPrice * 0.5) / (currentPrice * 0.5)) * 100}%` }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
          />
          
          {/* CURRENT PRICE INDICATOR */}
          <line x1="50%" y1="0" x2="50%" y2="100%" stroke="#3b82f6" strokeWidth="2" strokeDasharray="2,2" />

          {/* INTERACTIVE TOOLTIP */}
          {showTooltip && tooltipData && (
            <motion.g
              initial={{ opacity: 0, scale: 0 }}
              animate={{ opacity: 1, scale: 1 }}
            >
              <circle cx={tooltipData.x} cy={tooltipData.y} r="5" fill="#fbbf24" />
              <rect 
                x={tooltipData.x + 5} 
                y={tooltipData.y - 30} 
                width="100" 
                height="25" 
                fill="rgba(0,0,0,0.9)" 
                rx="4"
              />
              <text 
                x={tooltipData.x + 8} 
                y={tooltipData.y - 15} 
                fill="white" 
                fontSize="11"
              >
                P&L: ${tooltipData.pnl.toFixed(0)}
              </text>
              <text 
                x={tooltipData.x + 8} 
                y={tooltipData.y - 8} 
                fill="#94a3b8" 
                fontSize="9"
              >
                Price: ${tooltipData.price.toFixed(0)}
              </text>
            </motion.g>
          )}
        </svg>

        {/* CHART LABELS */}
        <div className="absolute top-2 left-2 text-xs text-green-400 font-bold">Profit Zone</div>
        <div className="absolute bottom-8 left-2 text-xs text-red-400 font-bold">Loss Zone</div>
        <div className="absolute top-2 right-2 text-xs text-yellow-400 font-bold">
          Strike: ${touchStrike.toFixed(0)}
        </div>
        <div className="absolute bottom-8 right-2 text-xs text-blue-400 font-bold">
          Current: ${currentPrice}
        </div>
        <div className="absolute top-2 left-1/2 transform -translate-x-1/2 text-xs text-white bg-black/50 px-2 py-1 rounded">
          {(confidence * 100).toFixed(0)}% Confidence
        </div>
      </div>
    );
  };

  // STOCKS/ETF CHART: PRICE TARGETS (ENHANCED FROM YOUR ORIGINAL)
  const renderStockChart = () => {
    const targetHigh = currentPrice * (direction === 'bullish' ? 1.15 : 0.95);
    const targetLow = currentPrice * (direction === 'bullish' ? 0.95 : 1.05);
    
    return (
      <div className="h-48 bg-slate-700/50 rounded-lg p-4 relative overflow-hidden">
        <div className="flex items-end justify-center h-full space-x-1">
          {/* ANIMATED PRICE BARS WITH TARGETS */}
          {Array.from({ length: 20 }, (_, i) => {
            const height = 30 + Math.sin((animationFrame + i * 30) * 0.02) * 20 + (confidence * 40);
            const isTarget = i === 5 || i === 15;
            const isSupport = i === 3 || i === 17;
            return (
              <motion.div
                key={i}
                className={`rounded-t transition-all duration-300 ${
                  isTarget ? 'bg-gradient-to-t from-yellow-600 to-yellow-400 shadow-lg' : 
                  isSupport ? 'bg-gradient-to-t from-orange-600 to-orange-400' :
                  direction === 'bullish' ? 'bg-gradient-to-t from-green-700 to-green-400' :
                  direction === 'bearish' ? 'bg-gradient-to-t from-red-700 to-red-400' :
                  'bg-gradient-to-t from-blue-700 to-blue-400'
                }`}
                style={{
                  height: `${Math.max(height, 15)}px`,
                  width: '8px'
                }}
                whileHover={{ scale: 1.1, filter: 'brightness(1.2)' }}
                initial={{ height: 0 }}
                animate={{ height: `${Math.max(height, 15)}px` }}
                transition={{ delay: i * 0.05 }}
              />
            );
          })}
        </div>
        
        {/* ENHANCED PRICE TARGET LABELS */}
        <div className="absolute top-2 left-2 text-xs">
          <div className="text-green-400 font-bold">Target: ${targetHigh.toFixed(0)}</div>
          <div className="text-blue-400">Current: ${currentPrice}</div>
        </div>
        <div className="absolute bottom-8 left-2 text-xs">
          <div className="text-red-400 font-bold">Support: ${targetLow.toFixed(0)}</div>
          <div className="text-yellow-400">Confidence: {(confidence * 100).toFixed(0)}%</div>
        </div>
        <div className="absolute top-2 right-2 text-xs text-slate-300">
          <div className="bg-black/50 px-2 py-1 rounded">
            {direction.toUpperCase()}
          </div>
        </div>
      </div>
    );
  };

  // BONDS CHART: YIELD CURVE (ENHANCED FROM YOUR ORIGINAL)
  const renderBondsChart = () => {
    const yieldCurve = [2.1, 2.3, 2.7, 3.1, 3.4, 3.6, 3.8, 4.0];
    
    return (
      <div className="h-48 bg-slate-700/50 rounded-lg p-4 relative overflow-hidden">
        <svg width="100%" height="100%" className="absolute inset-0">
          {/* ANIMATED BACKGROUND GRID */}
          <defs>
            <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
              <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#374151" strokeWidth="0.5"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" opacity="0.3"/>

          {/* ANIMATED YIELD CURVE */}
          <motion.polyline
            fill="none"
            stroke="#8b5cf6"
            strokeWidth="3"
            points={yieldCurve.map((yield_, index) => {
              const x = (index / (yieldCurve.length - 1)) * 90 + 5;
              const y = ((4.5 - yield_) / 2.5) * 70 + 15;
              return `${x},${y}`;
            }).join(' ')}
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 2, ease: "easeInOut" }}
          />
          
          {/* INTERACTIVE YIELD POINTS */}
          {yieldCurve.map((yield_, index) => {
            const x = (index / (yieldCurve.length - 1)) * 90 + 5;
            const y = ((4.5 - yield_) / 2.5) * 70 + 15;
            return (
              <motion.circle
                key={index}
                cx={x}
                cy={y}
                r="4"
                fill="#a855f7"
                whileHover={{ r: 6, fill: "#c084fc" }}
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: index * 0.1 }}
              />
            );
          })}
          
          <text x="50%" y="95%" textAnchor="middle" fill="#8b5cf6" fontSize="12" fontWeight="bold">
            Yield Curve • Est. {(confidence * 4).toFixed(1)}% Return
          </text>
        </svg>
        
        {/* BOND METRICS */}
        <div className="absolute top-2 left-2 text-xs space-y-1">
          <div className="text-purple-400 font-bold">Bond Analysis</div>
          <div className="text-slate-300">Duration: {(confidence * 10).toFixed(1)} years</div>
          <div className="text-slate-300">Rating: AA+</div>
        </div>
      </div>
    );
  };

  // CRYPTO CHART: VOLATILITY BANDS (ENHANCED FROM YOUR ORIGINAL)
  const renderCryptoChart = () => {
    return (
      <div className="h-48 bg-slate-700/50 rounded-lg p-4 relative overflow-hidden">
        <div className="relative w-full h-full">
          {/* ANIMATED VOLATILITY WAVES */}
          {Array.from({ length: 7 }, (_, i) => (
            <motion.div
              key={i}
              className="absolute border-2 rounded-full opacity-20"
              style={{
                borderColor: ['#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#10b981', '#f97316', '#ec4899'][i],
                width: `${30 + i * 12}%`,
                height: `${30 + i * 12}%`,
                top: `${35 - i * 6}%`,
                left: `${35 - i * 6}%`,
              }}
              animate={{ 
                scale: [1, 1.1, 1],
                opacity: [0.2, 0.4, 0.2]
              }}
              transition={{ 
                duration: 3 + i * 0.5, 
                repeat: Infinity,
                delay: i * 0.2
              }}
            />
          ))}
          
          {/* ENHANCED PRICE CENTER */}
          <div className="absolute inset-0 flex items-center justify-center">
            <motion.div 
              className="text-center bg-black/30 backdrop-blur-sm rounded-xl p-4"
              whileHover={{ scale: 1.05 }}
            >
              <motion.div 
                className="text-2xl font-bold text-orange-400"
                animate={{ scale: [1, 1.05, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                ${currentPrice.toLocaleString()}
              </motion.div>
              <div className="text-sm text-slate-300">
                Vol: {(confidence * 150).toFixed(0)}%
              </div>
              <div className="text-xs text-green-400 mt-1">
                {direction.toUpperCase()}
              </div>
            </motion.div>
          </div>
          
          {/* CRYPTO METRICS */}
          <div className="absolute top-2 right-2 text-xs space-y-1 text-right">
            <div className="text-orange-400 font-bold">Crypto Analysis</div>
            <div className="text-slate-300">24h Vol: ${(currentPrice * 1000).toLocaleString()}</div>
            <div className="text-slate-300">Market Cap: $1.2T</div>
          </div>
        </div>
      </div>
    );
  };

  // MAIN CHART CONTAINER
  return (
    <motion.div 
      className="bg-gradient-to-br from-slate-800 to-slate-900 rounded-xl p-4 border border-blue-500/30 overflow-hidden"
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
    >
      <div className="text-center mb-4">
        {/* ENHANCED CHART HEADER */}
        <motion.div 
          className="text-2xl font-bold text-white"
          animate={{ scale: [1, 1.02, 1] }}
          transition={{ duration: 3, repeat: Infinity }}
        >
          {ticker}
        </motion.div>
        <div className="text-3xl text-green-400 font-bold">${typeof price === 'number' ? price.toFixed(2) : price}</div>
        <div className="text-sm text-slate-300 mt-1 font-semibold">{strategyType}</div>
        <div className="text-xs text-slate-400 mb-3">
          Confidence: {(confidence * 100).toFixed(1)}% • {assetClass?.toUpperCase()} • Touch to interact
        </div>
        
        {/* DYNAMIC CHART BASED ON ASSET CLASS */}
        {assetClass === 'options' && renderOptionsChart()}
        {(assetClass === 'equity' || assetClass === 'etf') && renderStockChart()}
        {assetClass === 'bonds' && renderBondsChart()}
        {assetClass === 'crypto' && renderCryptoChart()}
        
        {/* INTERACTIVE STRIKE PRICE SLIDER (Options Only) */}
        {assetClass === 'options' && (
          <div className="mt-4 space-y-2">
            <label className="text-xs text-slate-400 font-semibold">Adjust Strike Price:</label>
            <motion.input
              type="range"
              min={currentPrice * 0.7}
              max={currentPrice * 1.3}
              value={touchStrike}
              onChange={(e) => setTouchStrike(parseFloat(e.target.value))}
              className="w-full h-3 bg-gradient-to-r from-red-500 via-yellow-500 to-green-500 rounded-lg appearance-none cursor-pointer"
              whileFocus={{ scale: 1.02 }}
            />
            <div className="flex justify-between text-xs text-slate-400">
              <span>${(currentPrice * 0.7).toFixed(0)}</span>
              <span className="text-yellow-400 font-bold">${touchStrike.toFixed(0)}</span>
              <span>${(currentPrice * 1.3).toFixed(0)}</span>
            </div>
          </div>
        )}

        {/* ENHANCED MINI STATS GRID */}
        <div className="mt-4 grid grid-cols-3 gap-3 text-xs">
          <motion.div 
            className="bg-slate-700/50 rounded-lg p-3 text-center border border-slate-600"
            whileHover={{ scale: 1.05, borderColor: '#3b82f6' }}
          >
            <div className="text-slate-400 font-semibold">Strategy</div>
            <div className="text-blue-400 font-bold text-sm">{strategyType}</div>
          </motion.div>
          <motion.div 
            className="bg-slate-700/50 rounded-lg p-3 text-center border border-slate-600"
            whileHover={{ scale: 1.05, borderColor: '#10b981' }}
          >
            <div className="text-slate-400 font-semibold">Asset</div>
            <div className="text-white font-bold text-sm">{assetClass?.toUpperCase()}</div>
          </motion.div>
          <motion.div 
            className="bg-slate-700/50 rounded-lg p-3 text-center border border-slate-600"
            whileHover={{ scale: 1.05, borderColor: confidence > 0.7 ? '#22c55e' : confidence > 0.4 ? '#eab308' : '#ef4444' }}
          >
            <div className="text-slate-400 font-semibold">AI Score</div>
            <div className={`font-bold text-sm ${
              confidence > 0.7 ? 'text-green-400' : 
              confidence > 0.4 ? 'text-yellow-400' : 'text-red-400'
            }`}>
              {(confidence * 100).toFixed(0)}%
            </div>
          </motion.div>
        </div>

        {/* OPTIONS-SPECIFIC METRICS (Enhanced) */}
        {assetClass === 'options' && (
          <div className="mt-4 grid grid-cols-3 gap-2">
            <div className="bg-slate-700/30 rounded-lg p-2 text-center">
              <div className="text-xs text-slate-400">Breakeven</div>
              <div className="text-sm font-bold text-yellow-400">
                ${(touchStrike + premium).toFixed(0)}
              </div>
            </div>
            <div className="bg-slate-700/30 rounded-lg p-2 text-center">
              <div className="text-xs text-slate-400">Max Profit</div>
              <div className="text-sm font-bold text-green-400">
                {strategyType.toLowerCase().includes('call') ? 'Unlimited' : `$${(touchStrike - premium).toFixed(0)}`}
              </div>
            </div>
            <div className="bg-slate-700/30 rounded-lg p-2 text-center">
              <div className="text-xs text-slate-400">Max Loss</div>
              <div className="text-sm font-bold text-red-400">
                ${premium.toFixed(0)}
              </div>
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
};

// MAIN ENHANCED CHAT INTERFACE - KEEPING ALL YOUR ORIGINAL FEATURES
const EnhancedChatInterface = () => {
  // CHAT MESSAGE STATE (Same as your original)
  const [messages, setMessages] = useState([
    {
      id: 1,
      type: 'ai',
      content: 'Hi! I\'m your Elite AI trading strategist. Tell me what you believe about the market and I\'ll craft the perfect strategy!',
      timestamp: new Date()
    }
  ]);
  
  // USER INPUT STATE
  const [inputValue, setInputValue] = useState('');
  
  // LOADING STATE
  const [isLoading, setIsLoading] = useState(false);
  const [investmentAmount, setInvestmentAmount] = useState({});
  const [showPortfolioModal, setShowPortfolioModal] = useState(false);

  // Add this retry function here:
  const handleRetryMessage = (newBelief) => {
    setInputValue(newBelief);
  };
  
  // REF FOR AUTO-SCROLLING
  const messagesEndRef = useRef(null);

  // AUTO-SCROLL TO BOTTOM FUNCTION
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // AUTO-SCROLL EFFECT
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // MAIN MESSAGE SEND HANDLER (Enhanced with better error handling)
  const handleSend = async () => {
    if (!inputValue.trim()) return;

    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: inputValue,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    const belief = inputValue;
    setInputValue('');
    setIsLoading(true);

    try {
      // Use the centralized processBelief helper
      const data = await processBelief("murad", belief);
      
      console.log('Backend Response:', data);

      // Check for sentiment validation error
      if (data.error === "Strategy blocked due to sentiment misalignment") {
        const errorMessage = {
          id: Date.now() + 1,
          type: 'ai',
          content: `${data.reason || "Strategy blocked due to sentiment misalignment"}`,
          timestamp: new Date()
        };
        setMessages(prev => [...prev, errorMessage]);
        return;
      }

      // CREATE ENHANCED AI RESPONSE MESSAGE
      const aiResponse = {
        id: Date.now() + 1,
        type: 'ai',
        content: `Perfect! Based on your belief, I've crafted an elite **${data.strategy?.type || 'Strategy'}** for ${data.ticker}.`,
        
        // ENHANCED STRATEGY OBJECT WITH ALL YOUR ORIGINAL FIELDS
        strategy: {
          // BASIC STRATEGY INFO
          type: data.strategy?.type || 'Unknown',
          ticker: data.strategy?.trade_legs?.[0]?.ticker || data.ticker || 'N/A',
          confidence: data.confidence || 0.5,
          explanation: data.strategy?.explanation || 'No explanation available',
          price: data.price_info?.latest || 0,
          assetClass: data.asset_class || 'options',
          
          // ADDITIONAL STRATEGY METADATA  
          direction: data.direction || 'neutral',
          tags: data.tags || [],
          goal_type: data.goal_type || 'Unspecified',
          risk_profile: data.risk_profile || 'Moderate',
          expiry_date: data.expiry_date || 'N/A',
          trade_legs: data.strategy?.trade_legs || [],
          source: data.strategy?.source || 'unknown',
          
          // ALL YOUR ORIGINAL DYNAMIC FIELDS
          strike_price: data.strike_price || data.strategy?.trade_legs?.[0]?.strike_price,
          premium: data.premium,
          break_even: data.break_even,
          max_profit: data.max_profit,
          max_loss: data.max_loss,
          theta: data.theta,
          delta: data.delta,
          implied_volatility: data.implied_volatility,
          entry_price: data.entry_price,
          target_price: data.target_price,
          stop_loss: data.stop_loss,
          position_size: data.position_size,
          risk_reward_ratio: data.risk_reward_ratio,
          market_cap: data.market_cap,
          dividend_yield: data.dividend_yield,
          yield: data.yield,
          duration: data.duration,
          maturity_date: data.maturity_date,
          credit_rating: data.credit_rating,
          coupon_rate: data.coupon_rate,
          face_value: data.face_value,
          interest_rate_risk: data.interest_rate_risk,
          volatility: data.volatility,
          '24h_volume': data['24h_volume'],
          circulating_supply: data.circulating_supply,
          all_time_high: data.all_time_high,
          fear_greed_index: data.fear_greed_index
        },
        timestamp: new Date()
      };

      setMessages(prev => [...prev, aiResponse]);
      
    } catch (error) {
      console.error('API Error:', error);
      
      const errorMessage = {
        id: Date.now() + 1,
        type: 'error',
        content: 'Strategy generation failed',
        errorData: {
          message: error.message || 'An unexpected error occurred. Please try again.',
          detected_sentiment: 'unknown',
          blocked_strategy: 'system error',
          original_belief: belief
        },
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  // ENTER KEY HANDLER
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // RENDER DYNAMIC FIELDS (Enhanced from your original)
  const renderDynamicFields = (strategy) => {
    const { assetClass } = strategy;
    
    if (assetClass === 'options' && strategy.strike_price) {
      return (
        <div className="mb-3 p-3 bg-gradient-to-r from-purple-900/50 to-blue-900/50 rounded-lg border border-purple-500/30">
          <h4 className="text-xs font-semibold text-purple-300 mb-2">Options Details</h4>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div><span className="text-slate-400">Strike:</span> <span className="text-white ml-1 font-semibold">${strategy.strike_price}</span></div>
            {strategy.premium && (
              <div><span className="text-slate-400">Premium:</span> <span className="text-green-400 ml-1 font-semibold">{strategy.premium}</span></div>
            )}
            {strategy.break_even && (
              <div><span className="text-slate-400">Break Even:</span> <span className="text-yellow-400 ml-1 font-semibold">{strategy.break_even}</span></div>
            )}
            {strategy.max_profit && (
              <div><span className="text-slate-400">Max Profit:</span> <span className="text-green-400 ml-1 font-semibold">{strategy.max_profit}</span></div>
            )}
            {strategy.theta && (
              <div><span className="text-slate-400">Theta:</span> <span className="text-orange-400 ml-1 font-semibold">{strategy.theta}</span></div>
            )}
            {strategy.delta && (
              <div><span className="text-slate-400">Delta:</span> <span className="text-purple-400 ml-1 font-semibold">{strategy.delta}</span></div>
            )}
          </div>
        </div>
      );
    }
    
    return null;
  };

  // FEEDBACK SUBMISSION HANDLER (Enhanced from your original)
  const sendFeedback = async (strategy, feedbackType) => {
    try {
      await fetch(`${BACKEND_URL}/feedback/submit_feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          belief: messages.find(m => m.type === 'user')?.content || '',
          strategy: strategy.type,
          feedback: feedbackType,
          user_id: 'elite_chat_user',
        }),
      });
      
      // Enhanced toast notification
      const toast = document.createElement('div');
      toast.className = `fixed top-20 right-4 ${feedbackType === 'good' ? 'bg-green-500' : 'bg-red-500'} text-white px-6 py-3 rounded-xl z-50 font-bold shadow-lg`;
      toast.textContent = `${feedbackType === 'good' ? 'Awesome!' : 'Thanks for the feedback!'} Your input helps me improve.`;
      document.body.appendChild(toast);
      setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => document.body.removeChild(toast), 300);
      }, 2000);
    } catch (error) {
      console.error('Feedback error:', error);
      alert('Failed to send feedback - but I still appreciate it!');
    }
  };

  // MAIN COMPONENT RENDER
  return (
    <div className="h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white relative overflow-hidden">
      
      {/* ENHANCED STOCK TICKER AT TOP */}
      <div className="fixed top-0 left-0 right-0 z-50" style={{ paddingTop: 'env(safe-area-inset-top)' }}>
        <EliteStockTicker />
      </div>

      {/* ENHANCED HEADER WITH BRANDING */}
      <motion.div 
        className="fixed top-12 left-0 right-0 z-40 bg-gradient-to-r from-slate-800/95 via-slate-900/95 to-slate-800/95 backdrop-blur-sm border-b border-blue-500/30 p-4"
        initial={{ y: -50, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.5 }}
      >
        <div className="flex items-center gap-3">
          <motion.div 
            className="w-10 h-10 bg-gradient-to-r from-blue-500 via-purple-600 to-pink-600 rounded-xl flex items-center justify-center shadow-lg"
            whileHover={{ rotate: 360, scale: 1.1 }}
            transition={{ duration: 0.5 }}
          >
            <span className="text-white">AI</span>
          </motion.div>
          <div>
            <h1 className="font-bold text-lg bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
              MarketPlayground Elite
            </h1>
            <p className="text-sm text-blue-400">AI Trading Strategist</p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <motion.div 
              className="w-3 h-3 bg-green-400 rounded-full shadow-lg"
              animate={{ scale: [1, 1.3, 1], opacity: [1, 0.5, 1] }}
              transition={{ repeat: Infinity, duration: 2 }}
            />
            <span className="text-xs text-green-400 font-semibold">LIVE</span>
          </div>
        </div>
      </motion.div>

      {/* ENHANCED MESSAGES AREA */}
      <div className="overflow-y-auto p-4 space-y-6" 
           style={{ 
             paddingTop: '150px',
             paddingBottom: '140px',
             height: '100vh',
             WebkitOverflowScrolling: 'touch'
           }}>
        
        <AnimatePresence>
          {messages.map((message) => (
            <motion.div
              key={message.id}
              initial={{ opacity: 0, y: 30, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ duration: 0.3, type: "spring" }}
              className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div className={`max-w-sm lg:max-w-lg ${message.type === 'user' ? 'order-2' : 'order-1'}`}>
                {/* ENHANCED MESSAGE BUBBLE */}
                <motion.div
                  className={`px-6 py-4 rounded-2xl backdrop-blur-sm border ${
                    message.type === 'user'
                      ? 'bg-gradient-to-r from-blue-600/90 to-blue-700/90 text-white ml-12 border-blue-500/30'
                      : 'bg-gradient-to-r from-slate-700/90 to-slate-800/90 text-slate-100 mr-12 border-slate-600/30'
                  }`}
                  whileHover={{ scale: 1.02, y: -2 }}
                  transition={{ duration: 0.2 }}
                >
                  <p className="text-sm leading-relaxed">{message.content}</p>
                  <p className="text-xs opacity-60 mt-2">
                    {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </p>
                </motion.div>
                
                {/* ENHANCED STRATEGY CARD */}
                {message.strategy && (
                  <motion.div
                    initial={{ opacity: 0, y: 20, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    transition={{ delay: 0.3, duration: 0.4 }}
                    className="mt-4"
                  >
                    <div className="bg-gradient-to-br from-slate-800/95 to-slate-900/95 rounded-2xl border border-blue-500/30 overflow-hidden backdrop-blur-sm">
                      {/* STRATEGY HEADER - ENHANCED */}
                      <div className="bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 p-4">
                        <div className="flex justify-between items-center">
                          <div>
                            <motion.div 
                              className="text-2xl font-bold text-white"
                              animate={{ scale: [1, 1.02, 1] }}
                              transition={{ duration: 2, repeat: Infinity }}
                            >
                              {message.strategy.type}
                            </motion.div>
                            <div className="text-blue-100 text-lg">{message.strategy.ticker}</div>
                          </div>
                          <div className="text-right">
                            <motion.div 
                              className="text-3xl font-bold text-yellow-300"
                              animate={{ scale: [1, 1.1, 1] }}
                              transition={{ duration: 1.5, repeat: Infinity }}
                            >
                              {(message.strategy.confidence * 100).toFixed(0)}%
                            </motion.div>
                            <div className="text-xs text-blue-100">AI Confidence</div>
                            <div className={`mt-1 px-3 py-1 rounded-full text-sm font-bold ${
                              message.strategy.source === 'ml_model' ? 'bg-red-500/80' : 'bg-green-500/80'
                            } text-white`}>
                              {message.strategy.source === 'ml_model' ? 'ML' : 'GPT'}
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* ENHANCED KEY METRICS GRID */}
                      <div className="p-4">
                        <div className="grid grid-cols-2 gap-3 mb-4">
                          <motion.div 
                            className="bg-slate-700/50 rounded-lg p-3 text-center border border-slate-600"
                            whileHover={{ scale: 1.05, borderColor: '#22c55e' }}
                          >
                            <div className="text-xs text-slate-400 uppercase tracking-wide font-semibold">Direction</div>
                            <div className={`text-lg font-bold flex items-center justify-center gap-1 ${
                              message.strategy.direction === 'bullish' ? 'text-green-400' :
                              message.strategy.direction === 'bearish' ? 'text-red-400' : 'text-yellow-400'
                            }`}>
                              {message.strategy.direction === 'bullish' ? 'BULL' :
                               message.strategy.direction === 'bearish' ? 'BEAR' : 'NEUTRAL'}
                            </div>
                          </motion.div>

                          <motion.div 
                            className="bg-slate-700/50 rounded-lg p-3 text-center border border-slate-600"
                            whileHover={{ scale: 1.05, borderColor: '#3b82f6' }}
                          >
                            <div className="text-xs text-slate-400 uppercase tracking-wide font-semibold">Current Price</div>
                            <div className="text-lg font-bold text-green-400">${message.strategy.price}</div>
                          </motion.div>

                          <motion.div 
                            className="bg-slate-700/50 rounded-lg p-3 text-center border border-slate-600"
                            whileHover={{ scale: 1.05, borderColor: '#8b5cf6' }}
                          >
                            <div className="text-xs text-slate-400 uppercase tracking-wide font-semibold">Asset Class</div>
                            <div className={`text-sm font-bold px-2 py-1 rounded ${
                              message.strategy.assetClass === 'options' ? 'bg-blue-500 text-white' :
                              message.strategy.assetClass === 'equity' ? 'bg-green-500 text-white' :
                              message.strategy.assetClass === 'bonds' ? 'bg-purple-500 text-white' :
                              message.strategy.assetClass === 'crypto' ? 'bg-orange-500 text-white' :
                              'bg-gray-500 text-white'
                            }`}>
                              {message.strategy.assetClass?.toUpperCase()}
                            </div>
                          </motion.div>

                          <motion.div 
                            className="bg-slate-700/50 rounded-lg p-3 text-center border border-slate-600"
                            whileHover={{ scale: 1.05, borderColor: '#eab308' }}
                          >
                            <div className="text-xs text-slate-400 uppercase tracking-wide font-semibold">Expiry</div>
                            <div className="text-sm font-bold text-white">{message.strategy.expiry_date}</div>
                          </motion.div>
                        </div>

                        {/* Dynamic Options Fields */}
                        {renderDynamicFields(message.strategy)}

                        {/* Trade Legs */}
                        {message.strategy.trade_legs && message.strategy.trade_legs.length > 0 && (
                          <div className="mb-4">
                            <h4 className="text-sm font-bold text-blue-400 mb-3 flex items-center">
                              Trade Actions
                            </h4>
                            {message.strategy.trade_legs.map((leg, idx) => (
                              <motion.div 
                                key={idx} 
                                className="bg-slate-700/50 rounded-lg p-3 mb-2 border-l-4 border-blue-400"
                                whileHover={{ scale: 1.02, borderColor: '#22c55e' }}
                              >
                                <div className="flex justify-between items-center">
                                  <div>
                                    <span className="font-bold text-white">{leg.action || 'N/A'}</span>
                                    <span className="text-slate-300 ml-2">{leg.ticker || message.strategy.ticker}</span>
                                  </div>
                                  {leg.option_type && (
                                    <div className="text-right">
                                      <div className="text-sm font-bold text-blue-400">{leg.option_type}</div>
                                      <div className="text-xs text-slate-400">Strike: {leg.strike_price}</div>
                                    </div>
                                  )}
                                </div>
                              </motion.div>
                            ))}
                          </div>
                        )}

                        {/* Explanation */}
                        <div className="bg-slate-700/30 rounded-lg p-4 mb-4 border border-slate-600/50">
                          <h4 className="text-sm font-bold text-slate-200 mb-2 flex items-center">
                            Elite AI Analysis
                          </h4>
                          <p className="text-sm text-slate-300 leading-relaxed">{message.strategy.explanation}</p>
                        </div>

                        {/* Interactive Chart Component */}
                        <div className="mb-4">
                          <InteractivePnLChart
                            ticker={message.strategy.ticker}
                            strategyType={message.strategy.type}
                            price={message.strategy.price}
                            confidence={message.strategy.confidence}
                            assetClass={message.strategy.assetClass}
                            strikePrice={message.strategy.strike_price}
                            direction={message.strategy.direction}
                          />
                        </div>

                        {/* Enhanced Action Buttons with Investment Flow */}
                        {!investmentAmount[message.id] ? (
                          // Investment Amount Selection
                          <div className="space-y-4">
                            <h4 className="text-lg font-bold text-white text-center">How much do you want to invest?</h4>
                            <div className="grid grid-cols-2 gap-3">
                              {[500, 1000, 2500, 5000].map(amount => (
                                <button
                                  key={amount}
                                  onClick={() => setInvestmentAmount(prev => ({ ...prev, [message.id]: amount }))}
                                  className="bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-white font-bold py-3 rounded-lg"
                                >
                                  ${amount}
                                </button>
                              ))}
                            </div>
                            <input
                              type="number"
                              placeholder="Custom amount"
                              className="w-full bg-slate-700 text-white rounded-lg p-3"
                              onKeyPress={(e) => {
                                if (e.key === 'Enter' && e.target.value) {
                                  setInvestmentAmount(prev => ({ ...prev, [message.id]: parseInt(e.target.value) }));
                                }
                              }}
                            />
                          </div>
                        ) : (
                          // Show scenarios after investment selected
                          <div className="space-y-4">
                            <div className="text-center mb-4">
                              <h4 className="text-lg font-bold text-white">Investment: ${investmentAmount[message.id]}</h4>
                            </div>
                            
                            {/* Worst/Neutral/Best scenarios */}
                            <div className="grid grid-cols-3 gap-3">
                              <div className="bg-red-900/30 border border-red-500/30 rounded-lg p-3 text-center">
                                <div className="text-red-400 font-bold">Worst</div>
                                <div className="text-2xl font-bold text-red-400">-${investmentAmount[message.id]}</div>
                                <div className="text-xs text-red-300">Total Loss</div>
                              </div>
                              
                              <div className="bg-yellow-900/30 border border-yellow-500/30 rounded-lg p-3 text-center">
                                <div className="text-yellow-400 font-bold">Neutral</div>
                                <div className="text-2xl font-bold text-yellow-400">+${Math.round(investmentAmount[message.id] * 0.1)}</div>
                                <div className="text-xs text-yellow-300">10% gain</div>
                              </div>
                              
                              <div className="bg-green-900/30 border border-green-500/30 rounded-lg p-3 text-center">
                                <div className="text-green-400 font-bold">Best</div>
                                <div className="text-2xl font-bold text-green-400">+${Math.round(investmentAmount[message.id] * 3)}</div>
                                <div className="text-xs text-green-300">300% gain</div>
                              </div>
                            </div>
                      
                            {/* Original action buttons */}
                            <div className="grid grid-cols-3 gap-3 mt-4">
                              <motion.button 
                                onClick={() => sendFeedback(message.strategy, 'good')}
                                className="bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-white font-bold py-3 px-4 rounded-lg transition-all shadow-lg"
                                whileTap={{ scale: 0.95 }}
                                whileHover={{ scale: 1.05, y: -2 }}
                              >
                                Perfect
                              </motion.button>
                              <motion.button 
                                onClick={() => sendFeedback(message.strategy, 'bad')}
                                className="bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 text-white font-bold py-3 px-4 rounded-lg transition-all shadow-lg"
                                whileTap={{ scale: 0.95 }}
                                whileHover={{ scale: 1.05, y: -2 }}
                              >
                                Improve
                              </motion.button>
                              <motion.button 
                                onClick={async () => {
                                  try {
                                    const response = await fetch(`${BACKEND_URL}/api/paper-trading/execute`, {
                                      method: 'POST',
                                      headers: { 'Content-Type': 'application/json' },
                                      body: JSON.stringify({
                                          user_id: 'demo_user',
                                          strategy_data: {
                                            ...message.strategy,
                                            investment_amount: investmentAmount[message.id]
                                          },
                                          belief: inputValue || 'User strategy execution'
                                        })
                                    });
                                    
                                    const result = await response.json();
                                    
                                    if (result.status === 'success') {
                                      alert(`Trade executed: ${result.message}`);
                                    } else {
                                      alert(`Trade failed: ${result.message}`);
                                    }
                                  } catch (error) {
                                    alert(`Error: ${error.message}`);
                                  }
                                }}
                                className="bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white font-bold py-3 px-4 rounded-lg transition-all shadow-lg"
                                whileTap={{ scale: 0.95 }}
                                whileHover={{ scale: 1.05, y: -2 }}
                              >
                                Execute
                              </motion.button>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </motion.div>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {/* Loading Indicator */}
        {isLoading && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex justify-start"
          >
            <div className="bg-gradient-to-r from-slate-700/90 to-slate-800/90 px-6 py-4 rounded-2xl mr-12 backdrop-blur-sm border border-slate-600/30">
              <div className="flex items-center space-x-3">
                <div className="flex space-x-1">
                  {[0, 1, 2].map((i) => (
                    <motion.div
                      key={i}
                      className="w-3 h-3 bg-blue-400 rounded-full"
                      animate={{ y: [0, -10, 0] }}
                      transition={{ repeat: Infinity, duration: 0.8, delay: i * 0.15 }}
                    />
                  ))}
                </div>
                <motion.span 
                  className="text-sm text-slate-300"
                  animate={{ opacity: [0.5, 1, 0.5] }}
                  transition={{ repeat: Infinity, duration: 1.5 }}
                >
                  AI is crafting your elite strategy...
                </motion.span>
              </div>
            </div>
          </motion.div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Mobile-Optimized Input Area */}
      <motion.div 
        className="fixed bottom-16 left-0 right-0 z-30 px-3 pb-2"
        style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
        initial={{ y: 100 }}
        animate={{ y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="bg-slate-800/95 backdrop-blur-md rounded-full border border-slate-700/50 shadow-xl">
          <div className="flex items-center px-4 py-3 gap-3">
            
            {/* Voice Input Button */}
            <motion.button
              type="button"
              onClick={() => {
                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                if (!SpeechRecognition) return alert("Speech not supported");
                const recognition = new SpeechRecognition();
                recognition.lang = 'en-US';
                recognition.onresult = (event) => {
                  setInputValue(event.results[0][0].transcript);
                };
                recognition.start();
              }}
              className="w-8 h-8 bg-purple-500 hover:bg-purple-600 text-white rounded-full flex items-center justify-center transition-colors"
              whileTap={{ scale: 0.95 }}
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
              </svg>
            </motion.button>
            
            {/* Text Input Field */}
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="What's your market belief?"
              className="flex-1 bg-transparent text-white placeholder-slate-400 focus:outline-none text-base"
              disabled={isLoading}
            />
            
            {/* Send Button */}
            <motion.button
              onClick={handleSend}
              disabled={!inputValue.trim() || isLoading}
              className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors ${
                inputValue.trim() && !isLoading 
                  ? 'bg-blue-500 hover:bg-blue-600 text-white' 
                  : 'bg-slate-700 text-slate-500'
              }`}
              whileTap={{ scale: 0.95 }}
            >
              {isLoading ? (
                <svg className="w-4 h-4 animate-spin" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 4V2A10 10 0 0 0 2 12h2a8 8 0 0 1 8-8z"/>
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                </svg>
              )}
            </motion.button>
          </div>
        </div>
      </motion.div>
      
      {/* Portfolio Modal */}
      {showPortfolioModal && (
        <PortfolioModal
          isOpen={showPortfolioModal}
          onClose={() => setShowPortfolioModal(false)}
          BACKEND_URL={BACKEND_URL}
        />
      )}
     
      {/* Persistent Bottom Navigation */}
      <BottomNavigation 
        onPortfolioClick={() => setShowPortfolioModal(true)}
      />
    </div>
  );
};

export default EnhancedChatInterface;
