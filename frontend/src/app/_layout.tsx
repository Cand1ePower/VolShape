import { Tabs } from 'expo-router';
import { useColorScheme, Platform } from 'react-native';
import { AnimatedSplashOverlay } from '@/components/animated-icon';
import { AuthProvider } from '@/contexts/AuthContext';
import { PlanProvider } from '@/contexts/PlanContext';
import { Colors } from '@/constants/theme';

export default function TabLayout() {
  const scheme = useColorScheme();
  const colors = Colors[scheme === 'unspecified' ? 'light' : scheme];

  return (
    <AuthProvider>
      <PlanProvider>
        <AnimatedSplashOverlay />
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
          <Tabs.Screen name="index" options={{ title: '教练' }} />
          <Tabs.Screen name="train" options={{ title: '训练' }} />
          <Tabs.Screen name="explore" options={{ title: '我的' }} />
        </Tabs>
      </PlanProvider>
    </AuthProvider>
  );
}
