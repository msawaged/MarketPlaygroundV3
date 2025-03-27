import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';

// 🧭 Navigation hook
import { useNavigation } from '@react-navigation/native';

const LoginScreen = () => {
  const navigation = useNavigation();

  // 🚀 Simulated login logic
  const handleLogin = () => {
    // 👇 Set default balance here and pass it forward
    navigation.reset({
      index: 0,
      routes: [
        {
          name: 'MarketPlayground',
          params: {
            balance: 1000,
          },
        },
      ],
    });
  };

  return (
    <View
      style={{
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: '#F3F4F6',
      }}
    >
      <Text style={{ fontSize: 32, fontWeight: 'bold', marginBottom: 20 }}>
        Welcome to Market Playground 🧠
      </Text>

      <TouchableOpacity
        onPress={handleLogin}
        style={{
          backgroundColor: '#3B82F6',
          paddingVertical: 15,
          paddingHorizontal: 40,
          borderRadius: 12,
        }}
      >
        <Text style={{ color: 'white', fontSize: 18, fontWeight: '600' }}>
          Enter
        </Text>
      </TouchableOpacity>
    </View>
  );
};

export default LoginScreen;

