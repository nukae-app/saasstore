'use client';

import { useCallback, useRef, useState } from 'react';
import { authFetch } from './auth';

/** Búsqueda cruda contra /admin/discogs/search (backend ya throttla ~55/min). */
export async function searchDiscogsReleases(query) {
  const r = await authFetch(`/admin/discogs/search?q=${encodeURIComponent(query)}`);
  const data = await r.json();
  return Array.isArray(data) ? data : (data.results ?? []);
}

/**
 * Los resultados de /discogs/search son "ligeros" (sin tracklist/créditos/estilos/país).
 * Antes de usar un resultado (rellenar un formulario, crear un release) pedimos la
 * ficha completa a /discogs/release/{id} y la fusionamos con lo que ya teníamos.
 */
export async function enrichDiscogsResult(result) {
  if (!result?.discogs_release_id) return result;
  try {
    const r = await authFetch(`/admin/discogs/release/${result.discogs_release_id}`);
    if (r.ok) return { ...result, ...(await r.json()) };
  } catch { /* nos conformamos con los datos de la búsqueda */ }
  return result;
}

/**
 * Busca un release local que ya coincida (por discogs_release_id, o artista+título) y
 * si no existe lo crea. Usado por todas las pantallas de compra al elegir un resultado
 * (de Discogs o metido a mano) para no duplicar releases en el catálogo.
 */
export async function resolveOrCreateRelease(full) {
  const params = new URLSearchParams();
  if (full.discogs_release_id) params.set('discogs_release_id', full.discogs_release_id);
  else { params.set('artista', full.artista || ''); params.set('titulo', full.titulo || ''); }
  const dupRes = await authFetch(`/admin/releases/check-duplicate?${params.toString()}`);
  const matches = dupRes.ok ? await dupRes.json() : [];
  if (matches.length > 0) {
    const m = matches[0];
    return { id: m.id, artista: m.artista, titulo: m.titulo, sello: m.sello, existing: true };
  }
  const rRes = await authFetch('/admin/releases', {
    method: 'POST',
    body: JSON.stringify({
      artista: full.artista, title: full.titulo, sello: full.sello || null,
      formato: full.formato ? full.formato.split(',')[0].trim() : null,
      anio: full.anio ? parseInt(full.anio) : null, genero: full.genero || null,
      estilos: full.estilos || null, pais: full.pais || null, image_url: full.imagen_url || null,
      tracklist: full.tracklist || null, credits: full.credits || null,
      discogs_release_id: full.discogs_release_id ? parseInt(full.discogs_release_id) : null,
    }),
  });
  const { id } = await rRes.json();
  return { id, artista: full.artista, titulo: full.titulo, sello: full.sello, existing: false };
}

/** Estado + debounce de una búsqueda a Discogs, para <DiscogsSearchField>. */
export function useDiscogsSearch({ minLength = 3, debounceMs = 400 } = {}) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const timer = useRef(null);

  const handleChange = useCallback((val) => {
    setQuery(val);
    clearTimeout(timer.current);
    if (val.trim().length < minLength) { setResults([]); return; }
    timer.current = setTimeout(async () => {
      setSearching(true);
      try { setResults(await searchDiscogsReleases(val)); }
      finally { setSearching(false); }
    }, debounceMs);
  }, [minLength, debounceMs]);

  const reset = useCallback(() => {
    clearTimeout(timer.current);
    setQuery(''); setResults([]);
  }, []);

  return { query, results, searching, handleChange, reset };
}
