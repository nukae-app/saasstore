'use client';

import { useEffect, useState } from 'react';

// Mismo patrón que useManteniment.js/useDiscogsEnabled.js: null hasta que
// se resuelve /config/public, luego el slug del vertical del tenant
// ("records", "floristry"...).
export function useTenantVertical() {
  const [vertical, setVertical] = useState(null);

  useEffect(() => {
    fetch('/api/config/public')
      .then(r => (r.ok ? r.json() : null))
      .then(d => setVertical(d?.vertical ?? 'records'))
      .catch(() => setVertical('records'));
  }, []);

  return vertical;
}
