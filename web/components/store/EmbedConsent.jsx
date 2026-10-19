'use client';

import { useCallback, useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';

// Contingut de tercers (YouTube, Spotify, Mixcloud...) NO es carrega fins que
// el visitant ho demana: un <iframe> fa que el tercer vegi la IP i hi posi
// cookies abans de cap consentiment (LSSI art. 22.2 / RGPD). Cada embed es
// substitueix per un placeholder; el "Carregar" és el consentiment. Si el
// visitant marca "recorda", es desa per proveïdor (host) a localStorage —
// això és una preferència, no una cookie de seguiment, i es pot revocar
// des del peu ("Gestionar contingut de tercers").

const STORAGE_KEY = 'embed_consent_hosts';

function readHosts() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeHosts(hosts) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(hosts));
  } catch {}
}

export function clearEmbedConsent() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {}
  if (typeof window !== 'undefined') window.dispatchEvent(new Event('embed-consent-changed'));
}

export function hostOf(src) {
  try {
    return new URL(src, 'https://x.invalid').hostname.replace(/^www\./, '');
  } catch {
    return '';
  }
}

// Hosts recordats + subscripció als canvis (revocació des del peu o d'un
// altre embed de la mateixa pàgina).
export function useRememberedHosts() {
  const [hosts, setHosts] = useState([]);
  useEffect(() => {
    const sync = () => setHosts(readHosts());
    sync();
    window.addEventListener('embed-consent-changed', sync);
    window.addEventListener('storage', sync);
    return () => {
      window.removeEventListener('embed-consent-changed', sync);
      window.removeEventListener('storage', sync);
    };
  }, []);
  const remember = useCallback((host) => {
    const next = Array.from(new Set([...readHosts(), host]));
    writeHosts(next);
    window.dispatchEvent(new Event('embed-consent-changed'));
  }, []);
  return { hosts, remember };
}

export function EmbedPlaceholder({ host, onLoad, className = '', style }) {
  const t = useTranslations('embed');
  const [remember, setRemember] = useState(false);
  return (
    <div
      className={`flex flex-col items-center justify-center gap-3 text-center bg-zinc-100 text-zinc-700 p-5 ${className}`}
      style={style}
    >
      <p className="text-sm max-w-md">{t('notice', { host })}</p>
      <button
        type="button"
        onClick={() => onLoad(remember)}
        className="px-4 py-2 rounded-md bg-zinc-900 text-white text-sm font-medium hover:bg-zinc-700 transition-colors"
      >
        {t('load')}
      </button>
      <label className="flex items-center gap-2 text-xs text-zinc-500 cursor-pointer">
        <input type="checkbox" checked={remember} onChange={e => setRemember(e.target.checked)} />
        {t('remember', { host })}
      </label>
    </div>
  );
}

// Embed individual (blocs de vídeo, pestanya Spotify). `children` es rep com
// a funció que pinta l'<iframe> real només un cop hi ha consentiment.
export default function EmbedConsent({ src, className, style, children }) {
  const host = hostOf(src);
  const { hosts, remember } = useRememberedHosts();
  const [accepted, setAccepted] = useState(false);

  if (accepted || hosts.includes(host)) return children;

  return (
    <EmbedPlaceholder
      host={host}
      className={className}
      style={style}
      onLoad={(rem) => {
        if (rem) remember(host);
        setAccepted(true);
      }}
    />
  );
}
