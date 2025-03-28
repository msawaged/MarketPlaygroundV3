import React, { createContext, useState, useEffect, useContext } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

// ✅ Create the context object
const UserContext = createContext();

// ✅ Hook to access user context easily
export const useUser = () => useContext(UserContext);

// ✅ Provider component that wraps the app
export const UserProvider = ({ children }) => {
  const [nickname, setNickname] = useState('');
  const [balance, setBalance] = useState(1000); // Default starting balance

  // ✅ Load nickname from AsyncStorage on mount
  useEffect(() => {
    const loadNickname = async () => {
      try {
        const storedNickname = await AsyncStorage.getItem('nickname');
        if (storedNickname) setNickname(storedNickname);
      } catch (error) {
        console.error('Failed to load nickname', error);
      }
    };
    loadNickname();
  }, []);

  return (
    <UserContext.Provider value={{ nickname, setNickname, balance, setBalance }}>
      {children}
    </UserContext.Provider>
  );
};

