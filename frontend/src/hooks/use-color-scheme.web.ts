import { useThemeController } from '@/contexts/ThemeContext';

export function useColorScheme() {
  return useThemeController().theme;
}
