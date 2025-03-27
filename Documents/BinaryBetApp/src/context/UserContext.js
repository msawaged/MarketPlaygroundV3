import React, { createContext, useState } from 'react';

// Create the context
export const UserContext = createContext();

// Create the provider
export const UserContextProvider = ({ children }) => {
  const [balance, setBalance] = useState(1000); // Initial balance
  const [username, setUsername] = useState(''); // New: store user's nickname

  return (
    <UserContext.Provider value={{ balance, setBalance, username, setUsername }}>
      {children}
    </UserContext.Provider>
  );
};

