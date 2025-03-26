import React, { useState } from 'react';
import { View, Text, TextInput, Button, StyleSheet, TouchableOpacity } from 'react-native';

export default function HomeScreen() {
  const [price, setPrice] = useState(68942.57); // mock BTC price
  const [stake, setStake] = useState('');
  const [direction, setDirection] = useState('yes');

  const handlePlaceBet = () => {
    alert(`Placing ${direction.toUpperCase()} bet with $${stake} on BTC being above target`);
  };

  return (
    <View style={styles.container}>
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
  title: { fontSize: 28, fontWeight: 'bold', marginBottom: 20, textAlign: 'center' },
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
