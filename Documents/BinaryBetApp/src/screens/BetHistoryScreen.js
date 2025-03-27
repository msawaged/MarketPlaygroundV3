import React, { useContext } from 'react';
import { View, Text, FlatList, StyleSheet } from 'react-native';
import { BetHistoryContext } from '../context/BetHistoryContext';

const BetHistoryScreen = () => {
  const { history } = useContext(BetHistoryContext);

  // 🔁 Renders each past bet as a card in the list
  const renderItem = ({ item }) => (
    <View style={[styles.card, item.result === 'win' ? styles.win : styles.loss]}>
      <Text style={styles.game}>🎮 {item.game}</Text>
      <Text style={styles.amount}>Stake: ${item.amount}</Text>
      <Text style={styles.outcome}>{item.result === 'win' ? '✅ WON' : '❌ LOST'}</Text>
      <Text style={styles.payout}>Payout: ${item.payout}</Text>
      <Text style={styles.time}>⏱ {item.time}</Text>
    </View>
  );

  return (
    <View style={styles.container}>
      <Text style={styles.title}>📜 Bet History</Text>
      {history.length === 0 ? (
        <Text style={styles.empty}>No bets yet. Play a game to get started!</Text>
      ) : (
        <FlatList
          data={history}
          keyExtractor={(item, index) => index.toString()}
          renderItem={renderItem}
        />
      )}
    </View>
  );
};

export default BetHistoryScreen;

// 💅 Basic styling for history layout
const styles = StyleSheet.create({
  container: {
    flex: 1,
    paddingTop: 60,
    paddingHorizontal: 20,
    backgroundColor: '#f4f4f4',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    textAlign: 'center',
    marginBottom: 20,
  },
  card: {
    borderRadius: 16,
    padding: 16,
    marginBottom: 14,
    shadowColor: '#000',
    shadowOpacity: 0.1,
    shadowOffset: { width: 0, height: 2 },
    shadowRadius: 6,
    elevation: 4,
  },
  win: {
    backgroundColor: '#e0f8e0',
    borderLeftWidth: 6,
    borderLeftColor: '#34c759',
  },
  loss: {
    backgroundColor: '#fde2e2',
    borderLeftWidth: 6,
    borderLeftColor: '#ff3b30',
  },
  game: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 4,
  },
  amount: {
    fontSize: 16,
  },
  payout: {
    fontSize: 16,
    marginTop: 4,
  },
  outcome: {
    fontSize: 16,
    fontWeight: 'bold',
    marginTop: 6,
  },
  time: {
    fontSize: 12,
    color: '#888',
    marginTop: 6,
  },
  empty: {
    textAlign: 'center',
    fontSize: 16,
    marginTop: 30,
    color: '#555',
  },
});

