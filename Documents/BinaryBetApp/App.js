// ✅ React & Navigation imports
import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { ThemeProvider } from '@rneui/themed';

// ✅ Screens
import LoginScreen from './src/screens/LoginScreen';
import MarketPlaygroundScreen from './src/screens/MarketPlaygroundScreen';
import TurboFlipScreen from './src/screens/TurboFlipScreen';
import RangeReaperScreen from './src/screens/RangeReaperScreen';
import RangeRunnerScreen from './src/screens/RangeRunnerScreen';
import LineBreakerScreen from './src/screens/LineBreakerScreen';
import BetHistoryScreen from './src/screens/BetHistoryScreen';

// ✅ Context Providers
import { BalanceProvider } from './src/context/BalanceContext';
import { BetHistoryProvider } from './src/context/BetHistoryContext';
import { UserProvider } from './src/context/UserContext';

// ✅ Create the main stack navigator
const Stack = createNativeStackNavigator();

// ✅ Main App Component
export default function App() {
  return (
    // Wrap everything in ThemeProvider for UI styling
    <ThemeProvider>
      {/* Wrap in UserProvider to manage nickname and balance */}
      <UserProvider>
        {/* Wrap in BalanceProvider to handle balance context */}
        <BalanceProvider>
          {/* Wrap in BetHistoryProvider to track user bets */}
          <BetHistoryProvider>
            {/* Navigation container for the entire app */}
            <NavigationContainer>
              <Stack.Navigator initialRouteName="Login" screenOptions={{ headerShown: false }}>
                {/* 👇 All the screen routes in the app */}
                <Stack.Screen name="Login" component={LoginScreen} />
                <Stack.Screen name="MarketPlayground" component={MarketPlaygroundScreen} />
                <Stack.Screen name="TurboFlip" component={TurboFlipScreen} />
                <Stack.Screen name="RangeReaper" component={RangeReaperScreen} />
                <Stack.Screen name="RangeRunner" component={RangeRunnerScreen} />
                <Stack.Screen name="LineBreaker" component={LineBreakerScreen} />
                <Stack.Screen name="BetHistory" component={BetHistoryScreen} />
              </Stack.Navigator>
            </NavigationContainer>
          </BetHistoryProvider>
        </BalanceProvider>
      </UserProvider>
    </ThemeProvider>
  );
}

