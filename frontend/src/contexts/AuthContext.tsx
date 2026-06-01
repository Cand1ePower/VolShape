import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { Platform } from 'react-native';

interface AuthState {
  token: string | null;
  userId: string | null;
  sessionId: string | null;
  isLoggedIn: boolean;
  isLoading: boolean;
}

interface AuthContextType extends AuthState {
  login: (token: string) => Promise<void>;
  logout: () => Promise<void>;
  switchUser: (token: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  token: null, userId: null, sessionId: null,
  isLoggedIn: false, isLoading: true,
  login: async () => {}, logout: async () => {}, switchUser: async () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

const STORAGE_KEY = 'volshape_auth_token';
const SESSION_KEY = 'volshape_session_id';

let _memToken: string | null = null;

async function getStorage() {
  if (Platform.OS === 'web') {
    return {
      getItem: (key: string) => Promise.resolve(localStorage.getItem(key)),
      setItem: (key: string, value: string) => { localStorage.setItem(key, value); return Promise.resolve(); },
      removeItem: (key: string) => { localStorage.removeItem(key); return Promise.resolve(); },
    };
  }
  // Native: try expo-secure-store, fallback to in-memory
  try {
    const SecureStore = require('expo-secure-store');
    return {
      getItem: (key: string) => SecureStore.getItemAsync(key),
      setItem: (key: string, value: string) => SecureStore.setItemAsync(key, value),
      removeItem: (key: string) => SecureStore.deleteItemAsync(key),
    };
  } catch {
    return {
      getItem: (_key: string) => Promise.resolve(_memToken),
      setItem: (_key: string, value: string) => { _memToken = value; return Promise.resolve(); },
      removeItem: (_key: string) => { _memToken = null; return Promise.resolve(); },
    };
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    token: null, userId: null, sessionId: null,
    isLoggedIn: false, isLoading: true,
  });

  useEffect(() => {
    (async () => {
      try {
        const storage = await getStorage();
        const savedToken = await storage.getItem(STORAGE_KEY);
        const savedSession = await storage.getItem(SESSION_KEY);
        if (savedToken) {
          const userId = extractUserId(savedToken);
          const sessionId = savedSession || `${userId}-${Date.now()}`;
          if (!savedSession) await storage.setItem(SESSION_KEY, sessionId);
          setState({ token: savedToken, userId, sessionId, isLoggedIn: true, isLoading: false });
        } else {
          setState(prev => ({ ...prev, isLoading: false }));
        }
      } catch {
        setState(prev => ({ ...prev, isLoading: false }));
      }
    })();
  }, []);

  const login = useCallback(async (token: string) => {
    const storage = await getStorage();
    await storage.setItem(STORAGE_KEY, token);
    const userId = extractUserId(token);
    const sessionId = userId; // stable per user — same user always loads same history
    await storage.setItem(SESSION_KEY, sessionId);
    setState({ token, userId, sessionId, isLoggedIn: true, isLoading: false });
  }, []);

  const logout = useCallback(async () => {
    const storage = await getStorage();
    await storage.removeItem(STORAGE_KEY);
    await storage.removeItem(SESSION_KEY);
    setState({ token: null, userId: null, sessionId: null, isLoggedIn: false, isLoading: false });
  }, []);

  const switchUser = useCallback(async (token: string) => {
    await login(token);
  }, [login]);

  return (
    <AuthContext.Provider value={{ ...state, login, logout, switchUser }}>
      {children}
    </AuthContext.Provider>
  );
}

function extractUserId(token: string): string {
  if (token.startsWith('test-user-')) return token;
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.sub || 'unknown';
  } catch {
    return token.substring(0, 20) + '...';
  }
}
