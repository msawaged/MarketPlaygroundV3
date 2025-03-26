import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, Button, StyleSheet, TouchableOpacity, FlatList, Alert } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { getBTCPrice } from '../utils/getPrice';

export default function HomeScreen({ navigation }) {
  const [price, setPrice] = useState(69000);
  const [stake, setStake] = useState('');
  const [direction, setDirection] = useState('yes');
  const [balance, setBalance] = useState(1000);
  const [bets, setBets] = useState([]);
  const [duration, setDuration] = useState(10);
  const [activeBet, setActiveBet] = useState(null);
  const [countdown, setCountdown] = useState(null);
  const [resultMessage, setResultMessage] = useState('');

  useEffect(() => {
    const fetchPrice = async () => {
      const livePrice = await getBTCPrice();
      if (livePrice) setPrice(livePrice);
    };

    const loadData = async () => {
      try {
        const savedBalance = await AsyncStorage.getItem('balance');
        const savedBets = await AsyncStorage.getItem('bets');
        if (savedBalance !== null) setBalance(parseFloat(savedBalance));
        if (savedBets !== null) setBets(JSON.parse(savedBets));
      } catch (err) {
        console.log('Failed to load saved data:', err);
      }
    };

    fetchPrice();
    loadData();
    const interval = setInterval(fetchPrice, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    AsyncStorage.setItem('balance', balance.toString());
  }, [balance]);

  useEffect(() => {
    AsyncStorage.setItem('bets', JSON.stringify(bets));
  }, [bets]);

  useEffect(() => {
    if (countdown === 0) {
      settleActiveBet();
    }
    if (countdown && countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown]);

  const handlePlaceBet = () => {
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
    const expiresAt = createdAt + duration * 1000;

    const bet = {
      id: createdAt,
      direction,
      stake: stakeAmount,
      strikePrice,
      createdAt,
      expiresAt,
      duration,
      status: 'pending',
      result: null,
    };

    setBalance((prev) => prev - stakeAmount);
    setActiveBet(bet);
    setCountdown(duration);
    setStake('');
    setResultMessage('');
  };

  const settleActiveBet = async () => {
    const currentPrice = await getBTCPrice();
    const bet = activeBet;
    const didWin =
      (bet.direction === 'yes' && currentPrice > bet.strikePrice) ||
      (bet.direction === 'no' && currentPrice < bet.strikePrice);

    const payout = didWin ? bet.stake * 1.9 : 0;

    const resolvedBet = {
      ...bet,
      status: 'settled',
      result: didWin ? 'won' : 'lost',
      resolvedPrice: currentPrice,
    };

    setBets((prev) => [...prev, resolvedBet]);
    setActiveBet(null);
    setCountdown(null);
    if (didWin) {
      setBalance((prev) => prev + payout);
      setResultMessage(`🎉 You WON! +$${payout.toFixed(2)}`);
    } else {
      setResultMessage(`❌ You LOST. Better luck next time.`);
    }
  };

  const renderBet = ({ item }) => (
    <View style={styles.betCard}>
      <Text>🕓 {new Date(item.createdAt).toLocaleTimeString()}</Text>
      <Text>Stake: ${item.stake}</Text>
      <Text>Direction: {item.direction.toUpperCase()}</Text>
      <Text>Strike: ${item.strikePrice}</Text>
      <Text>Result: {item.result?.toUpperCase()}</Text>
      <Text>Resolved Price: ${item.resolvedPrice}</Text>
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

      <Text style={styles.label}>Select Duration:</Text>
      <View style={styles.row}>
        {[10, 30, 60].map((d) => (
          <TouchableOpacity
            key={d}
            style={[styles.choice, duration === d && styles.activeChoice]}
            onPress={() => setDuration(d)}
          >
            <Text style={styles.choiceText}>{d}s</Text>
          </TouchableOpacity>
        ))}
      </View>

      <TextInput
        style={styles.input}
        placeholder="Stake Amount ($)"
        keyboardType="numeric"
        value={stake}
        onChangeText={setStake}
      />

      <Button title="Place Bet" onPress={handlePlaceBet} disabled={!!activeBet} />
      <Button title="Play Turbo Flip" onPress={() => navigation.navigate('TurboFlip')} />

      {activeBet && (
        <View style={styles.statusBox}>
          <Text style={styles.statusText}>Betting ${activeBet.stake} on {activeBet.direction.toUpperCase()}</Text>
          <Text style={styles.statusText}>Strike Price: ${activeBet.strikePrice}</Text>
          <Text style={styles.countdown}>⏱ {countdown}s</Text>
        </View>
      )}

      {resultMessage !== '' && <Text style={styles.result}>{resultMessage}</Text>}

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
    paddingHorizontal: 20,
    backgroundColor: '#ccc',
    borderRadius: 10,
  },
  activeChoice: {
    backgroundColor: '#2e86de',
  },
  choiceText: {
    fontSize: 16,
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
  statusBox: {
    backgroundColor: '#f1f1f1',
    padding: 10,
    marginBottom: 15,
    borderRadius: 8,
    alignItems: 'center'
  },
  statusText: { fontSize: 16 },
  countdown: { fontSize: 24, fontWeight: 'bold', color: '#2c3e50' },
  result: { textAlign: 'center', fontSize: 20, marginVertical: 10, fontWeight: 'bold' },
  betCard: {
    padding: 10,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 10,
  },
});

