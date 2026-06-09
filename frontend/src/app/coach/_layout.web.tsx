import { useEffect, useState } from 'react';
import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { ColorValue, Pressable, View, useWindowDimensions } from 'react-native';

import { Colors } from '@/constants/theme';
import { ThemeProvider, useThemeController } from '@/contexts/ThemeContext';
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
    return <Ionicons name={name as any} size={size} color="#007AFF" />;
  }

  return <Ionicons name={`${name}-outline` as any} size={size + 2} color={String(color)} />;
}

function WebFloatingTabBar({ state, descriptors, navigation, isDark, isDesktopWeb, onToggleTheme }: any) {
  const themeIcon = isDark ? 'sunny-outline' : 'moon-outline';
  const themeColor = isDark ? '#F8FAFC' : '#0F172A';

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
                backgroundColor: isFocused
                  ? isDark
                    ? 'rgba(0, 122, 255, 0.12)'
                    : 'rgba(0, 122, 255, 0.08)'
                  : 'transparent',
              }}
            >
              {icon}
            </Pressable>
          );
        })}
        <View
          style={{
            height: 1,
            marginHorizontal: 10,
            backgroundColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)',
          }}
        />
        <Pressable
          onPress={onToggleTheme}
          style={{
            width: 48,
            height: 48,
            borderRadius: 24,
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)',
          }}
        >
          <Ionicons name={themeIcon as any} size={20} color={themeColor} />
        </Pressable>
      </View>
    );
  }

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
              backgroundColor: isFocused
                ? isDark
                  ? 'rgba(0, 122, 255, 0.12)'
                  : 'rgba(0, 122, 255, 0.08)'
                : 'transparent',
            }}
          >
            {icon}
          </Pressable>
        );
      })}
      <Pressable
        onPress={onToggleTheme}
        style={{
          width: 38,
          height: 28,
          borderRadius: 14,
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)',
        }}
      >
        <Ionicons name={themeIcon as any} size={16} color={themeColor} />
      </Pressable>
    </View>
  );
}

function CoachTabs() {
  const scheme = useColorScheme();
  const { width } = useWindowDimensions();
  const [mounted, setMounted] = useState(false);
  const colors = Colors[scheme === 'unspecified' ? 'light' : scheme];
  const { isDark, toggleTheme } = useThemeController();
  const isDesktopWeb = mounted && width >= 1024;

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <Tabs
      tabBar={(props) => (
        <WebFloatingTabBar
          {...props}
          isDark={isDark}
          isDesktopWeb={isDesktopWeb}
          onToggleTheme={toggleTheme}
        />
      )}
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: '#007AFF',
        tabBarInactiveTintColor: colors.textSecondary,
        tabBarShowLabel: false,
        tabBarStyle: {
          display: 'none',
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
  );
}

export default function WebTabLayout() {
  return (
    <ThemeProvider>
      <CoachTabs />
    </ThemeProvider>
  );
}
