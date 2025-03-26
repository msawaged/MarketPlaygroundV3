import React from 'react';
import { View, Text, FlatList, TouchableOpacity, StyleSheet } from 'react-native';
import { useBalance } from '../context/BalanceContext'; // 💰 Use global balance

// 🔧 Simulated market data — we’ll wire to real API later
const markets = [
  { id: 'btc', name: 'BTC/USD', price: 69000 },
  { id: 'eth', name: 'ETH/USD', price: 3500 },
  { id: 'sol', name: 'SOL/USD', price: 180 },
];

const MarketPlaygroundScreen = ({ navigation }) => {
  const { balance } = useBalance();

  // 🧭 Navigate to a chosen game screen based on button click
  const handleSelectGame = (marketId, game) => {
    if (game === 'turbo') navigation.navigate('TurboFlip');
    if (game === 'linebreaker') navigation.navigate('LineBreaker');
    if (game === 'rangerunner') navigation.navigate('RangeRunner');
  };

  // 📦 Render each market card with three game launch buttons
  const renderMarket = ({ item }) => (
    <View style={styles.card}>
      <Text style={styles.marketName}>{item.name}</Text>
      <Text style={styles.marketPrice}>${item.price}</Text>

      {/* 🎮 Turbo Flip Button */}
      <TouchableOpacity
        style={styles.button}
        onPress={() => handleSelectGame(item.id, 'turbo')}
      >
        <Text style={styles.buttonText}>▶ Play Turbo Flip</Text>
      </TouchableOpacity>

      {/* 🎮 Line Breaker Button */}
      <TouchableOpacity
        style={[styles.button, styles.lineBreakerBtn]}
        onPress={() => handleSelectGame(item.id, 'linebreaker')}
      >
        <Text style={styles.buttonText}>🚀 Play LineBreaker</Text>
      </TouchableOpacity>

      {/* 🎮 Range Runner Button */}
      <TouchableOpacity
        style={[styles.button, styles.rangeRunnerBtn]}
        onPress={() => handleSelectGame(item.id, 'rangerunner')}
      >
        <Text style={styles.buttonText}>📉 Play RangeRunner</Text>
      </TouchableOpacity>
    </View>
  );

  return (
    <View style={styles.container}>
      <View style={styles.balanceBox}>
        <Text style={styles.balanceText}>Balance: ${balance}</Text>
      </View>

      <Text style={styles.header}>🎯 Market Playground</Text>

      <FlatList
        data={markets}
        keyExtractor={(item) => item.id}
        renderItem={renderMarket}
        contentContainerStyle={styles.list}
      />
    </View>
  );
};

export default MarketPlaygroundScreen;

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f9f9f9',
    paddingTop: 50,
    paddingHorizontal: 16,
  },
  balanceBox: {
    marginBottom: 10,
    alignItems: 'center',
  },
  balanceText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#444',
  },
  header: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 24,
    textAlign: 'center',
  },
  list: {
    paddingBottom: 40,
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 20,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOpacity: 0.1,
    shadowOffset: { width: 0, height: 2 },
    shadowRadius: 6,
    elevation: 4,
  },
  marketName: {
    fontSize: 20,
    fontWeight: 'bold',
  },
  marketPrice: {
    fontSize: 16,
    marginTop: 4,
    color: '#555',
  },
  button: {
    backgroundColor: '#2e86de',
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 10,
    marginTop: 10,
  },
  lineBreakerBtn: {
    backgroundColor: '#4caf50',
  },
  rangeRunnerBtn: {
    backgroundColor: '#ff9800',
  },
  buttonText: {
    fontSize: 16,
    color: '#fff',
    fontWeight: '600',
    textAlign: 'center',
  },
});

