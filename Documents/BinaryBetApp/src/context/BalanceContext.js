// src/context/BalanceContext.js

import React, { createContext, useContext, useState } from 'react';

// Create the BalanceContext
export const BalanceContext = createContext();

// Provider component to wrap your app with balance state
export const BalanceProvider = ({ children }) => {
  const [balance, setBalance] = useState(1000); // Starting balance

  // updateBalance: function to update balance
  const updateBalance = (newBalance) => {
    setBalance(newBalance);
  };

  return (
    <BalanceContext.Provider value={{ balance, updateBalance }}>
      {children}
    </BalanceContext.Provider>
  );
};

// Custom hook to use balance context
export const useBalance = () => {
  const context = useContext(BalanceContext);
  if (!context) {
    throw new Error('useBalance must be used within a BalanceProvider');
  }
  return context;
};

