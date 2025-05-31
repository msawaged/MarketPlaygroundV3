// src/screens/TestScreen.js

import React, { useEffect, useState } from 'react';
import { View, Text, FlatList, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { fusionScan, playFusion } from '../api/api';

export default function TestScreen() {
  const [fusionList, setFusionList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [roundResult, setRoundResult] = useState(null);

  // Fetch the fusion list on mount
  useEffect(() => {
    (async () => {
      const { fusion, error } = await fusionScan();
      if (!error) setFusionList(fusion);
      setLoading(false);
    })();
  }, []);

  // Handler to play one round
  const handlePlay = async () => {
    const result = await playFusion();
    setRoundResult(result);
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#00FFAA" />
        <Text style={styles.text}>Loading market playground...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.header}>🎯 Top 5 Fusion Trades</Text>
      <FlatList
        data={fusionList}
        keyExtractor={(item) => item.symbol}
        renderItem={({ item }) => (
          <Text style={styles.item}>
            • {item.symbol} — Score: {item.score}
          </Text>
        )}
      />

      <TouchableOpacity style={styles.button} onPress={handlePlay}>
        <Text style={styles.buttonText}>▶️ Play Fusion Round</Text>
      </TouchableOpacity>

      {roundResult && (
        <View style={styles.resultBox}>
          <Text style={styles.resultHeader}>{roundResult.message}</Text>
          <Text>Option: {roundResult.optionTrade.symbol}</Text>
          <Text>Futures: {roundResult.futuresTrade.symbol}</Text>
          <Text>Outcome: {roundResult.result.result}</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20, backgroundColor: '#111' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#111' },
  header: { color: '#00FFAA', fontSize: 22, marginBottom: 10, fontWeight: 'bold' },
  item: { color: '#fff', fontSize: 16, marginVertical: 4 },
  text: { color: '#fff', marginTop: 8 },
  button: {
    marginTop: 20, padding: 12, backgroundColor: '#00FFAA', borderRadius: 6, alignItems: 'center'
  },
  buttonText: { color: '#111', fontSize: 16, fontWeight: 'bold' },
  resultBox: { marginTop: 20, padding: 12, backgroundColor: '#222', borderRadius: 6 },
  resultHeader: { color: '#00FFAA', fontSize: 18, marginBottom: 8, fontWeight: 'bold' },
});
