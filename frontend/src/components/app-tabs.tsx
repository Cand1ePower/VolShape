import { Tabs } from 'expo-router';
import { useColorScheme, Platform } from 'react-native';
import { Colors } from '@/constants/theme';

export default function AppTabs() {
  const scheme = useColorScheme();
  const colors = Colors[scheme === 'unspecified' ? 'light' : scheme];

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: '#007AFF',
        tabBarInactiveTintColor: colors.textSecondary,
        tabBarStyle: {
          backgroundColor: colors.background,
          borderTopColor: scheme === 'dark' ? '#2C2C2E' : '#E5E5EA',
          borderTopWidth: 0.5,
          paddingBottom: Platform.OS === 'ios' ? 20 : 8,
          paddingTop: 8,
          height: Platform.OS === 'ios' ? 84 : 64,
        },
        tabBarLabelStyle: { fontSize: 11, fontWeight: '600' },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: '教练',
          tabBarIcon: ({ color }) => null,
        }}
      />
      <Tabs.Screen
        name="train"
        options={{
          title: '训练',
          tabBarIcon: ({ color }) => null,
        }}
      />
      <Tabs.Screen
        name="explore"
        options={{
          title: '我的',
          tabBarIcon: ({ color }) => null,
        }}
      />
    </Tabs>
  );
}
