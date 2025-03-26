import React, { useState, useEffect } from 'react';
import { View, Text, Button, StyleSheet } from 'react-native';

const RangeRunnerScreen = () => {
  const [startingPrice, setStartingPrice] = useState(69000); // placeholder
  const [currentPrice, setCurrentPrice] = useState(69000);
  const [range, setRange] = useState(50); // user will try to stay inside +/- this range
  const [countdown, setCountdown] = useState(10);
  const [gameState, setGameState] = useState('idle');
  const [result, setResult] = useState(null);

  // 🎮 Start game and simulate price movement
  const startGame = () => {
    setGameState('running');
    setCountdown(10);
    setStartingPrice(currentPrice);
    setResult(null);
  };

  // ⏱ Price drift simulation while game is running
  useEffect(() => {
    let interval;
    if (gameState === 'running') {
      interval = setInterval(() => {
        const movement = Math.floor(Math.random() * 11) - 5; // Simulate price drift
        setCurrentPrice((prev) => prev + movement);
        setCountdown((prev) => {
          if (prev <= 1) {
            clearInterval(interval);
            const delta = Math.abs(currentPrice - startingPrice);
            setResult(delta <= range ? '✅ You stayed in range!' : '❌ You broke the range!');
            setGameState('done');
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [gameState]);

  return (
    <View style={styles.container}>
      <Text style={styles.header}>📉 Range Runner</Text>
      <Text style={styles.subtext}>Stay within ${range} of the starting price</Text>
      <Text style={styles.price}>Starting: ${startingPrice}</Text>
      <Text style={styles.price}>Current: ${currentPrice}</Text>

      {gameState === 'idle' && (
        <Button title="Start Game" onPress={startGame} />
      )}

      {gameState === 'running' && (
        <Text style={styles.countdown}>⏱️ {countdown}s</Text>
      )}

      {result && (
        <Text style={[styles.result, { color: result.includes('✅') ? 'green' : 'red' }]}>{result}</Text>
      )}
    </View>
  );
};

export default RangeRunnerScreen;

const styles = StyleSheet.create({
  container: {
    flex: 1,
    paddingTop: 80,
    paddingHorizontal: 24,
    alignItems: 'center',
    backgroundColor: '#fff',
  },
  header: {
    fontSize: 24,
    fontWeight: 'bold',
  },
  subtext: {
    fontSize: 16,
    color: '#555',
    marginVertical: 10,
  },
  price: {
    fontSize: 20,
    marginVertical: 6,
  },
  countdown: {
    fontSize: 28,
    color: 'orange',
    marginVertical: 20,
  },
  result: {
    fontSize: 24,
    fontWeight: 'bold',
    marginTop: 20,
  },
});

