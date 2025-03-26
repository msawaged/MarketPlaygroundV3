import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, Button, StyleSheet, TouchableOpacity, Alert } from 'react-native';
import { getBTCPrice } from '../utils/getPrice';

export default function HomeScreen() {
  const [price, setPrice] = useState(69000);
  const [stake, setStake] = useState('');
  const [direction, setDirection] = useState('yes');
  const [balance, setBalance] = useState(1000); // 💰 starting balance

  useEffect(() => {
    const fetchPrice = async () => {
      const livePrice = await getBTCPrice();
      if (livePrice) setPrice(livePrice);
    };

    fetchPrice();
    const interval = setInterval(fetchPrice, 5000);
    return () => clearInterval(interval);
  }, []);

  const handlePlaceBet = () => {
    const stakeAmount = parseFloat(stake);

    if (isNaN(stakeAmount) || stakeAmount <= 0) {
      Alert.alert('Invalid Stake', 'Please enter a valid dollar amount.');
      return;
    }

    if (stakeAmount > balance) {
      Alert.alert('Insufficient Funds', 'You do not have enough balance.');
      return;
    }

    // Subtract the stake
    setBalance((prev) => prev - stakeAmount);

    // Simulate win/loss (50/50 chance for now)
    const won = Math.random() > 0.5;

    if (won) {
      const payout = stakeAmount * 1.9; // stake + 90%
      setTimeout(() => {
        Alert.alert('You Won!', `You earned $${payout.toFixed(2)}`);
        setBalance((prev) => prev + payout);
      }, 500);
    } else {
      setTimeout(() => {
        Alert.alert('You Lost', `You lost your $${stakeAmount.toFixed(2)} stake.`);
      }, 500);
    }

    setStake('');
  };

  return (
    <View style={styles.container}>
      <Text style={styles.balance}>Balance: ${balance.toFixed(2)}</Text>
      <Text style={styles.title}>Binary Betting</Text>
      <Text style={styles.label}>Asset: BTC/USD</Text>
      <Text style={styles.price}>Current Price: ${price}</Text>

      <View style={styles.row}>
        <TouchableOpacity
          style={[styles.choice, direction === 'yes' && styles.activeChoice]}
          onPress={() => setDirection('yes')}
        >
          <Text style={styles.choiceText}>Yes</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.choice, direction === 'no' && styles.activeChoice]}
          onPress={() => setDirection('no')}
        >
          <Text style={styles.choiceText}>No</Text>
        </TouchableOpacity>
      </View>

      <TextInput
        style={styles.input}
        placeholder="Stake Amount ($)"
        keyboardType="numeric"
        value={stake}
        onChangeText={setStake}
      />

      <Button title="Place Bet" onPress={handlePlaceBet} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: 20, backgroundColor: '#fff' },
  title: { fontSize: 28, fontWeight: 'bold', marginBottom: 10, textAlign: 'center' },
  balance: { fontSize: 20, fontWeight: 'bold', marginBottom: 20, textAlign: 'center', color: '#2ecc71' },
  label: { fontSize: 18, marginBottom: 8 },
  price: { fontSize: 24, marginBottom: 20 },
  row: { flexDirection: 'row', justifyContent: 'space-around', marginBottom: 20 },
  choice: {
    paddingVertical: 10,
    paddingHorizontal: 30,
    backgroundColor: '#eee',
    borderRadius: 10,
  },
  activeChoice: {
    backgroundColor: '#2e86de',
  },
  choiceText: {
    fontSize: 18,
    color: '#fff',
  },
  input: {
    borderWidth: 1,
    borderColor: '#ccc',
    borderRadius: 10,
    padding: 10,
    marginBottom: 20,
    fontSize: 16,
  },
});

