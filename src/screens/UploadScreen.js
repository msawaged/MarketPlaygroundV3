import React from 'react';
import { View, StyleSheet } from 'react-native';

export default function UploadScreen() {
  return (
    <View style={styles.container} />
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: 'red',  // Should make screen BRIGHT red
  },
});
