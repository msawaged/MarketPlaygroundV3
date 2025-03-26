import React from 'react';
import { View, Text, FlatList, TouchableOpacity, StyleSheet } from 'react-native';
import { useBalance } from '../context/BalanceContext'; // 💰 Import balance hook

// 🧪 Simulated market data — later this will be real-time
const markets = [
  { id: 'btc', name: 'BTC/USD', price: 69000 },
  { id: 'eth', name: 'ETH/USD', price: 3500 },
  { id: 'sol', name: 'SOL/USD', price: 180 },
];

const MarketPlaygroundScreen = ({ navigation }) => {
  const { balance } = useBalance(); // 🧠 Access the user's current balance

  const handleSelectMarket = (marketId) => {
    navigation.navigate('TurboFlip');
  };

  const renderMarket = ({ item }) => (
    <TouchableOpacity style={styles.card} onPress={() => handleSelectMarket(item.id)}>
      <Text style={styles.marketName}>{item.name}</Text>
      <Text style={styles.marketPrice}>${item.price}</Text>
      <Text style={styles.playText}>▶ Play Turbo Flip</Text>
    </TouchableOpacity>
  );

  return (
    <View style={styles.container}>
      {/* 💰 Balance shown at top */}
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
  playText: {
    fontSize: 16,
    marginTop: 12,
    color: '#2e86de',
    fontWeight: '600',
  },
});

export default MarketPlaygroundScreen;

