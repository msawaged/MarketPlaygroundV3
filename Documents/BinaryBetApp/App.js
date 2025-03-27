import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { ThemeProvider } from '@rneui/themed';

import MarketPlaygroundScreen from './src/screens/MarketPlaygroundScreen';
import TurboFlipScreen from './src/screens/TurboFlipScreen';
import RangeReaperScreen from './src/screens/RangeReaperScreen';
import LineBreakerScreen from './src/screens/LineBreakerScreen';
import RangeRunnerScreen from './src/screens/RangeRunnerScreen';
import BetHistoryScreen from './src/screens/BetHistoryScreen';
import LoginScreen from './src/screens/LoginScreen';

import { UserContextProvider } from './src/context/UserContext';

const Stack = createNativeStackNavigator();

export default function App() {
  return (
    <UserContextProvider>
      <ThemeProvider>
        <NavigationContainer>
          <Stack.Navigator initialRouteName="Login">
            <Stack.Screen name="Login" component={LoginScreen} />
            <Stack.Screen name="MarketPlayground" component={MarketPlaygroundScreen} />
            <Stack.Screen name="TurboFlip" component={TurboFlipScreen} />
            <Stack.Screen name="RangeReaper" component={RangeReaperScreen} />
            <Stack.Screen name="LineBreaker" component={LineBreakerScreen} />
            <Stack.Screen name="RangeRunner" component={RangeRunnerScreen} />
            <Stack.Screen name="BetHistory" component={BetHistoryScreen} />
          </Stack.Navigator>
        </NavigationContainer>
      </ThemeProvider>
    </UserContextProvider>
  );
}

