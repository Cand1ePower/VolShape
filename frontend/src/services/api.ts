import { Platform } from 'react-native';

export const getBackendBaseUrl = () => {
  const configuredUrl = process.env.EXPO_PUBLIC_API_BASE_URL?.trim();
  if (configuredUrl) {
    return configuredUrl.replace(/\/$/, '');
  }

  if (Platform.OS === 'android') {
    return 'http://192.168.10.9:8000';
  }
  return 'http://localhost:8000';
};

export async function apiFetch(path: string, options: RequestInit = {}) {
  const baseUrl = getBackendBaseUrl();
  return fetch(`${baseUrl}${path}`, options);
}
