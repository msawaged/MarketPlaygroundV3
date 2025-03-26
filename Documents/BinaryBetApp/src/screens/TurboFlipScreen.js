import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { getBTCPrice } from '../utils/getPrice';

export default function TurboFlipScreen({ navigation }) {
  const [price, setPrice] = useState(null);
  const [strikePrice, setStrikePrice] = useState(null);
  const [direction, setDirection] = useState(null);
  const [countdown, setCountdown] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    const fetchPrice = async () => {
      const livePrice = await getBTCPrice();
      if (livePrice) setPrice(livePrice);
    };
    fetchPrice();
    const interval = setInterval(fetchPrice, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (countdown === 0) settleBet();
    if (countdown && countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown]);

  const placeBet = (chosenDirection) => {
    setDirection(chosenDirection);
    setStrikePrice(price);
    setCountdown(30);
    setResult(null);
  };

  const settleBet = async () => {
    const finalPrice = await getBTCPrice();
    let win = false;
    if (direction === 'up' && finalPrice > strikePrice) win = true;
    if (direction === 'down' && finalPrice < strikePrice) win = true;
    setResult({ finalPrice, win });
  };

  return (
    <View style={styles.container}>
      <Text style={styles.header}>Turbo Flip: BTC/USD</Text>
      <Text style={styles.label}>Live Price: ${price ?? '...'}</Text>

      {strikePrice === null ? (
        <View style={styles.buttonRow}>
          <TouchableOpacity style={styles.betButton} onPress={() => placeBet('up')}>
            <Text style={styles.betText}>📈 Up</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.betButton} onPress={() => placeBet('down')}>
            <Text style={styles.betText}>📉 Down</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <View style={styles.statusBox}>
          <Text style={styles.info}>Strike Price: ${strikePrice}</Text>
          <Text style={styles.info}>Countdown: {countdown}s</Text>
        </View>
      )}

      {result && (
        <View style={styles.resultBox}>
          <Text style={styles.resultText}>Final Price: ${result.finalPrice}</Text>
          <Text style={[styles.resultText, { color: result.win ? 'green' : 'red' }]}>
            You {result.win ? 'WIN 🎉' : 'LOSE ❌'}
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20, justifyContent: 'center', backgroundColor: '#fff' },
  header: { fontSize: 24, fontWeight: 'bold', textAlign: 'center', marginBottom: 20 },
  label: { fontSize: 18, textAlign: 'center', marginBottom: 20 },
  buttonRow: { flexDirection: 'row', justifyContent: 'space-around', marginBottom: 20 },
  betButton: { backgroundColor: '#2e86de', padding: 15, borderRadius: 10 },
  betText: { color: '#fff', fontSize: 18 },
  statusBox: { alignItems: 'center', marginVertical: 20 },
  info: { fontSize: 16 },
  resultBox: { alignItems: 'center', marginTop: 30 },
  resultText: { fontSize: 20, fontWeight: 'bold' },
});

