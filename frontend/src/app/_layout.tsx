import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { ColorValue, Platform, View } from 'react-native';

import { AnimatedSplashOverlay } from '@/components/animated-icon';
import { Colors } from '@/constants/theme';
import { AuthProvider } from '@/contexts/AuthContext';
import { PlanProvider } from '@/contexts/PlanContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { useColorScheme } from '@/hooks/use-color-scheme';

function TabIcon({
  name,
  focused,
  color,
  size = 24,
}: {
  name: string;
  focused: boolean;
  color: ColorValue;
  size?: number;
}) {
  if (focused) {
    return (
      <View
        style={{
          width: 40,
          height: 40,
          borderRadius: 20,
          backgroundColor: 'rgba(0, 122, 255, 0.08)',
          justifyContent: 'center',
          alignItems: 'center',
        }}
      >
        <Ionicons name={name as any} size={size} color="#007AFF" />
      </View>
    );
  }

  return <Ionicons name={`${name}-outline` as any} size={size + 2} color={String(color)} />;
}

function AppTabs() {
  const scheme = useColorScheme();
  const colors = Colors[scheme];
  const isDark = scheme === 'dark';

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: '#007AFF',
        tabBarInactiveTintColor: colors.textSecondary,
        tabBarShowLabel: false,
        tabBarStyle: {
          backgroundColor: isDark ? 'rgba(20, 20, 26, 0.85)' : 'rgba(255, 255, 255, 0.88)',
          borderTopWidth: 0.5,
          borderTopColor: isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.03)',
          shadowColor: 'transparent',
          elevation: 0,
          position: Platform.OS === 'web' ? 'fixed' : 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          paddingBottom: Platform.OS === 'ios' ? 22 : 8,
          paddingTop: 8,
          height: Platform.OS === 'ios' ? 76 : 58,
          ...(Platform.OS === 'web'
            ? ({ backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)' } as any)
            : {}),
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: '教练',
          tabBarIcon: ({ color, focused }) => (
            <TabIcon name="chatbubble-ellipses" focused={focused} color={color} size={22} />
          ),
        }}
      />
      <Tabs.Screen
        name="train"
        options={{
          title: '训练',
          tabBarIcon: ({ color, focused }) => (
            <TabIcon name="barbell" focused={focused} color={color} size={22} />
          ),
        }}
      />
      <Tabs.Screen
        name="explore"
        options={{
          title: '我的',
          tabBarIcon: ({ color, focused }) => (
            <TabIcon name="person-circle" focused={focused} color={color} size={23} />
          ),
        }}
      />
    </Tabs>
  );
}

export default function TabLayout() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <PlanProvider>
          <AnimatedSplashOverlay />
          <AppTabs />
        </PlanProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
