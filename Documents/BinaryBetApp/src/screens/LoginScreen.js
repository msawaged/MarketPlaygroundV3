import React, { useState, useContext } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { UserContext } from '../context/UserContext';

const LoginScreen = () => {
  const [username, setUsername] = useState('');
  const navigation = useNavigation();
  const { setBalance, setUsername: setUserContextName } = useContext(UserContext); // access context setters

  // Handle login press
  const handleLogin = () => {
    if (username.trim().length === 0) return; // ignore empty names
    setUserContextName(username); // store username in context
    setBalance(1000); // initialize balance
    navigation.reset({
      index: 0,
      routes: [{ name: 'MarketPlayground' }],
    });
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Welcome to Market Playground 🧠</Text>
      <TextInput
        style={styles.input}
        placeholder="Enter a nickname"
        placeholderTextColor="#aaa"
        value={username}
        onChangeText={setUsername}
      />
      <TouchableOpacity style={styles.button} onPress={handleLogin}>
        <Text style={styles.buttonText}>Enter</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f0f0f',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  title: {
    fontSize: 26,
    color: '#fff',
    fontWeight: 'bold',
    marginBottom: 40,
    textAlign: 'center',
  },
  input: {
    backgroundColor: '#1f1f1f',
    color: '#fff',
    borderRadius: 10,
    paddingHorizontal: 16,
    paddingVertical: 12,
    width: '100%',
    fontSize: 16,
    marginBottom: 20,
  },
  button: {
    backgroundColor: '#1e90ff',
    paddingVertical: 14,
    paddingHorizontal: 30,
    borderRadius: 10,
    width: '100%',
    alignItems: 'center',
  },
  buttonText: {
    color: '#fff',
    fontSize: 18,
    fontWeight: 'bold',
  },
});

export default LoginScreen;

