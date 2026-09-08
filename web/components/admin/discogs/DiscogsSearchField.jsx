'use client';

import { useState } from 'react';
import MIcon from '../../ui/m-icon';
import { useT } from '../../../app/lib/i18n';
import { useDiscogsSearch, enrichDiscogsResult } from '../../../app/lib/discogs';

export function CoverImg({ url, size = 36 }) {
  const [failed, setFailed] = useState(false);
  if (!url || failed) return (
    <div className="rounded-lg bg-surface-container-high border border-outline-variant shrink-0 flex items-center justify-center" style={{ width: size, height: size }}>
      <MIcon name="album" size={Math.round(size * 0.4)} className="text-secondary-foreground" />
    </div>
  );
  return (
    <img src={url} alt="" width={size} height={size} onError={() => setFailed(true)}
      className="rounded-lg object-cover bg-surface-container-high shrink-0" style={{ width: size, height: size }} />
  );
}

/**
 * Buscador de discos en Discogs, compartido por todas las pantallas de admin que
 * necesitan resolver un release de Discogs (alta de catálogo, comandas a proveedor,
 * compras a particulares, solicitudes, peticiones del club).
 *
 * Al elegir un resultado, pide la ficha completa (/discogs/release/{id}) antes de
 * llamar a onPick, así el llamante recibe siempre el objeto enriquecido (tracklist,
 * créditos, estilos, país...) sin tener que pedirla él mismo.
 */
export default function DiscogsSearchField({
  onPick, disabled = false, placeholder, variant = 'dropdown', className = '', autoFocus = false,
}) {
  const t = useT();
  const { query, results, searching, handleChange, reset } = useDiscogsSearch();
  const [resolving, setResolving] = useState(false);
  const busy = disabled || resolving;

  async function pick(result) {
    setResolving(true);
    try {
      const full = await enrichDiscogsResult(result);
      await onPick(full);
    } finally {
      setResolving(false);
      reset();
    }
  }

  const isDropdown = variant === 'dropdown';

  return (
    <div className={`relative ${className}`}>
      <input
        value={query}
        onChange={e => handleChange(e.target.value)}
        placeholder={placeholder || t('purchases.discogs_search_ph', 'Cerca a Discogs...')}
        disabled={busy}
        autoFocus={autoFocus}
        className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
      />
      {(searching || resolving) && (
        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-secondary-foreground flex items-center gap-1 bg-card pl-1">
          <MIcon name="progress_activity" size={12} className="animate-spin" /> {t('common.searching', 'Cercant…')}
        </span>
      )}
      {results.length > 0 && (
        <div className={isDropdown
          ? 'absolute top-full left-0 right-0 mt-1 bg-card border border-outline-variant rounded-xl shadow-lg z-10 overflow-hidden max-h-72 overflow-y-auto'
          : 'mt-1 max-h-52 overflow-y-auto space-y-1 border border-outline-variant rounded-lg bg-card p-1'}>
          {results.map((r, i) => (
            <button key={i} type="button" onClick={() => pick(r)} disabled={busy}
              className={isDropdown
                ? 'w-full flex items-center gap-3 text-left px-3 py-2.5 text-sm hover:bg-surface-container-high border-b border-outline-variant last:border-0 transition-colors disabled:opacity-50'
                : 'w-full flex items-center gap-3 p-2.5 rounded-lg hover:bg-surface-container-high text-left transition-colors disabled:opacity-50'}>
              <CoverImg url={r.imagen_url} size={36} />
              <div className="min-w-0">
                <div className="text-sm font-medium text-on-surface truncate">
                  {r.artista ? <><span className="font-semibold">{r.artista}</span> — {r.titulo}</> : r.titulo}
                </div>
                <div className="text-xs text-secondary-foreground truncate">
                  {[r.sello, r.formato, r.anio, r.genero].filter(Boolean).join(' · ')}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
