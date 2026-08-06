'use client';

import { useEffect, useState } from 'react';
import { authFetch } from './AuthProvider';

// null mentre no sabem encara si el mòdul de Spotify està actiu al servidor
// (SPOTIFY_ENABLED); true/false un cop consultat /auth/spotify/enabled.
export function useSpotifyEnabled() {
  const [enabled, setEnabled] = useState(null);

  useEffect(() => {
    authFetch('/api/auth/spotify/enabled')
      .then(r => (r.ok ? r.json() : { enabled: false }))
      .then(d => setEnabled(!!d.enabled))
      .catch(() => setEnabled(false));
  }, []);

  return enabled;
}
