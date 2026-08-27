'use client';

import { useEffect, useState } from 'react';

// Config pública completa del tenant (/config/public) — mismo endpoint que
// useManteniment.js/useDiscogsEnabled.js/useSubscripcionsActives.js ya
// consultan cada uno por su cuenta; este hook lo usa quien necesite varios
// campos a la vez (p. ej. nombre/slug para el logo del nav) sin duplicar
// las comprobaciones de un solo booleano.
const FALLBACK = { nombre: '', slug: null };

export function useTenantConfig() {
  const [config, setConfig] = useState(FALLBACK);

  useEffect(() => {
    fetch('/api/config/public')
      .then(r => (r.ok ? r.json() : null))
      .then(data => { if (data) setConfig(data); })
      .catch(() => {});
  }, []);

  return config;
}
