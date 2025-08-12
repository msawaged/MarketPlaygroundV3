import React, { useState, useEffect } from 'react';

const StockTicker = () => {
  const [tickerData, setTickerData] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  // Sample data for now
  const sampleTickerData = [
    { symbol: 'SPY', price: 637.18, change: 1.25, changePercent: 0.20 },
    { symbol: 'AAPL', price: 150.25, change: -0.75, changePercent: -0.50 },
    { symbol: 'TSLA', price: 245.67, change: 2.13, changePercent: 0.87 },
    { symbol: 'NVDA', price: 892.45, change: 15.23, changePercent: 1.74 },
    { symbol: 'BTC-USD', price: 45230.12, change: 523.45, changePercent: 1.17 }
  ];

  useEffect(() => {
    setTimeout(() => {
      setTickerData(sampleTickerData);
      setIsLoading(false);
    }, 1000);
  }, []);

  if (isLoading) {
    return (
      <div className="bg-slate-900 text-white py-2 text-center">
        <span className="text-slate-400">Loading market data...</span>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 text-white py-2 overflow-hidden border-b border-slate-700">
      <div className="flex space-x-8 animate-pulse">
        {tickerData.map((stock, index) => (
          <div key={index} className="flex items-center space-x-2 whitespace-nowrap">
            <span className="font-bold text-blue-400">{stock.symbol}</span>
            <span className="font-semibold">${stock.price}</span>
            <span className={stock.change >= 0 ? 'text-green-400' : 'text-red-400'}>
              {stock.change >= 0 ? '▲' : '▼'} {Math.abs(stock.change).toFixed(2)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default StockTicker;