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
    const refresh = await fetch(`${base}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    });
    if (refresh.ok) {
      const { access_token } = await refresh.json();
      setToken(access_token);
      res = await makeReq(access_token);
    } else {
      clearToken();
      notifySessionExpired();
      throw new Error('401');
    }
  }

  return res;
}
