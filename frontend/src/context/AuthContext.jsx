import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { authAPI, usersAPI, destroySession } from '../lib/api';
import { hasSession, clearSession, setSession } from '../lib/auth';

// ---------------------------------------------------------------------------
// Global authentication state. The backend owns identity (Neon Auth); this
// context only tracks the loaded profile and session lifecycle.
// ---------------------------------------------------------------------------

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [profile, setProfile] = useState(null);
  const [status, setStatus] = useState(hasSession() ? 'loading' : 'guest'); // loading | authed | guest

  useEffect(() => {
    let cancelled = false;
    async function boot() {
      if (!hasSession()) {
        setStatus('guest');
        return;
      }
      try {
        const me = await usersAPI.me();
        if (!cancelled) {
          setProfile(me);
          setStatus('authed');
        }
      } catch {
        if (!cancelled) {
          clearSession();
          setProfile(null);
          setStatus('guest');
        }
      }
    }
    boot();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email, password) => {
    const data = await authAPI.login({ email, password });
    if (data?.session?.access_token) {
      setSession(data.session.access_token, data.session.refresh_token || '');
    }
    setProfile(data.profile || null);
    setStatus('authed');
    return data;
  }, []);

  const register = useCallback(async (email, password, fullName) => {
    const data = await authAPI.register({ email, password, full_name: fullName });
    if (data?.session?.access_token) {
      setSession(data.session.access_token, data.session.refresh_token || '');
    }
    setProfile(data.profile || null);
    setStatus('authed');
    // India-first default: give every new account INR as preferred currency.
    // Best effort — never blocks the signup flow.
    if (data?.session?.access_token) {
      try {
        const updated = await usersAPI.updateMe({ preferred_currency: 'INR' });
        if (updated) setProfile(updated);
      } catch {
        /* profile keeps the backend default; user can change it in Profile */
      }
    }
    return data;
  }, []);

  const logout = useCallback(async () => {
    await destroySession();
    setProfile(null);
    setStatus('guest');
  }, []);

  const updateProfile = useCallback((partial) => {
    setProfile((prev) => (prev ? { ...prev, ...partial } : prev));
  }, []);

  const reloadProfile = useCallback(async () => {
    const me = await usersAPI.me();
    setProfile(me);
    return me;
  }, []);

  const value = useMemo(
    () => ({ profile, status, isAuthed: status === 'authed', login, register, logout, updateProfile, reloadProfile }),
    [profile, status, login, register, logout, updateProfile, reloadProfile]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
