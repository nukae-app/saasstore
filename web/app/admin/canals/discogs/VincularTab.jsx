'use client';

// Pestaña Vincular: releases con stock activo y sin ID de Discogs (altas a mano: novedades que aún no
// estaban en Discogs). Busca candidatos (EAN primero), permite vincular a mano o aplazar. Solo LEE de
// Discogs, así que funciona también en modo solo lectura. Vincular NO publica: el release pasa a
// "Pendent" en Listings y allí sigue su flujo de publicación.

import { useState, useEffect, useCallback } from 'react';
import { Button } from '../../../../components/ui/button';
import MIcon from '../../../../components/ui/m-icon';
import { CH, PAGE, Badge, ErrorBox, api, fmtDate } from './shared';

const VINCULAR = `${CH}/vincular`;
const FILTRES = [
  { key: 'pendents', label: 'Pendents' },
  { key: 'amb_ean', label: 'Amb EAN' },
  { key: 'sense_ean', label: 'Sense EAN' },
  { key: 'ajornats', label: 'Ajornats' },
];
const VIA = {
  ean: { label: 'Coincideix per EAN', cls: 'bg-green-100 text-green-800' },
  text_exacte: { label: 'Text exacte', cls: 'bg-blue-100 text-blue-800' },
  text: { label: 'Text', cls: 'bg-surface-container-high text-secondary-foreground' },
};
const MAX_RONDES = 10;

export default function VincularTab({ t, goTab }) {
  const [filtre, setFiltre] = useState('pendents');
  const [q, setQ] = useState('');
  const [page, setPage] = useState(0);
  const [data, setData] = useState({ total: 0, counts: {}, rows: [] });
  const [open, setOpen] = useState(null);       // release_id desplegado
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [auto, setAuto] = useState(false);
  const [enriching, setEnriching] = useState(false);

  const load = useCallback(async () => {
    const p = new URLSearchParams({ filtre, limit: String(PAGE), offset: String(page * PAGE) });
    if (q.trim()) p.set('q', q.trim());
    const r = await api(`${VINCULAR}?${p}`);
    if (r.ok) setData(r.data);
  }, [filtre, q, page]);

  useEffect(() => { load(); }, [load]);

  async function runAuto() {
    setError(''); setMsg(''); setAuto(true);
    const tot = { revisats: 0, vinculats: 0, ambigus: 0, sense_resultat: 0, errors: 0 };
    try {
      for (let i = 0; i < MAX_RONDES; i++) {
        const r = await api(`${VINCULAR}/auto`, { method: 'POST' });
        if (!r.ok) { setError(r.data.detail || t('discogs.link.auto_error', 'No s\'ha pogut cercar per EAN.')); break; }
        Object.keys(tot).forEach((k) => { tot[k] += r.data[k] || 0; });
        if (r.data.aturat) { setError(r.data.aturat); break; }
        if (r.data.revisats === 0) break;
        setMsg(`${tot.revisats} ${t('discogs.link.checked', 'revisats')} · ${tot.vinculats} ${t('discogs.link.linked', 'vinculats')}…`);
      }
      setMsg(`${t('discogs.link.auto_done', 'Cerca per EAN acabada')}: ${tot.revisats} ${t('discogs.link.checked', 'revisats')}, `
        + `${tot.vinculats} ${t('discogs.link.linked', 'vinculats')}, ${tot.ambigus} ${t('discogs.link.ambiguous', 'ambigus (per revisar)')}, `
        + `${tot.sense_resultat} ${t('discogs.link.no_result', 'sense resultat')}.`);
    } finally {
      setAuto(false);
      load();
    }
  }

  async function runEnrich() {
    setError(''); setMsg(''); setEnriching(true);
    const r = await api('/admin/discogs/sync/images/start', { method: 'POST' });
    setEnriching(false);
    if (r.ok) setMsg(r.data.message);
    else setError(r.data.detail || t('discogs.link.enrich_error', 'No s\'ha pogut iniciar l\'enriquiment.'));
  }

  async function ajornar(row, ajornat) {
    await api(`${VINCULAR}/${row.release_id}/ajornar`, { method: 'POST', body: { ajornat } });
    if (open === row.release_id) setOpen(null);
    load();
  }

  const pages = Math.max(1, Math.ceil(data.total / PAGE));

  return (
    <div className="space-y-4">
      <p className="text-sm text-secondary-foreground max-w-3xl">
        {t('discogs.link.intro', 'Discos a la venda que encara no tenen fitxa de Discogs (p. ex. novetats donades d\'alta a mà). Busca\'ls per codi de barres i vincula\'ls. Vincular només llegeix de Discogs: no publica res; el disc passa a "Pendent" a Listings.')}
      </p>
      <ErrorBox>{error}</ErrorBox>
      {msg && <div className="bg-blue-50 border border-blue-200 text-blue-900 rounded-xl px-4 py-2 text-sm">{msg}</div>}

      <div className="flex items-center gap-2 flex-wrap">
        <Button size="sm" onClick={runAuto} disabled={auto}>
          <MIcon name={auto ? 'progress_activity' : 'barcode_scanner'} size={14} className={auto ? 'animate-spin' : ''} />
          {auto ? t('discogs.link.searching', 'Cercant…') : t('discogs.link.auto', 'Cercar coincidències per EAN')}
        </Button>
        <Button size="sm" variant="secondary" onClick={runEnrich} disabled={enriching}
          title={t('discogs.link.enrich_hint', 'Omple caràtula, gènere, estils, EAN, tracklist i crèdits dels discos ja vinculats. No toca estoc ni preus.')}>
          <MIcon name={enriching ? 'progress_activity' : 'image'} size={14} className={enriching ? 'animate-spin' : ''} />
          {t('discogs.link.enrich', 'Enriquir dades dels vinculats')}
        </Button>
        <Button size="sm" variant="secondary" onClick={() => goTab('listings')}>
          {t('discogs.link.go_listings', 'Anar a Listings')}
        </Button>
      </div>

      <div className="bg-card rounded-2xl border border-outline-variant shadow-sm overflow-hidden">
        <div className="p-4 flex items-center gap-3 flex-wrap border-b border-outline-variant">
          <div className="flex gap-1 bg-surface-container-high p-1 rounded-xl flex-wrap">
            {FILTRES.map((f) => (
              <button key={f.key} type="button" onClick={() => { setFiltre(f.key); setPage(0); setOpen(null); }}
                className={`px-3 py-1 rounded-lg text-sm transition-colors ${filtre === f.key ? 'bg-card text-on-surface shadow-sm font-medium' : 'text-secondary-foreground hover:text-on-surface'}`}>
                {t(`discogs.link.f_${f.key}`, f.label)} ({data.counts[f.key] ?? 0})
              </button>
            ))}
          </div>
          <input value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }}
            placeholder={t('discogs.link.search_ph', 'Cerca per artista, títol o EAN…')}
            className="flex-1 min-w-[200px] border border-outline-variant rounded-xl px-3 py-2 text-sm bg-card" />
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-surface-container-high text-xs text-secondary-foreground border-b border-outline-variant">
              <tr>
                <th className="px-3 py-3 text-left font-medium">{t('discogs.canal.col_disc', 'Disc')}</th>
                <th className="px-3 py-3 text-left font-medium">EAN</th>
                <th className="px-3 py-3 text-right font-medium">{t('discogs.link.col_items', 'A la venda')}</th>
                <th className="px-3 py-3 text-left font-medium">{t('discogs.link.col_last', 'Última cerca')}</th>
                <th className="px-3 py-3" />
              </tr>
            </thead>
            <tbody>
              {data.rows.length === 0 && (
                <tr><td colSpan={5} className="px-3 py-8 text-center text-secondary-foreground">
                  {t('discogs.link.empty', 'No hi ha cap disc per vincular.')}
                </td></tr>
              )}
              {data.rows.map((r) => [
                <tr key={r.release_id} className="border-b border-outline-variant">
                  <td className="px-3 py-2.5">
                    <span className="font-medium text-on-surface">{r.artista || '—'}</span>
                    <span className="text-secondary-foreground"> — {r.titulo}</span>
                    {r.formato && <span className="text-xs text-secondary-foreground"> · {r.formato}</span>}
                  </td>
                  <td className="px-3 py-2.5 font-mono text-xs">
                    {r.ean || <Badge>{t('discogs.link.no_ean', 'Sense EAN')}</Badge>}
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{r.num_items}</td>
                  <td className="px-3 py-2.5 text-secondary-foreground">{r.ultima_cerca ? fmtDate(r.ultima_cerca) : '—'}</td>
                  <td className="px-3 py-2.5 text-right whitespace-nowrap">
                    {!r.ajornat && (
                      <button type="button" className="text-xs text-primary hover:underline"
                        onClick={() => setOpen(open === r.release_id ? null : r.release_id)}>
                        {open === r.release_id ? t('discogs.listings.hide', 'Amaga') : t('discogs.link.search', 'Cerca i vincula')}
                      </button>
                    )}
                    <button type="button" className="ml-3 text-xs text-secondary-foreground hover:text-on-surface hover:underline"
                      onClick={() => ajornar(r, !r.ajornat)}>
                      {r.ajornat ? t('discogs.link.restore', 'Recupera') : t('discogs.link.postpone', 'Ajorna')}
                    </button>
                  </td>
                </tr>,
                open === r.release_id && (
                  <tr key={`${r.release_id}-c`} className="bg-surface-container-high/40 border-b border-outline-variant">
                    <td colSpan={5} className="px-4 py-3">
                      <Candidats t={t} row={r} onLinked={() => { setOpen(null); load(); }} />
                    </td>
                  </tr>
                ),
              ])}
            </tbody>
          </table>
        </div>

        <div className="p-3 flex items-center justify-between text-xs text-secondary-foreground border-t border-outline-variant">
          <span>{data.total} {t('discogs.link.total', 'discos')}</span>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="secondary" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>‹</Button>
            <span>{page + 1} / {pages}</span>
            <Button size="sm" variant="secondary" disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}>›</Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Candidats({ t, row, onLinked }) {
  const [loading, setLoading] = useState(true);
  const [cands, setCands] = useState([]);
  const [text, setText] = useState('');
  const [manualId, setManualId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [conflict, setConflict] = useState(null);   // { id, detail }

  const search = useCallback(async (query) => {
    setLoading(true); setError('');
    const p = query ? `?q=${encodeURIComponent(query)}` : '';
    const r = await api(`${VINCULAR}/${row.release_id}/candidats${p}`);
    setLoading(false);
    if (r.ok) setCands(r.data.candidats); else setError(r.data.detail || t('discogs.link.search_error', 'No s\'ha pogut consultar Discogs.'));
  }, [row.release_id, t]);

  useEffect(() => { search(''); }, [search]);

  async function vincular(id, force = false) {
    setBusy(true); setError(''); setConflict(null);
    const r = await api(`${VINCULAR}/${row.release_id}`, { method: 'POST', body: { discogs_release_id: Number(id), force } });
    setBusy(false);
    if (r.ok) { onLinked(); return; }
    if (r.status === 409 && r.data.detail?.release_id) setConflict({ id, detail: r.data.detail });
    else setError(typeof r.data.detail === 'string' ? r.data.detail : t('discogs.link.link_error', 'No s\'ha pogut vincular.'));
  }

  const viaOf = (c) => (c.via === 'ean' ? VIA.ean : c.exacte ? VIA.text_exacte : VIA.text);

  return (
    <div className="space-y-3">
      <ErrorBox>{error}</ErrorBox>
      {conflict && (
        <div className="bg-amber-50 border border-amber-200 text-amber-900 rounded-xl px-4 py-3 text-sm space-y-2">
          <p>{conflict.detail.message} ({conflict.detail.artista} — {conflict.detail.titulo})</p>
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => vincular(conflict.id, true)}>
            {t('discogs.link.link_anyway', 'Vincula igualment')}
          </Button>
        </div>
      )}
      {loading ? (
        <p className="text-sm text-secondary-foreground flex items-center gap-2">
          <MIcon name="progress_activity" size={14} className="animate-spin" /> {t('discogs.link.searching', 'Cercant…')}
        </p>
      ) : cands.length === 0 ? (
        <p className="text-sm text-secondary-foreground">
          {row.ean
            ? t('discogs.link.none_ean', 'Discogs encara no té cap fitxa amb aquest EAN ni coincidència per text.')
            : t('discogs.link.none', 'Cap coincidència a Discogs.')}
        </p>
      ) : (
        <ul className="space-y-1">
          {cands.map((c) => (
            <li key={c.discogs_release_id} className="flex items-center gap-3 bg-card border border-outline-variant rounded-lg px-3 py-2">
              {c.imagen_url && <img src={c.imagen_url} alt="" width={36} height={36} className="rounded object-cover w-9 h-9" />}
              <div className="min-w-0 flex-1">
                <p className="text-sm text-on-surface truncate">
                  <span className="font-medium">{c.artista || '—'}</span> — {c.titulo}
                </p>
                <p className="text-xs text-secondary-foreground truncate">
                  {[c.formato, c.anio, c.sello].filter(Boolean).join(' · ')} ·{' '}
                  <a href={`https://www.discogs.com/release/${c.discogs_release_id}`} target="_blank" rel="noreferrer" className="text-primary hover:underline">
                    #{c.discogs_release_id}
                  </a>
                </p>
              </div>
              <Badge cls={viaOf(c).cls}>{viaOf(c).label}</Badge>
              <Button size="sm" disabled={busy} onClick={() => vincular(c.discogs_release_id)}>
                {t('discogs.link.link', 'Vincula')}
              </Button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex items-center gap-2 flex-wrap">
        <input value={text} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); search(text.trim()); } }}
          placeholder={t('discogs.link.text_ph', 'Cerca per text a Discogs…')}
          className="border border-outline-variant rounded-lg px-3 py-1.5 text-sm bg-card min-w-[220px]" />
        <Button size="sm" variant="secondary" disabled={!text.trim() || loading} onClick={() => search(text.trim())}>
          {t('discogs.link.search_btn', 'Cerca')}
        </Button>
        <span className="text-xs text-secondary-foreground mx-2">{t('discogs.link.or_id', 'o ID de Discogs:')}</span>
        <input value={manualId} onChange={(e) => setManualId(e.target.value.replace(/\D/g, ''))} inputMode="numeric"
          placeholder="1234567"
          className="border border-outline-variant rounded-lg px-3 py-1.5 text-sm bg-card w-32 font-mono" />
        <Button size="sm" variant="secondary" disabled={!manualId || busy} onClick={() => vincular(manualId)}>
          {t('discogs.link.link', 'Vincula')}
        </Button>
      </div>
    </div>
  );
}
