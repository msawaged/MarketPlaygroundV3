// App.js
// This is the main entry point of your React app. It renders the BeliefForm component
// which lets the user input a market belief and see an AI-generated strategy.

import React from 'react';
import BeliefForm from './components/BeliefForm'; // Import our form component

function App() {
  return (
    <div style={{ padding: '2rem', fontFamily: 'Arial, sans-serif' }}>
      {/* Main Title */}
      <h1 style={{ fontSize: '2rem', marginBottom: '1rem' }}>
        🚀 MarketPlayground
      </h1>

      {/* Short Description */}
      <p style={{ fontSize: '1rem', marginBottom: '2rem' }}>
        Enter your belief and watch the strategy unfold
      </p>

      {/* Belief Input Form */}
      <BeliefForm />
    </div>
  );
}

export default App;
