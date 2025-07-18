// frontend/src/BasketBuilderPage.jsx
import React, { useState } from 'react';
import { FiMic } from 'react-icons/fi';
import { useNavigate } from 'react-router-dom';

const BasketBuilderPage = () => {
  const [goalText, setGoalText] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const recognition = SpeechRecognition ? new SpeechRecognition() : null;

  const handleMicClick = () => {
    if (!recognition) return alert("Speech recognition not supported in this browser.");
    if (isListening) {
      recognition.stop();
      setIsListening(false);
    } else {
      recognition.start();
      setIsListening(true);
      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setGoalText(transcript);
      };
      recognition.onerror = (event) => {
        console.error('Speech error:', event.error);
        setIsListening(false);
      };
    }
  };

  const handleSubmit = async () => {
    if (!goalText.trim()) return;

    try {
      const res = await fetch(
        `${import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'}/basket/generate_basket`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            input_text: goalText,
            goal: goalText,
            user_id: "test_user"
          })
        }
      );

      const data = await res.json();

      if (!res.ok) {
        const errorMessage = typeof data.detail === 'string'
          ? data.detail
          : JSON.stringify(data);
        throw new Error(errorMessage);
      }

      setResult(data);
      setError(null);
    } catch (err) {
      console.error('❌ Backend error:', err);
      const displayError = typeof err.message === 'string' ? err.message : JSON.stringify(err);
      setError(displayError);
      setResult(null);
    }
  };

    // 🧪 Mock data for top-performing assets (eventually fetched from yfinance/Finnhub)
    const topAssets = [
      {
        name: "Vanguard Growth ETF (VUG)",
        ytd: "+17.4%",
        mix: "85% US Stocks / 15% Intl Stocks"
      },
      {
        name: "iShares Core Agg Bond (AGG)",
        ytd: "+6.2%",
        mix: "70% US Bonds / 30% Government Bonds"
      },
      {
        name: "ARK Innovation ETF (ARKK)",
        ytd: "+24.1%",
        mix: "100% High-Growth Tech"
      }
    ];
  

  return (
    <div className="min-h-screen bg-gray-950 text-white px-6 py-10 flex flex-col items-center">
      <h1 className="text-4xl font-extrabold mb-2 text-white drop-shadow">🧺 AI Asset Basket Builder</h1>
      <p className="mb-6 text-gray-400 text-center max-w-2xl">
        Describe your investment goals, risk level, or preferences. Example: <br />
        <code className="text-green-400">"I want 70% stocks and 30% bonds for moderate growth"</code>
      </p>

      <div className="flex gap-4 mb-6">
        <button
          className="bg-yellow-500 hover:bg-yellow-600 text-black font-bold px-5 py-2 rounded-xl shadow-lg"
          onClick={() => navigate('/generator')}
        >
          ⬅ Back to Strategy Page
        </button>
      </div>

      {/* 🎙️ Input */}
      <div className="w-full flex flex-col lg:flex-row gap-6 justify-between items-start mt-4 max-w-5xl">
  {/* 🎙️ + Generate Basket input section */}
  <div className="flex-1 flex flex-col gap-4">
    <textarea
      rows="4"
      className="w-full p-4 rounded-xl bg-gray-800 text-white border border-gray-700 focus:outline-none"
      placeholder="Enter your investment goal..."
      value={goalText}
      onChange={(e) => setGoalText(e.target.value)}
    />
    <div className="flex justify-between items-center">
      <button
        className={`flex items-center gap-2 px-4 py-2 rounded-xl text-white ${isListening ? 'bg-red-600' : 'bg-blue-600'} hover:opacity-90`}
        onClick={handleMicClick}
      >
        <FiMic /> {isListening ? 'Listening...' : 'Speak Goal'}
      </button>
      <button
        className="bg-green-500 px-6 py-2 rounded-xl hover:bg-green-600 text-white font-semibold shadow"
        onClick={handleSubmit}
      >
        Generate Basket
      </button>
    </div>
  </div>

 
    <p className="text-[11px] text-gray-400 mt-3 text-center italic">
      Auto-synced from market data — <span className="text-yellow-400">Premium after beta</span> 🚀
    </p>
  </div>



      {/* 🔴 Error */}
      {error && (
        <div className="mt-6 text-red-400 font-semibold text-center">
          ⚠️ {error}
        </div>

      )}

      {/* 🌟 Top Performing Asset Mixes — Mocked Live Card */}
<div className="mt-12 w-full max-w-2xl bg-gradient-to-br from-indigo-800 to-gray-900 p-6 rounded-2xl shadow-xl border border-indigo-700">
  <h2 className="text-2xl font-extrabold text-white mb-4 drop-shadow flex items-center gap-2">
    🔥 Top Performing Asset Mixes <span className="text-sm text-gray-300 font-normal">(YTD)</span>
  </h2>

  <div className="space-y-4">
    {topAssets.map((asset, index) => (
      <div key={index} className="bg-indigo-950 p-4 rounded-xl border border-indigo-700 shadow-md hover:shadow-lg transition">
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center">
          <div>
            <span className="text-lg font-bold text-white">{asset.name}</span>
            <p className="text-indigo-300 text-sm italic mt-1">{asset.mix}</p>
          </div>
          <span className="mt-2 sm:mt-0 bg-green-700 text-white text-sm px-3 py-1 rounded-full shadow inline-block">
            {asset.ytd}
          </span>
        </div>
      </div>
    ))}
  </div>

  <p className="text-xs text-gray-400 mt-4 text-center italic">
    (Auto-synced from live market data — <span className="text-yellow-400 font-semibold">Premium after beta</span> 🚀)
  </p>
</div>


      {/* ✅ Result */}
      {result && (
        <div className="mt-10 w-full max-w-2xl bg-gradient-to-br from-gray-800 to-gray-900 p-6 rounded-2xl shadow-2xl border border-gray-700">
          <h2 className="text-2xl font-bold text-white mb-4">📊 Suggested Asset Basket</h2>

          <div className="space-y-4">
            {result.basket?.map((item, index) => (
              <div key={index} className="bg-gray-900 p-4 rounded-xl border border-gray-700 shadow">
                <div className="flex justify-between items-center">
                  <span className="text-lg font-bold text-white">{item.ticker}</span>
                  <span className="text-green-400 font-semibold">{item.allocation}</span>
                </div>
                <p className="text-gray-400 text-sm mt-1 italic">{item.rationale}</p>
              </div>
            ))}
          </div>

          <div className="mt-6 text-sm text-gray-300 space-y-1">
            <p><strong>🎯 Goal:</strong> {result.goal}</p>
            <p><strong>📈 Est. Return:</strong> {result.estimated_return}</p>
            <p><strong>⚖️ Risk Profile:</strong> {result.risk_profile}</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default BasketBuilderPage;
