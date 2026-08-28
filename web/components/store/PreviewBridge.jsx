'use client';

import { useEffect } from 'react';

// Pont de missatges per a la previsualització en viu del constructor de
// disseny (web/app/admin/disseny-web) — es munta sempre a [locale]/page.jsx
// però només s'activa quan la pàgina es carrega dins un <iframe> amb
// ?admin_preview=1 (l'admin), així que zero efecte per a visitants reals.
// No persisteix res: només aplica canvis provisionals al DOM ja renderitzat
// perquè es vegin abans de prémer "Guardar" (que sí que crida als PATCH
// habituals, igual que abans).
export default function PreviewBridge() {
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (!params.has('admin_preview') || window.self === window.top) return;

    function applyThemeVars(vars) {
      const root = document.documentElement;
      for (const [key, value] of Object.entries(vars || {})) {
        const cssVar = `--${key.replace(/_/g, '-')}`;
        // Un valor buit (p. ex. "Restaurar valors per defecte") ha de
        // treure la propietat perquè el fallback CSS de cada component
        // (var(--radius-card, 24px)) torni a aplicar-se — deixar-la posada
        // amb setProperty('', ...) no la buida.
        if (value) root.style.setProperty(cssVar, value);
        else root.style.removeProperty(cssVar);
      }
    }

    function applyCustomCss(css) {
      let tag = document.getElementById('__admin_preview_css');
      if (!tag) {
        tag = document.createElement('style');
        tag.id = '__admin_preview_css';
        document.head.appendChild(tag);
      }
      tag.textContent = css || '';
    }

    function applyBlockField({ blockId, field, value }) {
      // El fons (color/imatge) s'aplica com a estil inline sobre el propi
      // element [data-block-id], no sobre un fill amb data-field — és
      // comú a hero/text/testimonials (ver BackgroundFieldset.jsx).
      if (field === 'background_color' || field === 'background_image_url') {
        const root = document.querySelector(`[data-block-id="${blockId}"]`);
        if (!root) return;
        if (field === 'background_image_url') {
          root.style.backgroundImage = value ? `linear-gradient(rgba(255,255,255,0.55), rgba(255,255,255,0.55)), url(${value})` : '';
          root.style.backgroundSize = value ? 'cover' : '';
          root.style.backgroundPosition = value ? 'center' : '';
        } else {
          root.style.backgroundColor = value || '';
        }
        return;
      }
      const el = document.querySelector(`[data-block-id="${blockId}"] [data-field="${field}"]`);
      if (!el) return;
      // Un camp de text es reflecteix mutant textContent; un camp que és en
      // realitat un atribut (p. ex. l'enllaç del CTA) es marca al propi
      // element amb data-attr="href" perquè aquest pont no hagi de saber
      // camp per camp quina mena de valor és.
      const attr = el.dataset.attr;
      if (attr) el.setAttribute(attr, value || '');
      else el.textContent = value || '';
    }

    function handleMessage(e) {
      if (e.origin !== window.location.origin || e.source !== window.parent) return;
      const msg = e.data;
      if (!msg || typeof msg !== 'object') return;
      switch (msg.type) {
        case 'theme-vars': applyThemeVars(msg.vars); break;
        case 'custom-css': applyCustomCss(msg.css); break;
        // Un bloc nou o buit encara no existeix al DOM (el seu component
        // torna null sense contingut), així que aquest camp és una millora
        // de cortesia quan el bloc ja es renderitza — mai la font de veritat:
        // el botó "Guardar canvis" de l'admin sempre acaba enviant 'reload'.
        case 'block-field': applyBlockField(msg); break;
        case 'reload': window.location.reload(); break;
        default: break;
      }
    }

    window.addEventListener('message', handleMessage);
    window.parent.postMessage({ type: 'preview-ready' }, window.location.origin);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  return null;
}
