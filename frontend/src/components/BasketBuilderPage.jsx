// frontend/src/components/BasketBuilderPage.jsx
import React, { useState } from 'react';
import { FiMic } from 'react-icons/fi';

const BasketBuilderPage = () => {
  const [goalText, setGoalText] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // ✅ Speech Recognition Setup
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
          body: JSON.stringify({ goal: goalText }),
        }
      );
  
      const data = await res.json();
  
      if (!res.ok) {
        // ✅ Show backend error message clearly
        const errorMessage = typeof data.detail === 'string'
          ? data.detail
          : JSON.stringify(data);
        throw new Error(errorMessage);
      }
  
      setResult(data); // ✅ Save result for rendering
      setError(null);  // ✅ Clear any old errors
    } catch (err) {
      console.error('❌ Backend error:', err);
  
      // ✅ Fix [object Object] issue
      const displayError =
        typeof err.message === 'string' ? err.message : JSON.stringify(err);
  
      setError(displayError);
      setResult(null);
    }
  };
  
  return (
    <div className="min-h-screen bg-gray-950 text-white p-6 flex flex-col items-center">
      <h1 className="text-3xl font-bold mb-4">🧺 Asset Basket Builder</h1>
      <p className="mb-6 text-gray-300 text-center max-w-xl">
        Describe your investment goal or allocation (e.g., "70% stocks, 30% bonds for moderate growth").
      </p>

      {/* Speech + Text Input */}
      <div className="w-full max-w-lg flex flex-col gap-4">
        <textarea
          rows="4"
          className="w-full p-4 rounded-xl bg-gray-800 text-white focus:outline-none"
          placeholder="Enter your investment goal..."
          value={goalText}
          onChange={(e) => setGoalText(e.target.value)}
        />
        <div className="flex justify-between items-center">
          <button
            className={`flex items-center gap-2 px-4 py-2 rounded-xl ${isListening ? 'bg-red-600' : 'bg-blue-600'} hover:opacity-90`}
            onClick={handleMicClick}
          >
            <FiMic /> {isListening ? 'Listening...' : 'Speak Goal'}
          </button>
          <button
            className="bg-green-600 px-6 py-2 rounded-xl hover:bg-green-700"
            onClick={handleSubmit}
          >
            Generate Basket
          </button>
        </div>
      </div>

      {/* 🔴 Error display */}
      {error && (
        <div className="mt-6 text-red-400 font-semibold text-center">
          ⚠️ {error}
        </div>
      )}

      {/* ✅ Result display */}
      {result && (
        <div className="mt-8 bg-gray-800 p-6 rounded-2xl shadow-xl w-full max-w-xl">
          <h2 className="text-xl font-bold mb-4 text-white">📊 Suggested Asset Basket</h2>
          <ul className="list-disc list-inside text-gray-300 space-y-1">
            {result.basket?.map((item, index) => (
              <li key={index}>
                <span className="font-semibold text-white">{item.ticker}</span>: {item.allocation}%
              </li>
            ))}
          </ul>
          {result.explanation && (
            <p className="mt-4 text-sm text-gray-400 italic">{result.explanation}</p>
          )}
        </div>
      )}
    </div>
  );
};

export default BasketBuilderPage;
