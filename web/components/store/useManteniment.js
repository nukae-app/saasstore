'use client';

import { useEffect, useState } from 'react';

// null mentre no sabem encara si el mode manteniment està actiu (toggle a
// /admin/configuracio); true/false un cop consultat /config/public.
export function useManteniment() {
  const [actiu, setActiu] = useState(null);

  useEffect(() => {
    fetch('/api/config/public')
      .then(r => (r.ok ? r.json() : null))
      .then(d => setActiu(!!d?.manteniment_actiu))
      .catch(() => setActiu(false));
  }, []);

  return actiu;
}
