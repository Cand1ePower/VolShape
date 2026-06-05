import { Platform } from 'react-native';

export const getBackendBaseUrl = () => {
  if (Platform.OS === 'android') {
    return 'http://192.168.10.9:8000';
  }
  return 'http://localhost:8000';
};

export async function apiFetch(path: string, options: RequestInit = {}) {
  const baseUrl = getBackendBaseUrl();
  return fetch(`${baseUrl}${path}`, options);
}
