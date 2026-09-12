const TOKEN_KEY = 'ulr_admin_token';

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

const sessionExpiredListeners = new Set();

export function onSessionExpired(callback) {
  sessionExpiredListeners.add(callback);
  return () => sessionExpiredListeners.delete(callback);
}

function notifySessionExpired() {
  sessionExpiredListeners.forEach((cb) => cb());
}

// Compartit entre totes les crides concurrents: si el panell dispara varies
// peticions en paral·lel just quan l'access token caduca, NOMÉS la primera
// crida `/auth/refresh` real — la resta esperen la mateixa promesa en comptes
// de presentar cadascuna el mateix refresh token ja rotat (el backend tracta
// això com a reús — possible robatori — i revoca TOTS els refresh tokens de
// l'usuari, tancant la sessió sencera per una carrera benigna).
let refreshPromise = null;

async function refreshAccessToken(base) {
  if (!refreshPromise) {
    refreshPromise = fetch(`${base}/auth/refresh`, { method: 'POST', credentials: 'include' })
      .then(async (r) => {
        if (!r.ok) throw new Error('refresh_failed');
        const { access_token } = await r.json();
        setToken(access_token);
        return access_token;
      })
      .finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}

export async function authFetch(path, options = {}) {
  const base = '/api';
  const token = getToken();

  const isFormData = options.body instanceof FormData;
  const makeReq = (t) =>
    fetch(`${base}${path}`, {
      ...options,
      headers: {
        ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
        ...(t ? { Authorization: `Bearer ${t}` } : {}),
        ...(options.headers || {}),
      },
      cache: 'no-store',
    });

  let res = await makeReq(token);

  if (res.status === 401) {
    try {
      const newToken = await refreshAccessToken(base);
      res = await makeReq(newToken);
    } catch {
      clearToken();
      notifySessionExpired();
      throw new Error('401');
    }
  }

  return res;
}
