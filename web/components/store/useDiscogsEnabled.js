'use client';

import { useEffect, useState } from 'react';

// Mismo patrón que useManteniment.js: null hasta que se resuelve
// /config/public, luego true/false (interruptor por tenant, ver
// ConfiguracioBotiga.discogs_habilitat).
export function useDiscogsEnabled() {
  const [enabled, setEnabled] = useState(null);

  useEffect(() => {
    fetch('/api/config/public')
      .then(r => (r.ok ? r.json() : null))
      .then(d => setEnabled(!!d?.discogs_habilitat))
      .catch(() => setEnabled(false));
  }, []);

  return enabled;
}
