import React, { useState, useEffect } from 'react';
import { View, Text, Button, StyleSheet, Alert } from 'react-native';
import { useBalance } from '../context/BalanceContext'; // 💰 Import balance context

const TurboFlipScreen = () => {
  const [livePrice, setLivePrice] = useState(69000); // Placeholder BTC price
  const [strikePrice, setStrikePrice] = useState(null);
  const [finalPrice, setFinalPrice] = useState(null);
  const [countdown, setCountdown] = useState(3);
  const [gameState, setGameState] = useState('idle');
  const [result, setResult] = useState(null);

  const { balance, increaseBalance, decreaseBalance } = useBalance(); // 🔌 Get balance + actions

  // 🎮 Start the game
  const startFlip = () => {
    const costToPlay = 50;

    if (balance < costToPlay) {
      Alert.alert("Not enough balance", "You need at least $50 to play.");
      return;
    }

    // 💸 Deduct to play
    decreaseBalance(costToPlay);
    setStrikePrice(livePrice);
    setCountdown(3);
    setGameState('running');
    setResult(null);
    setFinalPrice(null);
  };

  // ⏱ Countdown logic
  useEffect(() => {
    let timer;
    if (gameState === 'running' && countdown > 0) {
      timer = setTimeout(() => setCountdown(countdown - 1), 1000);
    } else if (gameState === 'running' && countdown === 0) {
      finishFlip();
    }
    return () => clearTimeout(timer);
  }, [countdown, gameState]);

  // 🎲 Finish the flip with a random up/down outcome
  const finishFlip = () => {
    const priceChange = Math.random() < 0.5 ? -50 : 50;
    const updatedPrice = livePrice + priceChange;

    setFinalPrice(updatedPrice);
    setGameState('result');

    const didWin = updatedPrice > strikePrice;
    setResult(didWin ? 'win' : 'lose');

    // 💰 Payout
    if (didWin) {
      increaseBalance(90); // Win = +$90
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Turbo Flip: BTC/USD</Text>
      <Text style={styles.price}>Live Price: ${livePrice}</Text>

      {gameState === 'idle' && (
        <Button title="Play Turbo Flip ($50)" onPress={startFlip} />
      )}

      {gameState === 'running' && (
        <>
          <Text style={styles.info}>Strike Price: ${strikePrice}</Text>
          <Text style={styles.countdown}>Countdown: {countdown}s</Text>
        </>
      )}

      {gameState === 'result' && (
        <View style={styles.resultBox}>
          <Text style={styles.info}>Strike Price: ${strikePrice}</Text>
          <Text style={styles.info}>Final Price: ${finalPrice}</Text>
          <Text
            style={[
              styles.resultText,
              result === 'win' ? styles.win : styles.lose,
            ]}
          >
            {result === 'win' ? 'You WIN ✅' : 'You LOSE ❌'}
          </Text>
          <Button title="Play Again" onPress={() => setGameState('idle')} />
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 24,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#fff',
  },
  title: {
    fontSize: 22,
    fontWeight: 'bold',
    marginBottom: 12,
  },
  price: {
    fontSize: 18,
    marginBottom: 20,
  },
  info: {
    fontSize: 16,
    marginVertical: 4,
  },
  countdown: {
    fontSize: 26,
    fontWeight: 'bold',
    color: 'orange',
    marginTop: 20,
  },
  resultBox: {
    marginTop: 30,
    alignItems: 'center',
  },
  resultText: {
    fontSize: 28,
    fontWeight: 'bold',
    marginTop: 12,
  },
  win: {
    color: 'green',
  },
  lose: {
    color: 'red',
  },
});

export default TurboFlipScreen;

