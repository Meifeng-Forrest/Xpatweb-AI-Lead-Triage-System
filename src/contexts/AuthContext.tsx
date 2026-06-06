import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { clearAuthToken, fetchMe, login as loginRequest, type AuthUser } from '../services/authApi';

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  can: (permission: string) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadCurrentUser = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const current = await fetchMe();
      setUser(current);
    } catch (err) {
      console.error('[client/auth/context] me_fail', { reason: err instanceof Error ? err.message : 'unknown' });
      setUser(null);
      setError('Please sign in to continue.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCurrentUser();
    const handleAuthRequired = () => {
      setUser(null);
      setError('Your session expired. Please sign in again.');
    };
    window.addEventListener('auth:required', handleAuthRequired);
    return () => window.removeEventListener('auth:required', handleAuthRequired);
  }, [loadCurrentUser]);

  const login = useCallback(async (email: string, password: string) => {
    setLoading(true);
    setError(null);
    try {
      const nextUser = await loginRequest(email, password);
      setUser(nextUser);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed.';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    clearAuthToken();
    setUser(null);
    setError('Signed out.');
  }, []);

  const value = useMemo<AuthContextValue>(() => ({
    user,
    loading,
    error,
    login,
    logout,
    can: (permission: string) => Boolean(user?.permissions.includes(permission)),
  }), [error, loading, login, logout, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return value;
}
