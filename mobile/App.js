// App.js
// Expo React Native Mobile App for MarketPlayground
// Entry point with navigation, belief input, strategy list, and detail charts

import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import axios from 'axios';
import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Button, Dimensions, FlatList, SafeAreaView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { LineChart } from 'react-native-chart-kit';

// Create the navigation stack
const Stack = createNativeStackNavigator();

// Point to your local backend (use your LAN IP)
const API_BASE = 'http://10.0.0.61:8001';

// Home screen: enter belief, fetch strategy, show top-10 list
function HomeScreen({ navigation }) {
  const [belief, setBelief] = useState('');
  const [loading, setLoading] = useState(false);
  const [contracts, setContracts] = useState([]);
  const [suggestion, setSuggestion] = useState(null);

  // Fetches the AI-suggested strategy and top contracts
  const fetchStrategy = async () => {
    setLoading(true);
    try {
      const res = await axios.post(`${API_BASE}/strategy`, { belief });
      setSuggestion(res.data.suggestion);
      setContracts(res.data.topContracts);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.title}>MarketPlayground</Text>

      {/* Input for user belief */}
      <TextInput
        style={styles.input}
        placeholder="Enter your belief"
        value={belief}
        onChangeText={setBelief}
      />

      {/* Button to fetch strategy */}
      <Button title="Get Strategy" onPress={fetchStrategy} />

      {/* Loading spinner */}
      {loading && <ActivityIndicator style={{ marginTop: 20 }} />}

      {/* Show the AI's example */}
      {suggestion && (
        <View style={styles.suggestion}>
          <Text>Example: {suggestion.example}</Text>
        </View>
      )}

      {/* List of top-10 option contracts */}
      <FlatList
        data={contracts}
        keyExtractor={(item) => item.contractSymbol}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.item}
            onPress={() => navigation.navigate('Detail', { contract: item })}
          >
            <Text style={styles.contract}>{item.contractSymbol}</Text>
            <Text>
              Vol: {item.volume} {'  '} IV: {item.impliedVolatility.toFixed(2)}
            </Text>
            {/* Mini leverage sparkline */}
            <LineChart
              data={{ datasets: [{ data: [item.leverage] }] }}
              width={100}
              height={40}
              chartConfig={{ backgroundGradientFrom: '#fff', backgroundGradientTo: '#fff', color: () => '#000' }}
              withDots={false}
              withHorizontalLines={false}
              withVerticalLines={false}
            />
          </TouchableOpacity>
        )}
      />
    </SafeAreaView>
  );
}

// Detail screen: show intraday P/L chart for chosen contract
function DetailScreen({ route }) {
  const { contract } = route.params;
  const [pnlData, setPnlData] = useState([]);
  const width = Dimensions.get('window').width - 40;

  // Fetch live intraday P/L from backend
  useEffect(() => {
    axios
      .get(`${API_BASE}/live-pnl?contract=${contract.contractSymbol}`)
      .then((res) => setPnlData(res.data))
      .catch(console.error);
  }, []);

  // Prepare data for the chart
  const labels = pnlData.map((p) => p.timestamp.split('T')[1].substr(0, 5));
  const dataPoints = pnlData.map((p) => p.pnl);

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.title}>{contract.contractSymbol}</Text>

      {/* Intraday P/L chart */}
      <LineChart
        data={{ labels, datasets: [{ data: dataPoints }] }}
        width={width}
        height={220}
        chartConfig={{ backgroundGradientFrom: '#fff', backgroundGradientTo: '#fff', color: () => '#000' }}
        bezier
      />
    </SafeAreaView>
  );
}

// App entry: set up navigation
export default function App() {
  return (
    <NavigationContainer>
      <Stack.Navigator>
        <Stack.Screen name="Home" component={HomeScreen} />
        <Stack.Screen name="Detail" component={DetailScreen} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}

// Styles for both screens
const styles = StyleSheet.create({
  container: { flex: 1, padding: 20 },
  title: { fontSize: 24, fontWeight: 'bold', marginBottom: 10 },
  input: { borderWidth: 1, borderColor: '#ccc', padding: 8, marginBottom: 10, borderRadius: 4 },
  suggestion: { padding: 10, backgroundColor: '#eef', marginVertical: 10, borderRadius: 4 },
  item: { padding: 10, borderBottomWidth: 1, borderColor: '#ddd' },
  contract: { fontSize: 16, fontWeight: '600' },
});
