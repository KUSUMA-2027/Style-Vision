import React from 'react';
import { Tabs } from 'expo-router';
import { Text, View, StyleSheet, Platform } from 'react-native';
import { Colors, Typography, Spacing } from '@/constants/theme';

interface TabIconProps {
  icon: string;
  focused: boolean;
  label: string;
}

const TabIcon: React.FC<TabIconProps> = ({ icon, focused, label }) => {
  return (
    <View style={styles.tabItem}>
      <Text style={[styles.icon, focused && styles.iconFocused]}>{icon}</Text>
      <Text style={[styles.label, focused && styles.labelFocused]}>{label}</Text>
    </View>
  );
};

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarShowLabel: false,
        tabBarStyle: styles.tabBar,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Home',
          tabBarIcon: ({ focused }) => (
            <TabIcon icon="🏛️" focused={focused} label="Atelier" />
          ),
        }}
      />
      <Tabs.Screen
        name="try-on"
        options={{
          title: 'Try-On',
          tabBarIcon: ({ focused }) => (
            <TabIcon icon="✨" focused={focused} label="Studio" />
          ),
        }}
      />
      <Tabs.Screen
        name="history"
        options={{
          title: 'Saved',
          tabBarIcon: ({ focused }) => (
            <TabIcon icon="💎" focused={focused} label="Closet" />
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: 'Profile',
          tabBarIcon: ({ focused }) => (
            <TabIcon icon="👑" focused={focused} label="VIP Suite" />
          ),
        }}
      />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    backgroundColor: Colors.backgroundSecondary,
    borderTopColor: Colors.border,
    borderTopWidth: 1.5,
    height: Platform.OS === 'ios' ? 88 : 68,
    paddingTop: Spacing.sm,
    paddingBottom: Platform.OS === 'ios' ? 24 : 10,
  },
  tabItem: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  icon: {
    fontSize: 22,
    opacity: 0.65,
  },
  iconFocused: {
    opacity: 1,
    transform: [{ scale: 1.15 }],
  },
  label: {
    fontSize: Typography.sizes.xs - 1,
    color: Colors.textMuted,
    fontWeight: Typography.weights.medium,
    marginTop: 3,
    letterSpacing: 0.5,
  },
  labelFocused: {
    color: Colors.primaryLight,
    fontWeight: Typography.weights.heavy,
    letterSpacing: 0.8,
  },
});
