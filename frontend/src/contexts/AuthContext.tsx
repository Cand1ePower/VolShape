import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { Platform } from 'react-native';
import { apiFetch } from '@/services/api';

interface AuthUser {
  id: string;
  email: string;
  username?: string | null;
  role: string;
  status: string;
}

interface AuthState {
  token: string | null;
  refreshToken: string | null;
  userId: string | null;
  user: AuthUser | null;
  sessionId: string | null;
  quota: any | null;
  isLoggedIn: boolean;
  isLoading: boolean;
}

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, username?: string) => Promise<void>;
  logout: () => Promise<void>;
  switchUser: (email: string, password: string) => Promise<void>;
  refreshMe: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  token: null,
  refreshToken: null,
  userId: null,
  user: null,
  sessionId: null,
  quota: null,
  isLoggedIn: false,
  isLoading: true,
  login: async () => {},
  register: async () => {},
  logout: async () => {},
  switchUser: async () => {},
  refreshMe: async () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

const ACCESS_KEY = 'volshape_access_token';
const REFRESH_KEY = 'volshape_refresh_token';
const SESSION_KEY = 'volshape_session_id';

let _mem: Record<string, string | null> = {};

async function getStorage() {
  if (Platform.OS === 'web') {
    return {
      getItem: (key: string) => Promise.resolve(localStorage.getItem(key)),
      setItem: (key: string, value: string) => { localStorage.setItem(key, value); return Promise.resolve(); },
      removeItem: (key: string) => { localStorage.removeItem(key); return Promise.resolve(); },
    };
  }
  try {
    const SecureStore = require('expo-secure-store');
    return {
      getItem: (key: string) => SecureStore.getItemAsync(key),
      setItem: (key: string, value: string) => SecureStore.setItemAsync(key, value),
      removeItem: (key: string) => SecureStore.deleteItemAsync(key),
    };
  } catch {
    return {
      getItem: (key: string) => Promise.resolve(_mem[key] ?? null),
      setItem: (key: string, value: string) => { _mem[key] = value; return Promise.resolve(); },
      removeItem: (key: string) => { _mem[key] = null; return Promise.resolve(); },
    };
  }
}

function stateFromAuthPayload(payload: any, refreshToken: string | null): AuthState {
  const user = payload.user;
  const sessionId = user?.id || null;
  return {
    token: payload.access_token,
    refreshToken,
    userId: user?.id || null,
    user: user || null,
    sessionId,
    quota: payload.quota || null,
    isLoggedIn: !!payload.access_token,
    isLoading: false,
  };
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    token: null,
    refreshToken: null,
    userId: null,
    user: null,
    sessionId: null,
    quota: null,
    isLoggedIn: false,
    isLoading: true,
  });

  const persistAuth = useCallback(async (accessToken: string, refreshToken: string, userId: string) => {
    const storage = await getStorage();
    await storage.setItem(ACCESS_KEY, accessToken);
    await storage.setItem(REFRESH_KEY, refreshToken);
    await storage.setItem(SESSION_KEY, userId);
  }, []);

  const clearAuth = useCallback(async () => {
    const storage = await getStorage();
    await storage.removeItem(ACCESS_KEY);
    await storage.removeItem(REFRESH_KEY);
    await storage.removeItem(SESSION_KEY);
  }, []);

  const refreshMe = useCallback(async () => {
    if (!state.token) return;
    const resp = await apiFetch('/api/auth/me', {
      headers: { Authorization: `Bearer ${state.token}`, Connection: 'close' },
    });
    if (!resp.ok) throw new Error('登录已过期');
    const data = await resp.json();
    setState(prev => ({
      ...prev,
      user: data.user,
      userId: data.user?.id || prev.userId,
      sessionId: data.user?.id || prev.sessionId,
      quota: data.quota,
      isLoggedIn: true,
      isLoading: false,
    }));
  }, [state.token]);

  useEffect(() => {
    (async () => {
      const storage = await getStorage();
      const savedAccess = await storage.getItem(ACCESS_KEY);
      const savedRefresh = await storage.getItem(REFRESH_KEY);
      if (!savedAccess || !savedRefresh) {
        setState(prev => ({ ...prev, isLoading: false }));
        return;
      }

      try {
        const meResp = await apiFetch('/api/auth/me', {
          headers: { Authorization: `Bearer ${savedAccess}`, Connection: 'close' },
        });
        if (meResp.ok) {
          const meData = await meResp.json();
          setState({
            token: savedAccess,
            refreshToken: savedRefresh,
            userId: meData.user.id,
            user: meData.user,
            sessionId: meData.user.id,
            quota: meData.quota,
            isLoggedIn: true,
            isLoading: false,
          });
          return;
        }

        const refreshResp = await apiFetch('/api/auth/refresh', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Connection: 'close' },
          body: JSON.stringify({ refresh_token: savedRefresh }),
        });
        if (!refreshResp.ok) throw new Error('refresh failed');
        const refreshed = await refreshResp.json();
        await persistAuth(refreshed.access_token, savedRefresh, refreshed.user.id);
        setState(stateFromAuthPayload(refreshed, savedRefresh));
      } catch {
        await clearAuth();
        setState(prev => ({ ...prev, isLoading: false }));
      }
    })();
  }, [clearAuth, persistAuth]);

  const authenticate = useCallback(async (path: '/api/auth/login' | '/api/auth/register', body: any) => {
    const resp = await apiFetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Connection: 'close' },
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.detail || '认证失败');
    }
    await persistAuth(data.access_token, data.refresh_token, data.user.id);
    setState(stateFromAuthPayload(data, data.refresh_token));
  }, [persistAuth]);

  const login = useCallback(async (email: string, password: string) => {
    await authenticate('/api/auth/login', { email, password });
  }, [authenticate]);

  const register = useCallback(async (email: string, password: string, username?: string) => {
    await authenticate('/api/auth/register', { email, password, username });
  }, [authenticate]);

  const logout = useCallback(async () => {
    const savedRefresh = state.refreshToken;
    if (savedRefresh) {
      apiFetch('/api/auth/logout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Connection: 'close' },
        body: JSON.stringify({ refresh_token: savedRefresh }),
      }).catch(() => {});
    }
    await clearAuth();
    setState({
      token: null,
      refreshToken: null,
      userId: null,
      user: null,
      sessionId: null,
      quota: null,
      isLoggedIn: false,
      isLoading: false,
    });
  }, [clearAuth, state.refreshToken]);

  const switchUser = useCallback(async (email: string, password: string) => {
    await login(email, password);
  }, [login]);

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout, switchUser, refreshMe }}>
      {children}
    </AuthContext.Provider>
  );
}
