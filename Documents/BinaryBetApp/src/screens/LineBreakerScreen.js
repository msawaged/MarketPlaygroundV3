import React, { useState } from 'react';
import { View, Text, TouchableOpacity, TextInput, StyleSheet } from 'react-native';

const LineBreakerScreen = () => {
  const [strikePrice, setStrikePrice] = useState('');
  const [livePrice] = useState(69000); // Placeholder for now
  const [betPlaced, setBetPlaced] = useState(false);
  const [result, setResult] = useState(null);
  const [countdown, setCountdown] = useState(10);

  const handlePlaceBet = () => {
    if (!strikePrice) return;

    setBetPlaced(true);
    setCountdown(10);

    const interval = setInterval(() => {
      setCountdown(prev => {
        if (prev === 1) {
          clearInterval(interval);
          const priceMoved = Math.random() > 0.5; // Simulate price movement
          const priceBroke = priceMoved && (Math.random() > 0.5);
          const finalPrice = priceBroke ? parseFloat(strikePrice) + 100 : parseFloat(strikePrice);

          setResult({
            finalPrice,
            won: priceBroke,
          });
        }
        return prev - 1;
      });
    }, 1000);
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>LineBreaker: BTC/USD</Text>
      <Text style={styles.label}>Live Price: ${livePrice}</Text>

      <TextInput
        placeholder="Enter Strike Price"
        keyboardType="numeric"
        value={strikePrice}
        onChangeText={setStrikePrice}
        style={styles.input}
      />

      {!betPlaced ? (
        <TouchableOpacity style={styles.button} onPress={handlePlaceBet}>
          <Text style={styles.buttonText}>Place LineBreaker Bet</Text>
        </TouchableOpacity>
      ) : (
        <>
          <Text style={styles.label}>Countdown: {countdown}s</Text>
          {result && (
            <View style={{ marginTop: 20 }}>
              <Text style={styles.label}>Final Price: ${result.finalPrice}</Text>
              <Text style={[styles.resultText, { color: result.won ? 'green' : 'red' }]}>
                {result.won ? 'You WIN ✅' : 'You LOSE ❌'}
              </Text>
            </View>
          )}
        </>
      )}
    </View>
  );
};

export default LineBreakerScreen;

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 24,
    justifyContent: 'center',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    textAlign: 'center',
    marginBottom: 16,
  },
  label: {
    fontSize: 18,
    textAlign: 'center',
    marginVertical: 8,
  },
  input: {
    borderWidth: 1,
    borderRadius: 8,
    padding: 12,
    fontSize: 18,
    marginVertical: 12,
  },
  button: {
    backgroundColor: '#4e8bed',
    padding: 14,
    borderRadius: 10,
    alignItems: 'center',
    marginTop: 10,
  },
  buttonText: {
    color: '#fff',
    fontSize: 18,
  },
  resultText: {
    fontSize: 22,
    fontWeight: 'bold',
    textAlign: 'center',
    marginTop: 12,
  },
});

