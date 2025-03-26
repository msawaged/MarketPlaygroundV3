import React, { createContext, useState, useContext } from 'react';

// 🧠 Create a context object to hold balance state
const BalanceContext = createContext();

// 🏦 Create a provider that wraps the app and shares balance globally
export const BalanceProvider = ({ children }) => {
  const [balance, setBalance] = useState(1000); // 💵 Starting balance

  // ➕ Increase balance (e.g., win a bet)
  const increaseBalance = (amount) => {
    setBalance((prev) => prev + amount);
  };

  // ➖ Decrease balance (e.g., place a bet)
  const decreaseBalance = (amount) => {
    setBalance((prev) => prev - amount);
  };

  return (
    <BalanceContext.Provider
      value={{
        balance,
        increaseBalance,
        decreaseBalance,
      }}
    >
      {children}
    </BalanceContext.Provider>
  );
};

// 🧩 Custom hook for using balance easily anywhere in the app
export const useBalance = () => useContext(BalanceContext);

