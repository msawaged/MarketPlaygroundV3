// 📁 FILE: frontend/src/components/ToolSelectorPage.jsx
// ✅ Main navigation hub for MarketPlayground
// This component serves as the landing page where users choose their tool
// Routes: /select-tool (default redirect from /)

import React from 'react';
import { useNavigate } from 'react-router-dom';

const ToolSelectorPage = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gray-900 text-white flex flex-col items-center justify-center p-6">
      {/* 🎯 Main Header */}
      <h1 className="text-4xl font-bold mb-8 text-center">
        🧠 Welcome to MarketPlayground
      </h1>
      
      {/* 📝 Subtitle */}
      <p className="text-lg mb-10 text-gray-300 text-center">
        Choose how you want to explore the market today:
      </p>
      
      {/* 🎮 Tool Selection Buttons */}
      <div className="flex flex-col gap-6 w-full max-w-md">
        
        {/* 💬 Chat Interface - Interactive AI chat for trading strategies */}
        <button
          className="bg-purple-600 hover:bg-purple-700 text-white font-semibold py-3 px-6 rounded-2xl shadow-md"
          onClick={() => navigate('/chat')}
        >
          💬 chat.test.App
        </button>
        
        {/* 🎯 Strategy Generator - Main belief-to-strategy engine */}
        <button
          className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-2xl shadow-md"
          onClick={() => navigate('/generator')}
        >
          🎯 AI Strategy Generator
        </button>
        
        {/* 🚀 Basket Builder - Portfolio construction tool */}
        <button
          className="bg-green-600 hover:bg-green-700 text-white font-semibold py-3 px-6 rounded-2xl shadow-md"
          onClick={() => navigate('/basket-builder')}
        >
          🚀 Asset Basket Builder
        </button>
        
      </div>
    </div>
  );
};

export default ToolSelectorPage;