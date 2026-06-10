import { Platform } from 'react-native';

export const getBackendBaseUrl = () => {
  const configuredUrl = process.env.EXPO_PUBLIC_API_BASE_URL?.trim();
  if (configuredUrl) {
    return configuredUrl.replace(/\/$/, '');
  }

  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    const { protocol, hostname } = window.location;
    if (protocol.startsWith('http') && hostname) {
      if (hostname === 'localhost' || hostname === '127.0.0.1') {
        return 'http://localhost:8000';
      }
      return `${protocol}//${hostname}`.replace(/\/$/, '');
    }
    return 'http://localhost:8000';
  }

  return 'https://volshape.candlepower.cool';
};

export async function apiFetch(path: string, options: RequestInit = {}) {
  const baseUrl = getBackendBaseUrl();
  return fetch(`${baseUrl}${path}`, options);
}
