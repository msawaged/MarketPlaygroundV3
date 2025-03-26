import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, Button, StyleSheet, TouchableOpacity, FlatList, Alert } from 'react-native';
import { getBTCPrice } from '../utils/getPrice';

export default function HomeScreen() {
  const [price, setPrice] = useState(69000);
  const [stake, setStake] = useState('');
  const [direction, setDirection] = useState('yes');
  const [balance, setBalance] = useState(1000);
  const [bets, setBets] = useState([]);

  // Fetch live price every 5 sec (optional)
  useEffect(() => {
    const fetchPrice = async () => {
      const livePrice = await getBTCPrice();
      if (livePrice) setPrice(livePrice);
    };

    fetchPrice();
    const interval = setInterval(fetchPrice, 5000);
    return () => clearInterval(interval);
  }, []);

  const handlePlaceBet = async () => {
    const stakeAmount = parseFloat(stake);
    if (isNaN(stakeAmount) || stakeAmount <= 0) {
      Alert.alert('Invalid Stake', 'Enter a valid dollar amount.');
      return;
    }
    if (stakeAmount > balance) {
      Alert.alert('Insufficient Funds', 'Not enough balance.');
      return;
    }

    const strikePrice = price;
    const createdAt = Date.now();

    const newBet = {
      id: createdAt,
      direction,
      stake: stakeAmount,
      strikePrice,
      createdAt,
      expiresAt: createdAt + 10000, // 10 seconds
      status: 'pending',
      result: null,
    };

    setBalance((prev) => prev - stakeAmount);
    setBets((prev) => [...prev, newBet]);
    setStake('');

    // Schedule settlement
    setTimeout(async () => {
      const currentPrice = await getBTCPrice();
      const didWin =
        (direction === 'yes' && currentPrice > strikePrice) ||
        (direction === 'no' && currentPrice < strikePrice);

      const payout = didWin ? stakeAmount * 1.9 : 0;

      setBets((prevBets) =>
        prevBets.map((b) =>
          b.id === newBet.id
            ? {
                ...b,
                status: 'settled',
                result: didWin ? 'won' : 'lost',
                resolvedPrice: currentPrice,
              }
            : b
        )
      );

      if (didWin) {
        Alert.alert('You Won!', `Payout: $${payout.toFixed(2)}`);
        setBalance((prev) => prev + payout);
      } else {
        Alert.alert('You Lost', 'Better luck next time.');
      }
    }, 10000);
  };

  const renderBet = ({ item }) => (
    <View style={styles.betCard}>
      <Text>🕓 {new Date(item.createdAt).toLocaleTimeString()}</Text>
      <Text>Stake: ${item.stake}</Text>
      <Text>Direction: {item.direction.toUpperCase()}</Text>
      <Text>Strike: ${item.strikePrice}</Text>
      {item.status === 'settled' && (
        <>
          <Text>Result: {item.result}</Text>
          <Text>Resolved: ${item.resolvedPrice}</Text>
        </>
      )}
    </View>
  );

  return (
    <View style={styles.container}>
      <Text style={styles.balance}>Balance: ${balance.toFixed(2)}</Text>
      <Text style={styles.title}>BTC Binary Game</Text>
      <Text style={styles.label}>BTC/USD Price: ${price}</Text>

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

      <Text style={styles.subTitle}>Your Bets</Text>
      <FlatList
        data={[...bets].reverse()}
        keyExtractor={(item) => item.id.toString()}
        renderItem={renderBet}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20, backgroundColor: '#fff' },
  balance: { fontSize: 20, fontWeight: 'bold', marginBottom: 10, color: '#2ecc71', textAlign: 'center' },
  title: { fontSize: 24, fontWeight: 'bold', marginBottom: 10, textAlign: 'center' },
  subTitle: { fontSize: 20, marginTop: 30, marginBottom: 10, fontWeight: 'bold' },
  label: { fontSize: 16, marginBottom: 8 },
  row: { flexDirection: 'row', justifyContent: 'space-around', marginBottom: 20 },
  choice: {
    paddingVertical: 10,
    paddingHorizontal: 30,
    backgroundColor: '#ccc',
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
  betCard: {
    padding: 10,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 10,
  },
});

