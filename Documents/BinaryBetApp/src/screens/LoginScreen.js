import React, { useState, useEffect } from 'react';
import { View, TextInput, Button, StyleSheet, Text } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useNavigation } from '@react-navigation/native';
import { useUser } from '../context/UserContext'; // ✅ Using our custom hook

const LoginScreen = () => {
  const [input, setInput] = useState('');
  const navigation = useNavigation();
  const { nickname, setNickname } = useUser(); // ✅ Correctly accessing context

  // Load stored nickname if it exists
  useEffect(() => {
    const loadNickname = async () => {
      try {
        const storedNickname = await AsyncStorage.getItem('nickname');
        if (storedNickname) {
          setNickname(storedNickname);
          navigation.reset({
            index: 0,
            routes: [{ name: 'MarketPlayground' }],
          });
        }
      } catch (e) {
        console.log('Failed to load nickname', e);
      }
    };

    loadNickname();
  }, []);

  // Save nickname and navigate
  const handleLogin = async () => {
    try {
      await AsyncStorage.setItem('nickname', input);
      setNickname(input);
      navigation.reset({
        index: 0,
        routes: [{ name: 'MarketPlayground' }],
      });
    } catch (e) {
      console.log('Failed to save nickname', e);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.label}>Enter Your Nickname</Text>
      <TextInput
        style={styles.input}
        value={input}
        onChangeText={setInput}
        placeholder="Nickname"
      />
      <Button title="Enter Market Playground" onPress={handleLogin} />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    padding: 20,
    backgroundColor: '#0e0e0e',
  },
  label: {
    color: 'white',
    fontSize: 18,
    marginBottom: 10,
    alignSelf: 'center',
  },
  input: {
    backgroundColor: 'white',
    borderRadius: 10,
    padding: 10,
    fontSize: 16,
    marginBottom: 20,
  },
});

export default LoginScreen;

