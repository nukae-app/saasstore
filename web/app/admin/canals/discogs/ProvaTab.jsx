'use client';

// Pestaña de diagnóstico: lanza UNA búsqueda por código de barras contra la API real de Discogs y
// muestra la respuesta tal cual (estado HTTP, resultados). No guarda nada. Sirve para comprobar que
// /database/search?barcode= funciona con el token configurado; se puede retirar cuando ya esté probado.

import { useState } from 'react';
import { Button } from '../../../../components/ui/button';
import MIcon from '../../../../components/ui/m-icon';
import { CH, Badge, ErrorBox, api } from './shared';

export default function ProvaTab({ t }) {
  const [ean, setEan] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [res, setRes] = useState(null);

  async function prova(e) {
    e.preventDefault();
    setLoading(true); setError(''); setRes(null);
    const r = await api(`${CH}/vincular/prova?ean=${encodeURIComponent(ean)}`);
    setLoading(false);
    if (r.ok) setRes(r.data);
    else setError(typeof r.data.detail === 'string' ? r.data.detail : t('discogs.prova.error', 'No s\'ha pogut fer la prova.'));
  }

  return (
    <div className="space-y-4 max-w-3xl">
      <p className="text-sm text-secondary-foreground">
        {t('discogs.prova.intro', 'Prova de la cerca per codi de barres a Discogs. Fa una sola consulta de lectura i no desa res.')}
      </p>
      <form onSubmit={prova} className="flex items-center gap-2 flex-wrap">
        <input value={ean} onChange={(e) => setEan(e.target.value)} inputMode="numeric" autoFocus
          placeholder={t('discogs.prova.ph', 'EAN / codi de barres (escaneja o enganxa)')}
          className="border border-outline-variant rounded-xl px-3 py-2 text-sm bg-card font-mono min-w-[280px]" />
        <Button type="submit" disabled={!ean.trim() || loading}>
          <MIcon name={loading ? 'progress_activity' : 'science'} size={14} className={loading ? 'animate-spin' : ''} />
          {t('discogs.prova.run', 'Provar')}
        </Button>
      </form>
      <ErrorBox>{error}</ErrorBox>

      {res && (
        <div className="bg-card rounded-2xl border border-outline-variant shadow-sm p-5 space-y-3">
          <div className="flex items-center gap-3 flex-wrap text-sm">
            <Badge cls={res.http_status === 200 ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}>HTTP {res.http_status}</Badge>
            <span className="font-mono text-xs">{res.ean}</span>
            <span className="text-secondary-foreground">
              {res.total_discogs ?? res.resultats.length} {t('discogs.prova.results', 'resultats')}
              {res.ratelimit_restant != null && ` · ${t('discogs.prova.rate', 'peticions restants aquest minut')}: ${res.ratelimit_restant}`}
            </span>
          </div>
          {res.error && <p className="text-sm text-red-700 break-all">{res.error}</p>}
          {res.http_status === 200 && res.resultats.length === 0 && (
            <p className="text-sm text-secondary-foreground">
              {t('discogs.prova.none', 'La API respon bé però no hi ha cap fitxa amb aquest EAN (la cerca funciona; potser Discogs encara no té el disc).')}
            </p>
          )}
          <ul className="space-y-1">
            {res.resultats.map((c) => (
              <li key={c.discogs_release_id} className="flex items-center gap-3 border border-outline-variant rounded-lg px-3 py-2">
                {c.imagen_url && <img src={c.imagen_url} alt="" width={36} height={36} className="rounded object-cover w-9 h-9" />}
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-on-surface truncate"><span className="font-medium">{c.artista || '—'}</span> — {c.titulo}</p>
                  <p className="text-xs text-secondary-foreground truncate">
                    {[c.formato, c.anio, c.sello].filter(Boolean).join(' · ')} ·{' '}
                    <a href={`https://www.discogs.com/release/${c.discogs_release_id}`} target="_blank" rel="noreferrer" className="text-primary hover:underline">#{c.discogs_release_id}</a>
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
