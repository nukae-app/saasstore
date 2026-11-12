// Consentimiento de analítica (Faro → Grafana Cloud). LSSI 22.2 / ePrivacy:
// sin decisión afirmativa del visitante NO se inicializa Faro (que guarda una
// sesión en el navegador y envía URL, UA y referrer). Es una preferencia del
// propio visitante, guardada en localStorage con caducidad de 12 meses; hasta
// entonces no se vuelve a preguntar.

const KEY = 'analytics_consent';
const VERSION = 1;
const TTL_MS = 365 * 24 * 60 * 60 * 1000;
export const CONSENT_EVENT = 'analytics-consent-changed';
export const OPEN_BANNER_EVENT = 'open-cookie-banner';

// true = aceptada, false = rechazada, null = sin decisión (o caducada).
export function readAnalyticsConsent() {
  try {
    const parsed = JSON.parse(localStorage.getItem(KEY) || 'null');
    if (!parsed || parsed.v !== VERSION || typeof parsed.analytics !== 'boolean') return null;
    if (Date.now() - parsed.ts > TTL_MS) return null;
    return parsed.analytics;
  } catch {
    return null;
  }
}

export function writeAnalyticsConsent(analytics) {
  try {
    localStorage.setItem(KEY, JSON.stringify({ v: VERSION, analytics, ts: Date.now() }));
  } catch {}
  window.dispatchEvent(new Event(CONSENT_EVENT));
}

export function openCookieBanner() {
  window.dispatchEvent(new Event(OPEN_BANNER_EVENT));
}

// Borra lo que Faro haya dejado en el navegador (clave de sesión, última
// navegación...). Se llama al retirar el consentimiento.
export function clearFaroStorage() {
  for (const storage of [window.localStorage, window.sessionStorage]) {
    try {
      Object.keys(storage)
        .filter((k) => k.startsWith('com.grafana.faro'))
        .forEach((k) => storage.removeItem(k));
    } catch {}
  }
}
