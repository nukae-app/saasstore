'use client';

import { useEffect, useState } from 'react';

// null mentre no sabem encara si el club del disc està actiu (toggle a
// /admin/configuracio); true/false un cop consultat /config/public.
export function useSubscripcionsActives() {
  const [actiu, setActiu] = useState(null);

  useEffect(() => {
    fetch('/api/config/public')
      .then(r => (r.ok ? r.json() : null))
      .then(d => setActiu(!!d?.subscripcions_actives))
      .catch(() => setActiu(false));
  }, []);

  return actiu;
}
