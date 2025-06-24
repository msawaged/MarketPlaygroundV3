// src/components/StrategyForm.js

import React, { useState } from 'react';

const StrategyForm = () => {
  const [belief, setBelief] = useState('');
  const [response, setResponse] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();

    try {
      const res = await fetch('http://127.0.0.1:8000/process_belief', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ belief }),
      });

      const data = await res.json();
      setResponse(data);
    } catch (err) {
      console.error('Error:', err);
    }
  };

  return (
    <div className="p-4 max-w-xl mx-auto">
      <h2 className="text-2xl font-semibold mb-4">🎯 Enter a Market Belief</h2>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={belief}
          onChange={(e) => setBelief(e.target.value)}
          placeholder="e.g. AAPL will go up next week"
          className="w-full p-2 border rounded mb-4"
        />
        <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded">
          Submit
        </button>
      </form>

      {response && (
        <div className="mt-6 bg-gray-100 p-4 rounded shadow">
          <h3 className="text-xl font-bold mb-2">📈 Suggested Strategy:</h3>
          <pre>{JSON.stringify(response, null, 2)}</pre>
        </div>
      )}
    </div>
  );
};

export default StrategyForm;
