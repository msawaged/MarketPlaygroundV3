// TurboFlipScreen.js

import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Alert } from 'react-native';
import { useBalance } from '../context/BalanceContext'; // Custom hook to access balance
import { useUser } from '../context/UserContext';         // Custom hook to access user info

// TurboFlipScreen lets the user flip a coin and adjusts balance based on win/loss.
const TurboFlipScreen = () => {
  // Access balance and its update function from BalanceContext
  const { balance, updateBalance } = useBalance();
  // Access the user's nickname from UserContext
  const { nickname } = useUser();

  // Local state to store game result
  const [result, setResult] = useState(null);
  const stake = 10; // Fixed bet amount

  // Function to simulate coin flip game
  const handleFlip = () => {
    if (balance < stake) {
      Alert.alert("Insufficient Funds", "You don't have enough balance to place this bet.");
      return;
    }
    const win = Math.random() < 0.5; // Randomly win or lose
    const newBalance = win ? balance + stake : balance - stake;
    updateBalance(newBalance);
    setResult(win ? "WIN" : "LOSS");
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Turbo Flip</Text>
      <Text style={styles.info}>Player: {nickname ? nickname : "Guest"}</Text>
      <Text style={styles.info}>Balance: ${balance}</Text>
      <TouchableOpacity style={styles.button} onPress={handleFlip}>
        <Text style={styles.buttonText}>Flip the Coin ($10)</Text>
      </TouchableOpacity>
      {result && (
        <Text style={[styles.result, result === "WIN" ? styles.win : styles.loss]}>
          You {result}!
        </Text>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 20,
  },
  info: {
    fontSize: 18,
    color: '#fff',
    marginBottom: 10,
  },
  button: {
    backgroundColor: '#1e90ff',
    padding: 15,
    borderRadius: 10,
  },
  buttonText: {
    color: '#fff',
    fontSize: 18,
    fontWeight: 'bold',
  },
  result: {
    fontSize: 24,
    marginTop: 20,
  },
  win: {
    color: 'green',
  },
  loss: {
    color: 'red',
  },
});

// IMPORTANT: Ensure the component is exported as default.
export default TurboFlipScreen;

