// frontend/src/components/StrategyOpsPanel.jsx
import React from 'react';
import { Link } from 'react-router-dom'; // ✅ Import Link for safe routing

function StrategyOpsPanel() {
  return (
    <div
      style={{
        backgroundColor: '#0f172a',
        color: '#f8fafc',
        minHeight: '100vh',
        padding: '2rem',
        fontFamily: 'Arial, sans-serif',
      }}
    >
      {/* 🔙 Back Button */}
      <Link to="/">
        <button
          style={{
            backgroundColor: '#f43f5e',
            color: '#fff',
            padding: '0.4rem 0.8rem',
            borderRadius: '6px',
            border: 'none',
            cursor: 'pointer',
            marginBottom: '1rem',
            fontWeight: 'bold',
          }}
        >
          ⬅️ Back to Main App
        </button>
      </Link>

      {/* 🛠️ Panel Header */}
      <h1 style={{ fontSize: '2rem', fontWeight: 'bold', marginBottom: '1rem' }}>
        ⚙️ Strategy Ops Panel
      </h1>

      {/* 📘 Description */}
      <p style={{ color: '#94a3b8' }}>
        This is your live internal dashboard for inspecting strategy logic, model outputs, and AI pipeline debugging.
      </p>

      {/* 🔧 Placeholder Modules */}
      <div
        style={{
          marginTop: '2rem',
          backgroundColor: '#1e293b',
          padding: '1.5rem',
          borderRadius: '8px',
          boxShadow: '0 0 12px rgba(100, 116, 139, 0.4)',
        }}
      >
        <p>✅ Future modules will go here:</p>
        <ul style={{ marginTop: '1rem', paddingLeft: '1.2rem' }}>
          <li>🔍 Strategy Distribution Visuals</li>
          <li>📊 Accuracy / Confidence Tracking</li>
          <li>🏆 Leaderboard Drilldown</li>
          <li>📈 Outcome Tracker Debugging</li>
        </ul>
      </div>
    </div>
  );
}

export default StrategyOpsPanel;
