import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import MarketPlaygroundScreen from './src/screens/MarketPlaygroundScreen';
import TurboFlipScreen from './src/screens/TurboFlipScreen';

// 🔌 Import the BalanceProvider so all screens can access the balance
import { BalanceProvider } from './src/context/BalanceContext';

const Stack = createNativeStackNavigator();

export default function App() {
  return (
    // 💰 Wrap everything in BalanceProvider
    <BalanceProvider>
      <NavigationContainer>
        <Stack.Navigator initialRouteName="MarketPlayground">
          <Stack.Screen name="MarketPlayground" component={MarketPlaygroundScreen} />
          <Stack.Screen name="TurboFlip" component={TurboFlipScreen} />
        </Stack.Navigator>
      </NavigationContainer>
    </BalanceProvider>
  );
}

