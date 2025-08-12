// 📁 FILE: frontend/src/components/ChatInterface.jsx
// 🎯 PURPOSE: Main chat interface component with persistent mobile UI elements
// 🔧 FEATURES: Fixed header/footer, real-time trading chat, strategy cards
// 📱 MOBILE: Optimized for iOS/Android with safe area handling

import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

// 🌐 BACKEND URL CONFIGURATION
// 📍 Handles localhost, local network (10.0.0.x, 192.168.x), and production URLs
const BACKEND_URL = window.location.hostname === 'localhost' 
  ? 'http://localhost:8000' 
  : window.location.hostname.startsWith('10.0.0') || window.location.hostname.startsWith('192.168')
    ? `http://${window.location.hostname}:8000`  // Use same IP for backend
    : 'https://marketplayground-backend.onrender.com';

// 📊 STOCK TICKER COMPONENT
// 🎯 PURPOSE: Real-time market data display at top of interface
// 🔄 TODO: Replace with live Alpaca/Finnhub feed instead of static data
const StockTicker = () => {
  const [position, setPosition] = useState(0);
  
  // 💾 SAMPLE TICKER DATA - Replace with real API call
  const tickerData = [
    { symbol: 'SPY', price: 637.18, change: 1.25, changePercent: 0.20 },
    { symbol: 'AAPL', price: 150.25, change: -0.75, changePercent: -0.50 },
    { symbol: 'TSLA', price: 245.67, change: 2.13, changePercent: 0.87 },
    { symbol: 'NVDA', price: 892.45, change: 15.23, changePercent: 1.74 },
    { symbol: 'BTC-USD', price: 45230.12, change: 523.45, changePercent: 1.17 }
  ];

  // 🔄 ANIMATE TICKER MOVEMENT
  useEffect(() => {
    const interval = setInterval(() => {
      setPosition(prev => prev <= -100 ? 100 : prev - 0.5);
    }, 50);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="bg-slate-900 text-white py-2 overflow-hidden relative">
      {/* 📱 SCROLLING TICKER */}
      <div 
        className="flex space-x-8 whitespace-nowrap transition-transform duration-75 ease-linear"
        style={{ transform: `translateX(${position}%)` }}
      >
        {/* 🔄 TRIPLE DATA FOR SEAMLESS LOOP */}
        {[...tickerData, ...tickerData, ...tickerData].map((stock, index) => (
          <div key={index} className="flex items-center space-x-2 whitespace-nowrap">
            {/* 🏷️ STOCK SYMBOL */}
            <span className="font-bold text-blue-400">{stock.symbol}</span>
            {/* 💲 CURRENT PRICE */}
            <span className="font-semibold">${stock.price.toLocaleString()}</span>
            {/* 📈📉 PRICE CHANGE INDICATOR */}
            <span className={stock.change >= 0 ? 'text-green-400' : 'text-red-400'}>
              {stock.change >= 0 ? '▲' : '▼'} {Math.abs(stock.change).toFixed(2)}
            </span>
            <span className={`text-xs ${stock.change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              ({stock.changePercent >= 0 ? '+' : ''}{stock.changePercent.toFixed(2)}%)
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

// 📈 STRATEGY-SPECIFIC CHART COMPONENT
// 🎯 PURPOSE: Dynamic chart visualization based on asset class and strategy
// 📊 FEATURES: Options P&L, Stock targets, Bond yields, Crypto volatility
const SimulatedChart = ({ ticker, strategyType, price, confidence, assetClass, strikePrice, direction }) => {
  const [animationFrame, setAnimationFrame] = useState(0);
  
  // 🔄 ANIMATION LOOP FOR DYNAMIC EFFECTS
  useEffect(() => {
    const interval = setInterval(() => {
      setAnimationFrame(prev => (prev + 1) % 360);
    }, 100);
    return () => clearInterval(interval);
  }, []);

  // 📊 OPTIONS CHART: P&L DIAGRAM
  const renderOptionsChart = () => {
    const currentPrice = parseFloat(price) || 637;
    const strike = parseFloat(strikePrice) || 700; // USE REAL STRIKE FROM BACKEND
    const premium = currentPrice * 0.05; // Estimated premium
    
    // 📈 Generate P&L curve points
    const pnlPoints = [];
    for (let i = 0; i <= 100; i++) {
      const stockPrice = currentPrice * 0.5 + (currentPrice * 1.0 * i / 100);
      let pnl;
      
      if (strategyType.toLowerCase().includes('put')) {
        // PUT OPTION P&L
        pnl = stockPrice < strike ? (strike - stockPrice - premium) : -premium;
      } else {
        // CALL OPTION P&L  
        pnl = stockPrice > strike ? (stockPrice - strike - premium) : -premium;
      }
      
      pnlPoints.push({ x: i, price: stockPrice, pnl: Math.max(pnl, -premium * 2) });
    }
    
    const maxPnl = Math.max(...pnlPoints.map(p => p.pnl));
    const minPnl = Math.min(...pnlPoints.map(p => p.pnl));
    const pnlRange = maxPnl - minPnl || 1;

    return (
      <div className="h-32 bg-slate-700 rounded p-2 relative">
        <svg width="100%" height="100%" className="absolute inset-0">
          {/* 📈 P&L CURVE */}
          <polyline
            fill="none"
            stroke={strategyType.toLowerCase().includes('put') ? "#ef4444" : "#22c55e"}
            strokeWidth="2"
            points={pnlPoints.map((point, index) => {
              const x = (index / (pnlPoints.length - 1)) * 100;
              const y = ((maxPnl - point.pnl) / pnlRange) * 80 + 10;
              return `${x},${y}`;
            }).join(' ')}
          />
          
          {/* 🎯 BREAKEVEN LINE */}
          <line x1="0" y1="50%" x2="100%" y2="50%" stroke="#94a3b8" strokeWidth="1" strokeDasharray="3,3" />
          
          {/* 💥 STRIKE PRICE INDICATOR */}
          <line x1="70%" y1="0" x2="70%" y2="100%" stroke="#fbbf24" strokeWidth="2" />
          <text x="72%" y="15%" fill="#fbbf24" fontSize="10">Strike: ${strike}</text>
          
          {/* 📍 CURRENT PRICE INDICATOR */}
          <line x1="50%" y1="0" x2="50%" y2="100%" stroke="#3b82f6" strokeWidth="2" />
          <text x="52%" y="95%" fill="#3b82f6" fontSize="10">Current: ${currentPrice}</text>
        </svg>
        
        {/* 📊 PROFIT/LOSS LABELS */}
        <div className="absolute top-1 left-1 text-xs text-green-400">Profit</div>
        <div className="absolute bottom-6 left-1 text-xs text-red-400">Loss</div>
        <div className="absolute top-1 right-1 text-xs text-yellow-400">
          {(confidence * 100).toFixed(0)}% Confidence
        </div>
      </div>
    );
  };

  // 📈 STOCKS/ETF CHART: PRICE TARGETS
  const renderStockChart = () => {
    const currentPrice = parseFloat(price) || 637;
    const targetHigh = currentPrice * (direction === 'bullish' ? 1.15 : 0.95);
    const targetLow = currentPrice * (direction === 'bullish' ? 0.95 : 1.05);
    
    return (
      <div className="h-32 bg-slate-700 rounded p-2 relative">
        <div className="flex items-end justify-center h-full space-x-1">
          {/* 📊 PRICE BARS WITH TARGETS */}
          {Array.from({ length: 12 }, (_, i) => {
            const height = 30 + Math.sin((animationFrame + i * 30) * 0.02) * 20 + (confidence * 30);
            const isTarget = i === 3 || i === 9;
            return (
              <div
                key={i}
                className={`rounded-t transition-all duration-200 ${
                  isTarget ? 'bg-yellow-400' : 
                  direction === 'bullish' ? 'bg-gradient-to-t from-green-600 to-green-400' :
                  direction === 'bearish' ? 'bg-gradient-to-t from-red-600 to-red-400' :
                  'bg-gradient-to-t from-blue-600 to-blue-400'
                }`}
                style={{
                  height: `${Math.max(height, 10)}px`,
                  width: '6px'
                }}
              />
            );
          })}
        </div>
        
        {/* 🎯 PRICE TARGET LABELS */}
        <div className="absolute top-1 left-1 text-xs text-green-400">
          Target: ${targetHigh.toFixed(0)}
        </div>
        <div className="absolute bottom-6 left-1 text-xs text-red-400">
          Support: ${targetLow.toFixed(0)}
        </div>
        <div className="absolute top-1 right-1 text-xs text-blue-400">
          Current: ${currentPrice}
        </div>
      </div>
    );
  };

  // 🏛️ BONDS CHART: YIELD CURVE
  const renderBondsChart = () => {
    const yieldCurve = [2.1, 2.3, 2.7, 3.1, 3.4, 3.6, 3.8, 4.0];
    
    return (
      <div className="h-32 bg-slate-700 rounded p-2 relative">
        <svg width="100%" height="100%" className="absolute inset-0">
          {/* 📈 YIELD CURVE */}
          <polyline
            fill="none"
            stroke="#8b5cf6"
            strokeWidth="3"
            points={yieldCurve.map((yield_, index) => {
              const x = (index / (yieldCurve.length - 1)) * 100;
              const y = ((4.5 - yield_) / 2.5) * 80 + 10;
              return `${x},${y}`;
            }).join(' ')}
          />
          
          {/* 📊 YIELD POINTS */}
          {yieldCurve.map((yield_, index) => {
            const x = (index / (yieldCurve.length - 1)) * 100;
            const y = ((4.5 - yield_) / 2.5) * 80 + 10;
            return (
              <circle
                key={index}
                cx={x}
                cy={y}
                r="3"
                fill="#a855f7"
                className="animate-pulse"
              />
            );
          })}
          
          <text x="50%" y="95%" textAnchor="middle" fill="#8b5cf6" fontSize="10">
            Yield Curve: {(confidence * 4).toFixed(1)}% Est.
          </text>
        </svg>
      </div>
    );
  };

  // 🪙 CRYPTO CHART: VOLATILITY BANDS
  const renderCryptoChart = () => {
    const currentPrice = parseFloat(price) || 45230;
    
    return (
      <div className="h-32 bg-slate-700 rounded p-2 relative">
        <div className="flex items-center justify-center h-full">
          {/* 🌊 VOLATILITY WAVES */}
          <div className="relative w-full h-full">
            {Array.from({ length: 5 }, (_, i) => (
              <div
                key={i}
                className="absolute w-full border-2 rounded-full opacity-30"
                style={{
                  borderColor: ['#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#10b981'][i],
                  height: `${20 + i * 15}%`,
                  top: `${10 + i * 8}%`,
                  left: '10%',
                  right: '10%',
                  animation: `pulse ${2 + i * 0.5}s infinite`
                }}
              />
            ))}
            
            {/* 💰 PRICE CENTER */}
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <div className="text-lg font-bold text-orange-400">
                  ${currentPrice.toLocaleString()}
                </div>
                <div className="text-xs text-slate-300">
                  Vol: {(confidence * 150).toFixed(0)}%
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // 🎨 MAIN CHART CONTAINER
  return (
    <div className="bg-slate-600 p-4 rounded-lg mt-2">
      <div className="text-center">
        {/* 🏷️ CHART HEADER */}
        <div className="text-lg font-bold text-white">{ticker}</div>
        <div className="text-2xl text-green-400">${price}</div>
        <div className="text-sm text-slate-300 mt-1">{strategyType}</div>
        <div className="text-xs text-slate-400 mb-3">
          📈 Confidence: {(confidence * 100).toFixed(1)}% | {assetClass?.toUpperCase()}
        </div>
        
        {/* 🎯 DYNAMIC CHART BASED ON ASSET CLASS */}
        {assetClass === 'options' && renderOptionsChart()}
        {(assetClass === 'equity' || assetClass === 'etf') && renderStockChart()}
        {assetClass === 'bonds' && renderBondsChart()}
        {assetClass === 'crypto' && renderCryptoChart()}
        
        {/* 📊 MINI STATS GRID */}
        <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
          <div>
            <div className="text-slate-400">Strategy</div>
            <div className="text-blue-400 font-semibold">{strategyType}</div>
          </div>
          <div>
            <div className="text-slate-400">Asset</div>
            <div className="text-white font-semibold">{assetClass?.toUpperCase()}</div>
          </div>
          <div>
            <div className="text-slate-400">Score</div>
            <div className={`font-semibold ${
              confidence > 0.7 ? 'text-green-400' : 
              confidence > 0.4 ? 'text-yellow-400' : 'text-red-400'
            }`}>
              {(confidence * 100).toFixed(0)}%
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// 💬 MAIN CHAT INTERFACE COMPONENT
// 🎯 PURPOSE: Core trading chat interface with AI strategy recommendations
// 📱 MOBILE: Fixed header/footer, responsive design, iOS safe areas
const ChatInterface = () => {
  // 📨 CHAT MESSAGE STATE
  // 💾 Stores all user/AI messages with timestamps and strategy data
  const [messages, setMessages] = useState([
    {
      id: 1,
      type: 'ai',
      content: 'Hi! I\'m your AI trading strategist. Tell me what you believe about the market!',
      timestamp: new Date()
    }
  ]);
  
  // ✍️ USER INPUT STATE
  const [inputValue, setInputValue] = useState('');
  
  // ⏳ LOADING STATE - Shows when AI is processing
  const [isLoading, setIsLoading] = useState(false);
  
  // 📍 REF FOR AUTO-SCROLLING TO BOTTOM
  const messagesEndRef = useRef(null);

  // 📜 AUTO-SCROLL TO BOTTOM FUNCTION
  // 🎯 PURPOSE: Keeps chat scrolled to newest message
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // 🔄 AUTO-SCROLL EFFECT
  // 📍 Triggers whenever messages array changes
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

// 🚀 MAIN MESSAGE SEND HANDLER
// 🎯 PURPOSE: Processes user input and gets AI strategy recommendation
// 📡 FLOW: User message → Backend API → AI response → Update UI
const handleSend = async () => {
    // 🚫 Exit early if input is empty
    if (!inputValue.trim()) return;
  
    // 📝 CREATE USER MESSAGE OBJECT
    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: inputValue,
      timestamp: new Date()
    };
  
    // 💾 ADD USER MESSAGE TO CHAT HISTORY
    setMessages(prev => [...prev, userMessage]);
    
    // 📦 STORE BELIEF TEXT FOR API CALL
    const belief = inputValue;
    
    // 🧹 CLEAR INPUT FIELD
    setInputValue('');
    
    // ⏳ START LOADING STATE
    setIsLoading(true);
  
    try {
      console.log('🔗 API Call:', `${BACKEND_URL}/strategy/process_belief`);
      
      // 🌐 MAKE API REQUEST TO BACKEND
      const res = await fetch(`${BACKEND_URL}/strategy/process_belief`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          belief: belief,
          user_id: 'chat_user',
        }),
      });
  
      // 📊 PARSE JSON RESPONSE FROM BACKEND
      const data = await res.json();
      console.log('📥 Backend Response:', data);
  
      // 🤖 CREATE AI RESPONSE MESSAGE WITH ENHANCED STRATEGY DATA
      const aiResponse = {
        id: Date.now() + 1,
        type: 'ai',
        content: `Based on your belief, I recommend a **${data.strategy?.type || 'Strategy'}**.`,
        
        // 🎯 ENHANCED STRATEGY OBJECT WITH ALL BACKEND DATA
        strategy: {
          // 📋 BASIC STRATEGY INFO
          type: data.strategy?.type || 'Unknown',
          // 🔧 FIX: Use strategy ticker if available, fallback to main ticker
          ticker: data.strategy?.trade_legs?.[0]?.ticker || data.ticker || 'N/A',
          confidence: data.confidence || 0.5,
          explanation: data.strategy?.explanation || 'No explanation available',
          price: data.price_info?.latest || 0,
          assetClass: data.asset_class || 'options',
          
          // 📈 ADDITIONAL STRATEGY METADATA  
          direction: data.direction || 'neutral',
          tags: data.tags || [],
          goal_type: data.goal_type || 'Unspecified',
          risk_profile: data.risk_profile || 'Moderate',
          expiry_date: data.expiry_date || 'N/A',
          trade_legs: data.strategy?.trade_legs || [],
          source: data.strategy?.source || 'unknown',
          
          // 🎯 BACKEND DYNAMIC FIELDS MAPPING
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
  
      // 💬 ADD AI RESPONSE TO CHAT HISTORY
      setMessages(prev => [...prev, aiResponse]);
      
    } catch (error) {
      console.error('❌ API Error:', error);
      
      // 🚨 CREATE ERROR MESSAGE IF API FAILS
      const errorMessage = {
        id: Date.now() + 1,
        type: 'ai',
        content: 'Sorry, I had trouble processing that. Please try again!',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      // ✅ STOP LOADING STATE
      setIsLoading(false);
    }
  };

  // ⌨️ ENTER KEY HANDLER
  // 🎯 PURPOSE: Send message on Enter, allow Shift+Enter for new lines
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // ✅ FUNCTION TO RENDER DYNAMIC FIELDS
  // 🎯 PURPOSE: Shows asset-specific details based on asset class
const renderDynamicFields = (strategy) => {
    const { dynamicFields, assetClass } = strategy;
    
    if (!dynamicFields) return null;
  
    return (
      <div className="mb-3 p-3 bg-slate-700 rounded-lg">
        <h4 className="text-xs font-semibold text-blue-400 mb-2">🎯 Asset-Specific Details</h4>
        
        {assetClass === 'options' && (
          <div className="grid grid-cols-2 gap-2 text-xs">
            {dynamicFields.strike_price && (
              <div><span className="text-slate-400">💥 Strike:</span> <span className="text-white ml-1 font-semibold">{dynamicFields.strike_price}</span></div>
            )}
            {dynamicFields.premium && (
              <div><span className="text-slate-400">💰 Premium:</span> <span className="text-green-400 ml-1 font-semibold">{dynamicFields.premium}</span></div>
            )}
            {dynamicFields.break_even && (
              <div><span className="text-slate-400">⚖️ Break Even:</span> <span className="text-yellow-400 ml-1 font-semibold">{dynamicFields.break_even}</span></div>
            )}
            {dynamicFields.max_profit && (
              <div><span className="text-slate-400">📈 Max Profit:</span> <span className="text-green-400 ml-1 font-semibold">{dynamicFields.max_profit}</span></div>
            )}
            {dynamicFields.theta && (
              <div><span className="text-slate-400">⏰ Theta:</span> <span className="text-orange-400 ml-1 font-semibold">{dynamicFields.theta}</span></div>
            )}
            {dynamicFields.delta && (
              <div><span className="text-slate-400">🔼 Delta:</span> <span className="text-purple-400 ml-1 font-semibold">{dynamicFields.delta}</span></div>
            )}
          </div>
        )}
      </div>
    );
  };

  // 👍👎 FEEDBACK SUBMISSION HANDLER
  // 🎯 PURPOSE: Sends user feedback to backend for model improvement
  const sendFeedback = async (strategy, feedbackType) => {
    try {
      await fetch(`${BACKEND_URL}/feedback/submit_feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          belief: messages.find(m => m.type === 'user')?.content || '',
          strategy: strategy.type,
          feedback: feedbackType,
          user_id: 'chat_user',
        }),
      });
      alert(`${feedbackType === 'good' ? '👍' : '👎'} Feedback sent!`);
    } catch (error) {
      alert('Failed to send feedback');
    }
  };

  // 🎨 MAIN COMPONENT RENDER
  return (
    // 📱 FULL SCREEN CONTAINER WITH DARK THEME
    // 🔧 FIXED: Changed from flex-col to relative positioning for mobile fixes
    <div className="h-screen bg-slate-900 text-white relative">
      
      {/* 📊 FIXED STOCK TICKER AT TOP */}
      {/* 📱 MOBILE: Persistent across all devices, z-index ensures it stays on top */}
      <div className="fixed top-0 left-0 right-0 z-50 bg-slate-900 border-b border-slate-700" 
           style={{ paddingTop: 'env(safe-area-inset-top)' }}>
        <StockTicker />
      </div>

      {/* 🧠 FIXED HEADER WITH APP BRANDING */}
      {/* 📍 POSITIONED: Below ticker, above content */}
      <div className="fixed top-12 left-0 right-0 z-40 bg-slate-800 border-b border-slate-700 p-4">
        <div className="flex items-center gap-3">
          {/* 🎨 APP ICON */}
          <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
            🧠
          </div>
          {/* 📝 APP TITLE AND SUBTITLE */}
          <div>
            <h1 className="font-semibold">MarketPlayground Chat</h1>
            <p className="text-sm text-slate-400">AI Trading Assistant</p>
          </div>
        </div>
      </div>

      {/* 💬 SCROLLABLE MESSAGES AREA */}
      {/* 📱 MOBILE: Padding accounts for fixed header (140px) and footer (120px) */}
      <div className="overflow-y-auto p-4 space-y-4" 
           style={{ 
             paddingTop: '140px',    // Space for ticker + header
             paddingBottom: '120px', // Space for input area
             height: '100vh',        // Full viewport height
             WebkitOverflowScrolling: 'touch' // Smooth scrolling on iOS
           }}>
        
        {/* 🎬 FRAMER MOTION ANIMATIONS */}
        <AnimatePresence>
          {messages.map((message) => (
            <motion.div
              key={message.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {/* 💭 MESSAGE BUBBLE */}
              <div
                className={`max-w-xs lg:max-w-md px-4 py-3 rounded-2xl ${
                  message.type === 'user'
                    ? 'bg-blue-600 text-white'      // 👤 User messages: Blue
                    : 'bg-slate-700 text-slate-100' // 🤖 AI messages: Gray
                }`}
              >
                {/* 📝 MESSAGE TEXT CONTENT */}
                <p className="text-sm">{message.content}</p>
                
                {/* 🎯 STRATEGY CARD (Only for AI messages with strategy data) */}
                {message.strategy && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="mt-3 bg-slate-800 rounded-xl p-4 border border-slate-600"
                  >
                    {/* 🎯 STRATEGY HEADER - HERO INFO */}
                    <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg p-4 mb-4 text-center">
                      <div className="text-2xl font-bold text-white">{message.strategy.type}</div>
                      <div className="text-lg text-blue-100">{message.strategy.ticker}</div>
                      <div className="flex justify-center items-center gap-4 mt-2">
                        <span className={`px-3 py-1 rounded-full text-sm font-bold ${
                          message.strategy.source === 'ml_model' ? 'bg-red-500' : 'bg-green-500'
                        } text-white`}>
                          {message.strategy.source === 'ml_model' ? '🤖 ML' : '🧠 GPT'}
                        </span>
                        <span className="text-2xl font-bold text-yellow-300">
                          {(message.strategy.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>

                    {/* 📊 KEY METRICS GRID - SCANNABLE */}
                    <div className="grid grid-cols-2 gap-3 mb-4">
                      {/* 📈 DIRECTION */}
                      <div className="bg-slate-700 rounded-lg p-3 text-center">
                        <div className="text-xs text-slate-400 uppercase tracking-wide">Direction</div>
                        <div className={`text-lg font-bold ${
                          message.strategy.direction === 'bullish' ? 'text-green-400' :
                          message.strategy.direction === 'bearish' ? 'text-red-400' : 'text-yellow-400'
                        }`}>
                          {message.strategy.direction === 'bullish' ? '📈 BULLISH' :
                           message.strategy.direction === 'bearish' ? '📉 BEARISH' : '⚖️ NEUTRAL'}
                        </div>
                      </div>

                      {/* 💲 CURRENT PRICE */}
                      <div className="bg-slate-700 rounded-lg p-3 text-center">
                        <div className="text-xs text-slate-400 uppercase tracking-wide">Current Price</div>
                        <div className="text-lg font-bold text-green-400">${message.strategy.price}</div>
                      </div>

                      {/* 🎯 ASSET CLASS */}
                      <div className="bg-slate-700 rounded-lg p-3 text-center">
                        <div className="text-xs text-slate-400 uppercase tracking-wide">Asset Class</div>
                        <div className={`text-sm font-bold px-2 py-1 rounded ${
                          message.strategy.assetClass === 'options' ? 'bg-blue-500 text-white' :
                          message.strategy.assetClass === 'equity' ? 'bg-green-500 text-white' :
                          message.strategy.assetClass === 'bonds' ? 'bg-purple-500 text-white' :
                          message.strategy.assetClass === 'crypto' ? 'bg-orange-500 text-white' :
                          'bg-gray-500 text-white'
                        }`}>
                          {message.strategy.assetClass?.toUpperCase()}
                        </div>
                      </div>

                      {/* ⏰ EXPIRY */}
                      <div className="bg-slate-700 rounded-lg p-3 text-center">
                        <div className="text-xs text-slate-400 uppercase tracking-wide">Expiry</div>
                        <div className="text-sm font-bold text-white">{message.strategy.expiry_date}</div>
                      </div>
                    </div>

                    {/* 🎯 OPTIONS-SPECIFIC DATA (Only show for options) */}
                    {message.strategy.assetClass === 'options' && message.strategy.strike_price && (
                      <div className="bg-gradient-to-r from-purple-900 to-blue-900 rounded-lg p-4 mb-4">
                        <h4 className="text-sm font-bold text-purple-200 mb-3">💥 Options Details</h4>
                        <div className="grid grid-cols-2 gap-3">
                          <div className="text-center">
                            <div className="text-xs text-purple-300">Strike Price</div>
                            <div className="text-lg font-bold text-white">${message.strategy.strike_price}</div>
                          </div>
                          {message.strategy.premium && (
                            <div className="text-center">
                              <div className="text-xs text-purple-300">Premium</div>
                              <div className="text-lg font-bold text-green-400">{message.strategy.premium}</div>
                            </div>
                          )}
                          {message.strategy.max_profit && (
                            <div className="text-center">
                              <div className="text-xs text-purple-300">Max Profit</div>
                              <div className="text-sm font-bold text-green-400">{message.strategy.max_profit}</div>
                            </div>
                          )}
                          {message.strategy.max_loss && (
                            <div className="text-center">
                              <div className="text-xs text-purple-300">Max Loss</div>
                              <div className="text-sm font-bold text-red-400">{message.strategy.max_loss}</div>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* 📈 TRADE LEGS - CLEANER DISPLAY */}
                    {message.strategy.trade_legs && message.strategy.trade_legs.length > 0 && (
                      <div className="mb-4">
                        <h4 className="text-sm font-bold text-blue-400 mb-3 flex items-center">
                          📋 Trade Actions
                        </h4>
                        {message.strategy.trade_legs.map((leg, idx) => (
                          <div key={idx} className="bg-slate-700 rounded-lg p-3 mb-2 border-l-4 border-blue-400">
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
                          </div>
                        ))}
                      </div>
                    )}

                    {/* 📄 EXPLANATION - BETTER FORMATTED */}
                    <div className="bg-slate-700 rounded-lg p-4 mb-4">
                      <h4 className="text-sm font-bold text-slate-200 mb-2 flex items-center">
                        🧠 Strategy Explanation
                      </h4>
                      <p className="text-sm text-slate-300 leading-relaxed">{message.strategy.explanation}</p>
                    </div>

                    {/* 📈 CHART COMPONENT */}
                    <div className="mb-4">
                      <SimulatedChart
                        ticker={message.strategy.ticker}
                        strategyType={message.strategy.type}
                        price={message.strategy.price}
                        confidence={message.strategy.confidence}
                        assetClass={message.strategy.assetClass}
                        strikePrice={message.strategy.strike_price}
                        direction={message.strategy.direction}
                      />
                    </div>

                    {/* 🎮 ACTION BUTTONS - BIGGER & BETTER */}
                    <div className="grid grid-cols-3 gap-3">
                      <button 
                        onClick={() => sendFeedback(message.strategy, 'good')}
                        className="bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-white font-bold py-3 px-4 rounded-lg transition-all transform hover:scale-105 shadow-lg"
                      >
                        👍 Good
                      </button>
                      <button 
                        onClick={() => sendFeedback(message.strategy, 'bad')}
                        className="bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 text-white font-bold py-3 px-4 rounded-lg transition-all transform hover:scale-105 shadow-lg"
                      >
                        👎 Bad
                      </button>
                      <button 
                        onClick={() => alert(`🚀 Executing: ${message.strategy.type} on ${message.strategy.ticker}`)}
                        className="bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white font-bold py-3 px-4 rounded-lg transition-all transform hover:scale-105 shadow-lg"
                      >
                        🚀 Execute
                      </button>
                    </div>
                  </motion.div>
                )}
                
                {/* 🕒 MESSAGE TIMESTAMP */}
                <p className="text-xs opacity-60 mt-2">
                  {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </p>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {/* ⏳ LOADING INDICATOR (Shows while AI is thinking) */}
        {isLoading && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex justify-start"
          >
            <div className="bg-slate-700 px-4 py-3 rounded-2xl">
              {/* 💭 ANIMATED DOTS */}
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-slate-400 rounded-full animate-pulse"></div>
                <div className="w-2 h-2 bg-slate-400 rounded-full animate-pulse delay-75"></div>
                <div className="w-2 h-2 bg-slate-400 rounded-full animate-pulse delay-150"></div>
              </div>
            </div>
          </motion.div>
        )}
        
        {/* 📍 SCROLL TARGET: Invisible div at bottom for auto-scroll */}
        <div ref={messagesEndRef} />
      </div>

      {/* ✍️ FIXED INPUT AREA AT BOTTOM */}
      {/* 📱 MOBILE: Persistent input, never scrolls away */}
      <div className="fixed bottom-0 left-0 right-0 z-40 bg-slate-800 border-t border-slate-700 p-4"
           style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}>
        <div className="flex gap-2 items-end">
          {/* 📝 TEXT INPUT AREA */}
          <div className="flex-1">
            <textarea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Tell me your market belief... (e.g. 'Tesla will hit $300')"
              className="w-full bg-slate-700 text-white rounded-2xl px-4 py-3 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-slate-400"
              rows="1"
            />
          </div>
          {/* 🎤 SPEECH RECOGNITION BUTTON */}
          <button
            type="button"
            onClick={() => {
              const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
              if (!SpeechRecognition) return alert("Speech Recognition not supported on this browser.");
              const recognition = new SpeechRecognition();
              recognition.lang = 'en-US';
              recognition.interimResults = false;
              recognition.maxAlternatives = 1;
              recognition.onstart = () => console.log('🎤 Speech recognition started');
              recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                console.log('🎤 Speech result:', transcript);
                setInputValue(transcript);
              };
              recognition.onerror = (event) => {
                console.error('🎤 Speech error:', event.error);
                alert('Speech recognition error: ' + event.error);
              };
              recognition.start();
            }}
            className="bg-slate-600 hover:bg-slate-500 text-white px-4 py-3 rounded-2xl transition-colors"
          >
            🎤
          </button>
          {/* 📤 SEND BUTTON */}
          <button
            onClick={handleSend}
            disabled={!inputValue.trim() || isLoading}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 disabled:cursor-not-allowed text-white rounded-2xl px-6 py-3 transition-colors"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;