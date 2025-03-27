import React, { createContext, useState } from 'react';

// 🎯 This stores all bet outcomes during this session
export const BetHistoryContext = createContext();

export const BetHistoryProvider = ({ children }) => {
  const [history, setHistory] = useState([]);

  // ✅ Call this from any game when a bet finishes
  const addBetToHistory = (bet) => {
    setHistory((prev) => [bet, ...prev]); // Add newest to top
  };

  return (
    <BetHistoryContext.Provider value={{ history, addBetToHistory }}>
      {children}
    </BetHistoryContext.Provider>
  );
};

