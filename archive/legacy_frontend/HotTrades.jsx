// frontend/src/components/HotTrades.jsx
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';  // ✅ Enables redirect to Home

/**
 * ✅ Smart backend URL routing (local + cloud-safe)
 */
const BACKEND_URL =
  import.meta.env.VITE_BACKEND_URL ||
  (window.location.hostname === 'localhost'

    ? 'http://localhost:8000'
    : 'https://marketplayground-backend.onrender.com');

function HotTradesPage() {
  const [hotTrades, setHotTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  // ✅ Fetch hot trades from backend
  useEffect(() => {
    fetch(`${BACKEND_URL}/hot_trades`)
      .then((res) => res.json())
      .then((data) => {
        setHotTrades(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load hot trades:', err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="text-white text-center mt-10">
        🔥 Loading Hot Trades...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0d1117] text-white px-6 py-10">

      {/* ✅ Home button */}
      <div className="max-w-screen-xl mx-auto mb-6">
        <button
          onClick={() => navigate('/')}
          className="bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded shadow"
        >
          🏠 Home
        </button>
      </div>

      {/* ✅ Header */}
      <h2 className="text-4xl font-bold mb-8 text-center">🔥 Hot Trades</h2>

      {/* ✅ Empty state */}
      {hotTrades.length === 0 ? (
        <div className="text-center text-gray-400">No trades available.</div>
      ) : (
        <div className="max-w-screen-xl mx-auto grid grid-cols-1 sm:grid-cols-2 gap-8">
          {hotTrades.map((trade, index) => (
            <div
              key={index}
              className="bg-gray-900 rounded-xl p-6 border border-gray-700 shadow-md hover:shadow-lg hover:scale-[1.01] transition-all"
            >
              <h3 className="text-2xl font-semibold text-yellow-400 mb-2">{trade.type}</h3>
              <p className="text-sm mb-2 italic text-gray-400">Usage Count: {trade.usage_count}</p>

              {/* ✅ Trade legs */}
              {trade.trade_legs && Array.isArray(trade.trade_legs) && (
                <ul className="mb-3 pl-5 list-disc text-sm text-gray-300">
                  {trade.trade_legs.map((leg, i) => (
                    <li key={i}>
                      {typeof leg === 'string' ? leg : JSON.stringify(leg)}
                    </li>
                  ))}
                </ul>
              )}

              {/* ✅ Metrics */}
              <p className="text-sm text-green-300 mb-1">
                🎯 Target Return: {trade.target_return}
              </p>
              <p className="text-sm text-red-300 mb-1">
                💥 Max Loss: {trade.max_loss}
              </p>
              <p className="text-sm text-gray-300 mb-2">
                ⏳ Time to Target: {trade.time_to_target}
              </p>

              {/* ✅ Explanation */}
              <p className="text-sm text-gray-200">🧠 {trade.explanation}</p>

            <p className="text-sm text-gray-200">🧠 {trade.explanation}</p>

{/* ✅ Execute Trade Button */}
<div className="mt-4 text-right">
  <button
    className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 transition"
    onClick={() => handleExecuteTrade(trade)}
  >
    🚀 Execute Trade
  </button>

</div>  // closes the card
              
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default HotTradesPage;


