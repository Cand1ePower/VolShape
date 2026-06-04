import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
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
  getValidToken: () => Promise<string | null>;
  setSessionId: (sessionId: string | null) => Promise<void>;
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
  getValidToken: async () => null,
  setSessionId: async () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

const ACCESS_KEY = 'volshape_access_token';
const REFRESH_KEY = 'volshape_refresh_token';
const SESSION_KEY = 'volshape_session_id';

let memoryStorage: Record<string, string | null> = {};

function getScopedSessionKey(userId?: string | null) {
  return userId ? `${SESSION_KEY}:${userId}` : SESSION_KEY;
}

function isJwtExpiringSoon(token: string | null, bufferSeconds = 60) {
  if (!token) return true;
  try {
    const [, payloadPart] = token.split('.');
    if (!payloadPart) return true;
    const normalized = payloadPart.replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized + '='.repeat((4 - (normalized.length % 4 || 4)) % 4);
    const bufferCtor = (globalThis as any).Buffer;
    const decoded = Platform.OS === 'web'
      ? atob(padded)
      : bufferCtor
        ? bufferCtor.from(padded, 'base64').toString('utf-8')
        : padded;
    const payload = JSON.parse(decoded);
    if (!payload?.exp) return true;
    const nowSeconds = Math.floor(Date.now() / 1000);
    return payload.exp - nowSeconds <= bufferSeconds;
  } catch {
    return true;
  }
}

async function getStorage() {
  if (Platform.OS === 'web') {
    return {
      getItem: (key: string) => Promise.resolve(localStorage.getItem(key)),
      setItem: (key: string, value: string) => {
        localStorage.setItem(key, value);
        return Promise.resolve();
      },
      removeItem: (key: string) => {
        localStorage.removeItem(key);
        return Promise.resolve();
      },
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
      getItem: (key: string) => Promise.resolve(memoryStorage[key] ?? null),
      setItem: (key: string, value: string) => {
        memoryStorage[key] = value;
        return Promise.resolve();
      },
      removeItem: (key: string) => {
        memoryStorage[key] = null;
        return Promise.resolve();
      },
    };
  }
}

function stateFromAuthPayload(payload: any, refreshToken: string | null, sessionId: string | null): AuthState {
  const user = payload.user;
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
  const stateRef = useRef(state);
  const refreshPromiseRef = useRef<Promise<string | null> | null>(null);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  const persistSessionId = useCallback(async (sessionId: string | null, userId?: string | null) => {
    const storage = await getStorage();
    if (sessionId) {
      await storage.setItem(SESSION_KEY, sessionId);
      if (userId) {
        await storage.setItem(getScopedSessionKey(userId), sessionId);
      }
    } else {
      await storage.removeItem(SESSION_KEY);
    }
  }, []);

  const persistAuth = useCallback(
    async (accessToken: string, refreshToken: string, sessionId?: string | null) => {
      const storage = await getStorage();
      await storage.setItem(ACCESS_KEY, accessToken);
      await storage.setItem(REFRESH_KEY, refreshToken);
      if (sessionId) {
        await storage.setItem(SESSION_KEY, sessionId);
      } else if (sessionId === null) {
        await storage.removeItem(SESSION_KEY);
      }
    },
    []
  );

  const clearAuth = useCallback(async () => {
    const storage = await getStorage();
    await storage.removeItem(ACCESS_KEY);
    await storage.removeItem(REFRESH_KEY);
    await storage.removeItem(SESSION_KEY);
  }, []);

  const setSessionId = useCallback(
    async (sessionId: string | null) => {
      await persistSessionId(sessionId, stateRef.current.userId);
      setState((prev) => ({ ...prev, sessionId }));
    },
    [persistSessionId]
  );

  const getValidToken = useCallback(async () => {
    if (refreshPromiseRef.current) {
      return refreshPromiseRef.current;
    }

    const current = stateRef.current;
    let accessToken = current.token;
    let refreshToken = current.refreshToken;
    let sessionId = current.sessionId;

    if (!accessToken || !refreshToken || !sessionId) {
      const storage = await getStorage();
      accessToken = accessToken || (await storage.getItem(ACCESS_KEY));
      refreshToken = refreshToken || (await storage.getItem(REFRESH_KEY));
      const scopedSessionId = current.userId ? await storage.getItem(getScopedSessionKey(current.userId)) : null;
      sessionId = sessionId || scopedSessionId || (await storage.getItem(SESSION_KEY));
    }

    if (accessToken && !refreshToken) {
      return accessToken;
    }

    if (accessToken && !isJwtExpiringSoon(accessToken)) {
      return accessToken;
    }

    if (!refreshToken) {
      return accessToken;
    }

    const refreshTask = (async () => {
      try {
        const refreshResp = await apiFetch('/api/auth/refresh', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Connection: 'close' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!refreshResp.ok) {
          throw new Error('refresh failed');
        }
        const refreshed = await refreshResp.json();
        const latestSessionId = stateRef.current.sessionId || sessionId;
        await persistAuth(refreshed.access_token, refreshToken, latestSessionId);
        setState((prev) => ({
          ...prev,
          token: refreshed.access_token,
          refreshToken,
          userId: refreshed.user?.id || prev.userId,
          user: refreshed.user || prev.user,
          sessionId: stateRef.current.sessionId || latestSessionId || prev.sessionId,
          quota: refreshed.quota || prev.quota,
          isLoggedIn: true,
          isLoading: false,
        }));
        return refreshed.access_token as string;
      } catch {
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
        return null;
      } finally {
        refreshPromiseRef.current = null;
      }
    })();

    refreshPromiseRef.current = refreshTask;
    return refreshTask;
  }, [clearAuth, persistAuth]);

  const refreshMe = useCallback(async () => {
    const validToken = await getValidToken();
    if (!validToken) {
      return;
    }
    const resp = await apiFetch('/api/auth/me', {
      headers: { Authorization: `Bearer ${validToken}`, Connection: 'close' },
    });
    if (!resp.ok) {
      throw new Error('登录已过期');
    }
    const data = await resp.json();
    setState((prev) => ({
      ...prev,
      user: data.user,
      userId: data.user?.id || prev.userId,
      quota: data.quota,
      isLoggedIn: true,
      isLoading: false,
    }));
  }, [getValidToken]);

  useEffect(() => {
    (async () => {
      const storage = await getStorage();
      const savedAccess = await storage.getItem(ACCESS_KEY);
      const savedRefresh = await storage.getItem(REFRESH_KEY);

      if (!savedAccess || !savedRefresh) {
        setState((prev) => ({ ...prev, isLoading: false }));
        return;
      }

      try {
        const meResp = await apiFetch('/api/auth/me', {
          headers: { Authorization: `Bearer ${savedAccess}`, Connection: 'close' },
        });
        if (meResp.ok) {
          const meData = await meResp.json();
          const scopedSessionId = await storage.getItem(getScopedSessionKey(meData.user.id));
          const savedSessionId = scopedSessionId || (await storage.getItem(SESSION_KEY));
          setState({
            token: savedAccess,
            refreshToken: savedRefresh,
            userId: meData.user.id,
            user: meData.user,
            sessionId: savedSessionId,
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
        if (!refreshResp.ok) {
          throw new Error('refresh failed');
        }
        const refreshed = await refreshResp.json();
        const scopedSessionId = await storage.getItem(getScopedSessionKey(refreshed.user.id));
        const savedSessionId = scopedSessionId || (await storage.getItem(SESSION_KEY));
        await persistAuth(refreshed.access_token, savedRefresh, savedSessionId);
        setState(stateFromAuthPayload(refreshed, savedRefresh, savedSessionId));
      } catch {
        await clearAuth();
        setState((prev) => ({ ...prev, isLoading: false }));
      }
    })();
  }, [clearAuth, persistAuth]);

  const authenticate = useCallback(
    async (path: '/api/auth/login' | '/api/auth/register', body: any) => {
      const resp = await apiFetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Connection: 'close' },
        body: JSON.stringify(body),
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.detail || '认证失败');
      }
      await persistAuth(data.access_token, data.refresh_token, null);
      setState(stateFromAuthPayload(data, data.refresh_token, null));
    },
    [persistAuth]
  );

  const login = useCallback(async (email: string, password: string) => {
    await authenticate('/api/auth/login', { email, password });
  }, [authenticate]);

  const register = useCallback(async (email: string, password: string, username?: string) => {
    await authenticate('/api/auth/register', { email, password, username });
  }, [authenticate]);

  const logout = useCallback(async () => {
    const savedRefresh = stateRef.current.refreshToken;
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
  }, [clearAuth]);

  const switchUser = useCallback(async (email: string, password: string) => {
    await login(email, password);
  }, [login]);

  return (
    <AuthContext.Provider
      value={{
        ...state,
        login,
        register,
        logout,
        switchUser,
        refreshMe,
        getValidToken,
        setSessionId,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
