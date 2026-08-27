const TOKEN_KEY = 'superadmin_token';

export function getToken() {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

// A diferencia de app/lib/auth.js (usuarios de tenant): el superadmin es un
// JWT plano de 8h (services/superadmin_security.py), sin cookie de refresh
// ni endpoint /superadmin/refresh — en un 401 no hay nada que reintentar,
// solo limpiar el token y volver al login.
export async function superadminAuthFetch(path, options = {}) {
  const token = getToken();
  const res = await fetch(`/api${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
    cache: 'no-store',
  });

  if (res.status === 401) {
    clearToken();
    if (typeof window !== 'undefined') window.location.href = '/superadmin/login';
  }

  return res;
}
