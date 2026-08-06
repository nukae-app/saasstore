'use client';

import { createContext, useContext, useState, useEffect, useCallback } from 'react';

const TOKEN_KEY = 'ulr_token';

export function getToken() {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(t) { localStorage.setItem(TOKEN_KEY, t); }
export function clearToken() { localStorage.removeItem(TOKEN_KEY); }

const sessionExpiredListeners = new Set();

export function onSessionExpired(callback) {
  sessionExpiredListeners.add(callback);
  return () => sessionExpiredListeners.delete(callback);
}

function notifySessionExpired() {
  sessionExpiredListeners.forEach((cb) => cb());
}

export async function authFetch(path, options = {}) {
  const token = getToken();
  const make = (t) => fetch(`/api${path}`, {
    ...options,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(t ? { Authorization: `Bearer ${t}` } : {}), ...(options.headers || {}) },
  });
  let res = await make(token);
  if (res.status === 401) {
    const r = await fetch('/api/auth/refresh', { method: 'POST', credentials: 'include' });
    if (r.ok) { const { access_token } = await r.json(); setToken(access_token); res = await make(access_token); }
    else { clearToken(); notifySessionExpired(); throw new Error('401'); }
  }
  return res;
}

const AuthContext = createContext({ user: null, loading: true, login: () => {}, logout: async () => {}, refresh: async () => {} });

export function useAuth() { return useContext(AuthContext); }

export default function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const res = await authFetch('/auth/me');
      if (res.ok) setUser(await res.json());
      else setUser(null);
    } catch { setUser(null); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  // Si el refresh token caduca mentre es navega, tornem l'usuari a l'estat
  // desconnectat en lloc de deixar les crides a l'API fallant en silenci.
  useEffect(() => onSessionExpired(() => setUser(null)), []);

  function login(token) {
    setToken(token);
    refresh();
  }

  async function logout() {
    try { await authFetch('/auth/logout', { method: 'POST' }); } catch {}
    clearToken();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}
