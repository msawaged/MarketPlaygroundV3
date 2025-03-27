import React, { createContext, useState } from 'react';

// Create the context
export const UserContext = createContext();

// Create the provider
export const UserContextProvider = ({ children }) => {
  const [balance, setBalance] = useState(1000); // Starting balance

  return (
    <UserContext.Provider value={{ balance, setBalance }}>
      {children}
    </UserContext.Provider>
  );
};

