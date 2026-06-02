import { Tabs } from 'expo-router';
import { useColorScheme, Platform, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedSplashOverlay } from '@/components/animated-icon';
import { AuthProvider } from '@/contexts/AuthContext';
import { PlanProvider } from '@/contexts/PlanContext';
import { Colors } from '@/constants/theme';

// 极致微光 Tab 选中态光圈容器
function TabIcon({ name, focused, color, size = 24 }: { name: string; focused: boolean; color: string; size?: number }) {
  if (focused) {
    return (
      <View style={{
        width: 40,
        height: 40,
        borderRadius: 20,
        backgroundColor: 'rgba(0, 122, 255, 0.08)', // 极柔和的淡蔚蓝光晕晕开效果，无边线无投影
        justifyContent: 'center',
        alignItems: 'center',
      }}>
        <Ionicons name={name as any} size={size} color="#007AFF" />
      </View>
    );
  }
  return (
    <Ionicons name={`${name}-outline` as any} size={size + 2} color={color} />
  );
}

export default function TabLayout() {
  const scheme = useColorScheme();
  const colors = Colors[scheme === 'unspecified' ? 'light' : scheme];
  const isDark = scheme === 'dark';

  return (
    <AuthProvider>
      <PlanProvider>
        <AnimatedSplashOverlay />
        <Tabs
          screenOptions={{
            headerShown: false,
            tabBarActiveTintColor: '#007AFF',
            tabBarInactiveTintColor: colors.textSecondary,
            tabBarShowLabel: false,
            tabBarStyle: {
              backgroundColor: isDark ? 'rgba(20, 20, 26, 0.85)' : 'rgba(255, 255, 255, 0.88)',
              borderTopWidth: 0.5,
              borderTopColor: isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.03)', // 超柔和极细衔接分界线
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
                ? { backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)' } as any
                : {})
            },
          }}
        >
          <Tabs.Screen
            name="index"
            options={{
              title: '教练',
              tabBarIcon: ({ color, focused }) => (
                <TabIcon
                  name="chatbubble-ellipses"
                  focused={focused}
                  color={color}
                  size={22}
                />
              ),
            }}
          />
          <Tabs.Screen
            name="train"
            options={{
              title: '训练',
              tabBarIcon: ({ color, focused }) => (
                <TabIcon
                  name="barbell"
                  focused={focused}
                  color={color}
                  size={22}
                />
              ),
            }}
          />
          <Tabs.Screen
            name="explore"
            options={{
              title: '我的',
              tabBarIcon: ({ color, focused }) => (
                <TabIcon
                  name="person-circle"
                  focused={focused}
                  color={color}
                  size={23}
                />
              ),
            }}
          />
        </Tabs>
      </PlanProvider>
    </AuthProvider>
  );
}

