'use client';

import { useMemo, useState } from 'react';
import { useTranslations } from 'next-intl';
import { hostOf, useRememberedHosts } from './EmbedConsent';

// Per al contingut HTML lliure (posts de blog i pàgines): els <iframe> que
// l'editor hi ha enganxat (Mixcloud, Bandcamp, YouTube...) es canvien per un
// placeholder abans de pintar-los. Funciona igual en SSR, així que el HTML que
// arriba al navegador ja no conté cap iframe de tercers fins al consentiment.

const IFRAME_RE = /<iframe\b[^>]*?\bsrc\s*=\s*(["'])(.*?)\1[^>]*>\s*(?:<\/iframe>)?/gis;

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

export function gateIframes(html, isAllowed, labels) {
  if (!html) return '';
  return html.replace(IFRAME_RE, (full, _q, src) => {
    const host = hostOf(src);
    if (!host || isAllowed(host, src)) return full;
    const h = escapeHtml(host);
    return (
      `<div class="embed-gate" data-embed-src="${escapeHtml(src)}">` +
      `<p>${escapeHtml(labels.notice.replace('{host}', host))}</p>` +
      `<button type="button" data-embed-load>${escapeHtml(labels.load)}</button>` +
      `<label><input type="checkbox" data-embed-remember> ${escapeHtml(labels.remember.replace('{host}', host))}</label>` +
      `</div>`
    ).replace(/\{host\}/g, h);
  });
}

export default function ConsentHtml({ html, className }) {
  const t = useTranslations('embed');
  const { hosts, remember } = useRememberedHosts();
  const [loadedSrcs, setLoadedSrcs] = useState([]);

  const labels = useMemo(
    () => ({
      notice: t('notice', { host: '{host}' }),
      load: t('load'),
      remember: t('remember', { host: '{host}' }),
    }),
    [t],
  );

  const gated = useMemo(
    () => gateIframes(html, (host, src) => hosts.includes(host) || loadedSrcs.includes(src), labels),
    [html, hosts, loadedSrcs, labels],
  );

  function onClick(e) {
    const btn = e.target.closest?.('[data-embed-load]');
    if (!btn) return;
    const gate = btn.closest('[data-embed-src]');
    if (!gate) return;
    const src = gate.getAttribute('data-embed-src');
    const rem = gate.querySelector('[data-embed-remember]')?.checked;
    if (rem) remember(hostOf(src));
    else setLoadedSrcs(prev => [...prev, src]);
  }

  return <div className={className} onClick={onClick} dangerouslySetInnerHTML={{ __html: gated }} />;
}
