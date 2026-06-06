import { useEffect, useState } from 'react';
import { Tabs } from 'expo-router';
import { useColorScheme, Pressable, View, ColorValue, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { AnimatedSplashOverlay } from '@/components/animated-icon';
import { Colors } from '@/constants/theme';
import { AuthProvider } from '@/contexts/AuthContext';
import { PlanProvider } from '@/contexts/PlanContext';

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
    return <Ionicons name={name as any} size={size} color="#007AFF" />;
  }

  return <Ionicons name={`${name}-outline` as any} size={size + 2} color={String(color)} />;
}

function WebFloatingTabBar({ state, descriptors, navigation, isDark, isDesktopWeb }: any) {
  // 桌面端样式 (垂直侧边胶囊)
  if (isDesktopWeb) {
    return (
      <View
        style={
          {
            position: 'fixed',
            top: 96,
            left: 18,
            width: 64,
            paddingVertical: 10,
            paddingHorizontal: 8,
            borderRadius: 32,
            borderWidth: 0.5,
            borderColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)',
            backgroundColor: isDark ? 'rgba(20, 20, 26, 0.92)' : 'rgba(255,255,255,0.92)',
            boxShadow: isDark
              ? '0 18px 48px rgba(0, 0, 0, 0.36)'
              : '0 18px 40px rgba(15, 23, 42, 0.12)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            zIndex: 99999,
            gap: 8,
          } as any
        }
      >
        {state.routes.map((route: any, index: number) => {
          const descriptor = descriptors[route.key];
          const isFocused = state.index === index;
          const color = isFocused ? '#007AFF' : isDark ? '#B0B4BA' : '#60646C';

          const onPress = () => {
            const event = navigation.emit({
              type: 'tabPress',
              target: route.key,
              canPreventDefault: true,
            });

            if (!isFocused && !event.defaultPrevented) {
              navigation.navigate(route.name, route.params);
            }
          };

          const icon = descriptor.options.tabBarIcon?.({
            focused: isFocused,
            color,
            size: 22,
          });

          return (
            <Pressable
              key={route.key}
              onPress={onPress}
              style={{
                width: 48,
                height: 48,
                borderRadius: 24,
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: isFocused ? (isDark ? 'rgba(0, 122, 255, 0.12)' : 'rgba(0, 122, 255, 0.08)') : 'transparent',
              }}
            >
              {icon}
            </Pressable>
          );
        })}
      </View>
    );
  }

  // 移动端/平板 Web 端样式 (左上角水平悬浮胶囊窗)
  return (
    <View
      style={
        {
          position: 'fixed',
          top: 14,
          left: 16,
          height: 40,
          flexDirection: 'row',
          alignItems: 'center',
          paddingHorizontal: 6,
          borderRadius: 20,
          borderWidth: 0.5,
          borderColor: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.06)',
          backgroundColor: isDark ? 'rgba(20, 20, 26, 0.88)' : 'rgba(255,255,255,0.88)',
          boxShadow: isDark
            ? '0 8px 24px rgba(0, 0, 0, 0.24)'
            : '0 8px 20px rgba(15, 23, 42, 0.08)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          zIndex: 99999,
          gap: 4,
        } as any
      }
    >
      {state.routes.map((route: any, index: number) => {
        const descriptor = descriptors[route.key];
        const isFocused = state.index === index;
        const color = isFocused ? '#007AFF' : isDark ? '#B0B4BA' : '#60646C';

        const onPress = () => {
          const event = navigation.emit({
            type: 'tabPress',
            target: route.key,
            canPreventDefault: true,
          });

          if (!isFocused && !event.defaultPrevented) {
            navigation.navigate(route.name, route.params);
          }
        };

        const icon = descriptor.options.tabBarIcon?.({
          focused: isFocused,
          color,
          size: 18,
        });

        return (
          <Pressable
            key={route.key}
            onPress={onPress}
            style={{
              width: 38,
              height: 28,
              borderRadius: 14,
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: isFocused ? (isDark ? 'rgba(0, 122, 255, 0.12)' : 'rgba(0, 122, 255, 0.08)') : 'transparent',
            }}
          >
            {icon}
          </Pressable>
        );
      })}
    </View>
  );
}

export default function WebTabLayout() {
  const scheme = useColorScheme();
  const { width } = useWindowDimensions();
  const [mounted, setMounted] = useState(false);
  const colors = Colors[scheme === 'unspecified' ? 'light' : scheme];
  const isDark = scheme === 'dark';
  const isDesktopWeb = mounted && width >= 1024;

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <AuthProvider>
      <PlanProvider>
        <AnimatedSplashOverlay />
        <Tabs
          tabBar={(props) => <WebFloatingTabBar {...props} isDark={isDark} isDesktopWeb={isDesktopWeb} />}
          screenOptions={{
            headerShown: false,
            tabBarActiveTintColor: '#007AFF',
            tabBarInactiveTintColor: colors.textSecondary,
            tabBarShowLabel: false,
            tabBarStyle: {
              display: 'none', // 彻底使用自定义悬浮组件代替默认底栏，解决移动端层级冲突
            } as any,
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
      </PlanProvider>
    </AuthProvider>
  );
}

const PlatformSpecificBlur = {
  backdropFilter: 'blur(20px)',
  WebkitBackdropFilter: 'blur(20px)',
};
