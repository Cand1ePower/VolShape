import { Stack } from 'expo-router';
import { Platform } from 'react-native';

import { AnimatedSplashOverlay } from '@/components/animated-icon';
import { AuthProvider } from '@/contexts/AuthContext';
import { PlanProvider } from '@/contexts/PlanContext';
import { ThemeProvider, useThemeController } from '@/contexts/ThemeContext';

function WebRootStack() {
  const { isDark } = useThemeController();

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        animation: 'none',
        contentStyle: { backgroundColor: isDark ? '#0A0A0C' : '#F5F5F7' },
      }}
    />
  );
}

export default function WebRootLayout() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <PlanProvider>
          {Platform.OS !== 'web' ? <AnimatedSplashOverlay /> : null}
          <WebRootStack />
        </PlanProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
