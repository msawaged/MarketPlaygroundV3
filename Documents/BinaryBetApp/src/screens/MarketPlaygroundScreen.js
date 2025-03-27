import React, { useContext } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { UserContext } from '../context/UserContext';

const MarketPlaygroundScreen = () => {
  const navigation = useNavigation();
  const { balance } = useContext(UserContext); // ✅ Safely pull balance from context

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>Market Playground 🧠</Text>
      <Text style={styles.balance}>Balance: ${balance}</Text>

      <TouchableOpacity
        style={styles.gameButton}
        onPress={() => navigation.navigate('TurboFlip')}
      >
        <Text style={styles.gameText}>Turbo Flip ⚡</Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.gameButton}
        onPress={() => navigation.navigate('LineBreaker')}
      >
        <Text style={styles.gameText}>Line Breaker 💥</Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.gameButton}
        onPress={() => navigation.navigate('RangeReaper')}
      >
        <Text style={styles.gameText}>Range Reaper ☠️</Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.gameButton}
        onPress={() => navigation.navigate('RangeRunner')}
      >
        <Text style={styles.gameText}>Range Runner 🏃‍♂️</Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.historyButton}
        onPress={() => navigation.navigate('BetHistory')}
      >
        <Text style={styles.historyText}>📜 View Bet History</Text>
      </TouchableOpacity>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flexGrow: 1,
    padding: 24,
    alignItems: 'center',
    backgroundColor: '#0f0f0f',
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 10,
  },
  balance: {
    fontSize: 18,
    color: '#ccc',
    marginBottom: 30,
  },
  gameButton: {
    backgroundColor: '#1e90ff',
    paddingVertical: 14,
    paddingHorizontal: 30,
    borderRadius: 12,
    marginVertical: 10,
    width: '100%',
    alignItems: 'center',
  },
  gameText: {
    fontSize: 18,
    color: '#fff',
    fontWeight: '600',
  },
  historyButton: {
    marginTop: 30,
    padding: 12,
  },
  historyText: {
    color: '#aaa',
    textDecorationLine: 'underline',
  },
});

export default MarketPlaygroundScreen;

