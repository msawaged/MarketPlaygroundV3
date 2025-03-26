import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, TextInput, Alert } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { getBTCPrice } from '../utils/getPrice';

export default function RangeReaperScreen({ navigation }) {
  const [price, setPrice] = useState(null);
  const [range, setRange] = useState({ low: null, high: null });
  const [countdown, setCountdown] = useState(null);
  const [finalPrice, setFinalPrice] = useState(null);
  const [result, setResult] = useState(null);
  const [stake, setStake] = useState('');
  const [balance, setBalance] = useState(1000);

  // Fetch BTC price on interval
  useEffect(() => {
    const fetchPrice = async () => {
      const livePrice = await getBTCPrice();
      if (livePrice) setPrice(livePrice);
    };
    fetchPrice();
    const interval = setInterval(fetchPrice, 5000);
    return () => clearInterval(interval);
  }, []);

  // Countdown timer logic
  useEffect(() => {
    if (countdown === 0) settleBet();
    if (countdown && countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown]);

  // Load balance from storage
  useEffect(() => {
    const load = async () => {
      const saved = await AsyncStorage.getItem('balance');
      if (saved !== null) setBalance(parseFloat(saved));
    };
    load();
  }, []);

  // Save balance to storage
  useEffect(() => {
    AsyncStorage.setItem('balance', balance.toString());
  }, [balance]);

  const placeBet = () => {
    const stakeAmount = parseFloat(stake);
    if (isNaN(stakeAmount) || stakeAmount <= 0) {
      Alert.alert('Invalid Stake', 'Enter a valid dollar amount.');
      return;
    }
    if (stakeAmount > balance) {
      Alert.alert('Insufficient Balance', 'Not enough funds to place this bet.');
      return;
    }

    const buffer = 100;
    const low = price - buffer;
    const high = price + buffer;
    setRange({ low, high });
    setCountdown(30);
    setResult(null);
    setFinalPrice(null);
    setBalance((prev) => prev - stakeAmount);
  };

  const settleBet = async () => {
    const fetchedPrice = await getBTCPrice();
    const won = fetchedPrice >= range.low && fetchedPrice <= range.high;
    const payout = won ? parseFloat(stake) * 1.9 : 0;
    if (won) setBalance((prev) => prev + payout);
    setFinalPrice(fetchedPrice);
    setResult(won ? 'win' : 'lose');
    setStake('');
  };

  return (
    <View style={styles.container}>
      <Text style={styles.header}>Range Reaper: BTC/USD</Text>
      <Text style={styles.balance}>Balance: ${balance.toFixed(2)}</Text>
      <Text style={styles.label}>Live Price: ${price ?? '...'}</Text>

      <TextInput
        style={styles.input}
        placeholder="Stake Amount ($)"
        keyboardType="numeric"
        value={stake}
        onChangeText={setStake}
      />

      {range.low === null ? (
        <TouchableOpacity style={styles.betButton} onPress={placeBet}>
          <Text style={styles.betText}>Place Bet</Text>
        </TouchableOpacity>
      ) : (
        <View style={styles.statusBox}>
          <Text style={styles.rangeText}>Goal: Stay between</Text>
          <Text style={styles.rangeText}>Low: ${range.low.toFixed(2)}</Text>
          <Text style={styles.rangeText}>High: ${range.high.toFixed(2)}</Text>
          <Text style={styles.countdown}>⏱ {countdown}s</Text>
        </View>
      )}

      {result && (
        <View style={styles.resultBox}>
          <Text style={styles.resultText}>Final Price: ${finalPrice.toFixed(2)}</Text>
          <Text style={[styles.resultText, { color: result === 'win' ? 'green' : 'red' }]}>You {result === 'win' ? 'WIN 🎉' : 'LOSE ❌'}</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20, backgroundColor: '#fff', justifyContent: 'center' },
  header: { fontSize: 22, fontWeight: 'bold', textAlign: 'center', marginBottom: 10 },
  balance: { fontSize: 18, textAlign: 'center', color: 'green', marginBottom: 10 },
  label: { fontSize: 16, textAlign: 'center', marginBottom: 10 },
  input: {
    borderWidth: 1,
    borderColor: '#ccc',
    padding: 10,
    borderRadius: 8,
    marginBottom: 15,
    fontSize: 16,
  },
  betButton: {
    backgroundColor: '#27ae60',
    padding: 15,
    borderRadius: 10,
    alignItems: 'center',
    marginTop: 10,
  },
  betText: { color: '#fff', fontSize: 18 },
  statusBox: { alignItems: 'center', marginVertical: 20 },
  rangeText: { fontSize: 16 },
  countdown: { fontSize: 24, fontWeight: 'bold', color: '#2c3e50', marginTop: 10 },
  resultBox: { alignItems: 'center', marginTop: 20 },
  resultText: { fontSize: 20, fontWeight: 'bold' },
});

