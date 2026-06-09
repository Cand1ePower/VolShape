import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { Platform, useColorScheme as useRNColorScheme } from 'react-native';

type ThemeName = 'light' | 'dark';
type ThemePreference = ThemeName | 'system';

interface ThemeContextValue {
  theme: ThemeName;
  preference: ThemePreference;
  isDark: boolean;
  setPreference: (preference: ThemePreference) => void;
  toggleTheme: () => void;
}

const STORAGE_KEY = 'volshape_theme_preference';

export const ThemeContext = createContext<ThemeContextValue | null>(null);

function readStoredPreference(): ThemePreference {
  if (Platform.OS !== 'web' || typeof window === 'undefined') {
    return 'system';
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw === 'light' || raw === 'dark' || raw === 'system') {
      return raw;
    }
  } catch {}

  return 'system';
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const systemScheme = useRNColorScheme();
  const [preference, setPreferenceState] = useState<ThemePreference>(() => readStoredPreference());

  const theme: ThemeName = preference === 'system' ? (systemScheme === 'dark' ? 'dark' : 'light') : preference;

  useEffect(() => {
    if (Platform.OS !== 'web' || typeof document === 'undefined') {
      return;
    }

    document.documentElement.style.colorScheme = theme;
    document.body.style.backgroundColor = theme === 'dark' ? '#0A0A0C' : '#F5F5F7';
    document.body.style.color = theme === 'dark' ? '#FFFFFF' : '#111827';
  }, [theme]);

  const setPreference = useCallback((nextPreference: ThemePreference) => {
    setPreferenceState(nextPreference);

    if (Platform.OS !== 'web' || typeof window === 'undefined') {
      return;
    }

    try {
      window.localStorage.setItem(STORAGE_KEY, nextPreference);
    } catch {}
  }, []);

  const toggleTheme = useCallback(() => {
    setPreference(theme === 'dark' ? 'light' : 'dark');
  }, [setPreference, theme]);

  const value = useMemo<ThemeContextValue>(
    () => ({
      theme,
      preference,
      isDark: theme === 'dark',
      setPreference,
      toggleTheme,
    }),
    [preference, setPreference, theme, toggleTheme]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useThemeController() {
  const context = useContext(ThemeContext);
  const systemScheme = useRNColorScheme();

  if (context) {
    return context;
  }

  const fallbackTheme: ThemeName = systemScheme === 'dark' ? 'dark' : 'light';

  return {
    theme: fallbackTheme,
    preference: 'system' as const,
    isDark: fallbackTheme === 'dark',
    setPreference: () => {},
    toggleTheme: () => {},
  };
}
