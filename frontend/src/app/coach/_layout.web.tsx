import { Ionicons } from '@expo/vector-icons';
import { Tabs } from 'expo-router';
import { Pressable, StyleSheet, Text, View, useWindowDimensions } from 'react-native';

import { useThemeController } from '@/contexts/ThemeContext';

function TabGlyph({
  name,
  focused,
  color,
  size = 20,
}: {
  name: string;
  focused: boolean;
  color: string;
  size?: number;
}) {
  return <Ionicons name={(focused ? name : `${name}-outline`) as any} size={size} color={color} />;
}

function CoachWebTabBar({ state, descriptors, navigation, isDark, isDesktopWeb, onToggleTheme }: any) {
  const railBg = isDark ? 'rgba(15, 18, 27, 0.84)' : 'rgba(255, 255, 255, 0.9)';
  const borderCol = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.08)';
  const muted = isDark ? '#94A3B8' : '#64748B';
  const textCol = isDark ? '#F8FAFC' : '#0F172A';

  if (isDesktopWeb) {
    return (
      <View style={[styles.desktopRail, { backgroundColor: railBg, borderColor: borderCol }]}>
        <View style={styles.desktopBrand}>
          <View style={[styles.desktopBrandMark, { backgroundColor: isDark ? 'rgba(37, 99, 235, 0.18)' : 'rgba(37, 99, 235, 0.1)' }]}>
            <Ionicons name="sparkles" size={18} color="#3B82F6" />
          </View>
          <View style={{ gap: 2 }}>
            <Text style={[styles.desktopBrandTitle, { color: textCol }]}>VolShape</Text>
            <Text style={[styles.desktopBrandSub, { color: muted }]}>Coach</Text>
          </View>
        </View>

        <View style={styles.desktopNav}>
          {state.routes.map((route: any, index: number) => {
            const descriptor = descriptors[route.key];
            const isFocused = state.index === index;
            const color = isFocused ? '#3B82F6' : muted;
            const label = descriptor.options.title || route.name;

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
              size: 20,
            });

            return (
              <Pressable
                key={route.key}
                onPress={onPress}
                style={({ hovered, pressed }) => [
                  styles.desktopNavItem,
                  {
                    backgroundColor: isFocused
                      ? isDark
                        ? 'rgba(37, 99, 235, 0.16)'
                        : 'rgba(37, 99, 235, 0.1)'
                      : hovered
                        ? isDark
                          ? 'rgba(255,255,255,0.04)'
                          : 'rgba(15,23,42,0.04)'
                        : 'transparent',
                    opacity: pressed ? 0.92 : 1,
                  },
                ]}
              >
                <View style={styles.desktopNavGlyph}>{icon}</View>
                <Text style={[styles.desktopNavLabel, { color: isFocused ? textCol : muted }]}>{label}</Text>
              </Pressable>
            );
          })}
        </View>

        <Pressable
          onPress={onToggleTheme}
          style={({ hovered, pressed }) => [
            styles.themeSwitch,
            {
              backgroundColor: hovered
                ? isDark
                  ? 'rgba(255,255,255,0.05)'
                  : 'rgba(15,23,42,0.04)'
                : 'transparent',
              borderColor: borderCol,
              opacity: pressed ? 0.92 : 1,
            },
          ]}
        >
          <Ionicons name={isDark ? 'sunny-outline' : 'moon-outline'} size={18} color={textCol} />
          <Text style={[styles.themeSwitchText, { color: textCol }]}>{isDark ? '浅色' : '深色'}</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={[styles.mobileRail, { backgroundColor: railBg, borderColor: borderCol }]}>
      {state.routes.map((route: any, index: number) => {
        const descriptor = descriptors[route.key];
        const isFocused = state.index === index;
        const color = isFocused ? '#3B82F6' : muted;

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
            style={({ pressed }) => [
              styles.mobileNavItem,
              {
                backgroundColor: isFocused
                  ? isDark
                    ? 'rgba(37, 99, 235, 0.16)'
                    : 'rgba(37, 99, 235, 0.1)'
                  : 'transparent',
                opacity: pressed ? 0.92 : 1,
              },
            ]}
          >
            {icon}
          </Pressable>
        );
      })}
      <Pressable
        onPress={onToggleTheme}
        style={({ pressed }) => [
          styles.mobileNavItem,
          {
            backgroundColor: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(15,23,42,0.04)',
            opacity: pressed ? 0.92 : 1,
          },
        ]}
      >
        <Ionicons name={isDark ? 'sunny-outline' : 'moon-outline'} size={16} color={textCol} />
      </Pressable>
    </View>
  );
}

function CoachTabs() {
  const { isDark, toggleTheme } = useThemeController();
  const { width } = useWindowDimensions();
  const isDesktopWeb = width >= 1100;

  return (
    <Tabs
      tabBar={(props) => (
        <CoachWebTabBar
          {...props}
          isDark={isDark}
          isDesktopWeb={isDesktopWeb}
          onToggleTheme={toggleTheme}
        />
      )}
      screenOptions={{
        headerShown: false,
        tabBarShowLabel: false,
        tabBarStyle: { display: 'none' } as any,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: '对话',
          tabBarIcon: ({ color, focused }) => (
            <TabGlyph name="chatbubble-ellipses" focused={focused} color={String(color)} size={20} />
          ),
        }}
      />
      <Tabs.Screen
        name="train"
        options={{
          title: '训练',
          tabBarIcon: ({ color, focused }) => (
            <TabGlyph name="barbell" focused={focused} color={String(color)} size={20} />
          ),
        }}
      />
      <Tabs.Screen
        name="explore"
        options={{
          title: '我的',
          tabBarIcon: ({ color, focused }) => (
            <TabGlyph name="person-circle" focused={focused} color={String(color)} size={21} />
          ),
        }}
      />
    </Tabs>
  );
}

export default function WebTabLayout() {
  return <CoachTabs />;
}

const styles = StyleSheet.create({
  desktopRail: {
    position: 'fixed',
    top: 28,
    left: 24,
    bottom: 28,
    width: 88,
    borderWidth: 1,
    borderRadius: 30,
    paddingVertical: 16,
    paddingHorizontal: 10,
    justifyContent: 'space-between',
    zIndex: 9999,
    backdropFilter: 'blur(22px)',
    WebkitBackdropFilter: 'blur(22px)',
    boxShadow: '0 22px 50px rgba(2, 6, 23, 0.16)',
  } as any,
  desktopBrand: {
    alignItems: 'center',
    gap: 10,
  },
  desktopBrandMark: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
  },
  desktopBrandTitle: {
    fontSize: 11,
    fontWeight: '800',
    textAlign: 'center',
  },
  desktopBrandSub: {
    fontSize: 10,
    fontWeight: '600',
    textAlign: 'center',
    letterSpacing: 0.4,
    textTransform: 'uppercase',
  },
  desktopNav: {
    gap: 8,
    alignItems: 'center',
  },
  desktopNavItem: {
    width: 68,
    minHeight: 68,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    transitionDuration: '180ms',
  } as any,
  desktopNavGlyph: {
    width: 32,
    height: 32,
    alignItems: 'center',
    justifyContent: 'center',
  },
  desktopNavLabel: {
    fontSize: 11,
    fontWeight: '700',
  },
  themeSwitch: {
    minHeight: 44,
    borderRadius: 18,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    transitionDuration: '180ms',
  } as any,
  themeSwitchText: {
    fontSize: 10,
    fontWeight: '700',
  },
  mobileRail: {
    position: 'fixed',
    top: 18,
    left: 18,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    padding: 6,
    borderRadius: 999,
    borderWidth: 1,
    zIndex: 9999,
    backdropFilter: 'blur(18px)',
    WebkitBackdropFilter: 'blur(18px)',
    boxShadow: '0 14px 34px rgba(2, 6, 23, 0.14)',
  } as any,
  mobileNavItem: {
    width: 38,
    height: 30,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
