'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { authFetch } from '../../lib/auth';
import { Button } from '../../../components/ui/button';
import MIcon from '../../../components/ui/m-icon';

const PAGE = 100;
const EMPTY_FILTERS = {
  q: '', artista: '', sello: '', genero: '', formato: '',
  anio_min: '', anio_max: '', precio_min: '', precio_max: '', con_stock: '',
};
const FIELDS = [
  ['q', 'Cerca lliure'], ['artista', 'Artista'], ['sello', 'Segell'], ['genero', 'Gènere'],
  ['formato', 'Format (LP, CD…)'], ['anio_min', 'Any des de'], ['anio_max', 'Any fins a'],
  ['precio_min', 'Preu mín. €'], ['precio_max', 'Preu màx. €'],
];

// Mateixos noms que GET /admin/releases; els camps de text passen a llista pels `criteris`.
function toQuery(f) {
  const p = new URLSearchParams();
  Object.entries(f).forEach(([k, v]) => { if (v !== '') p.set(k, v); });
  return p;
}
function toCriteris(f) {
  const c = {};
  Object.entries(f).forEach(([k, v]) => {
    if (v === '') return;
    if (['artista', 'sello', 'genero', 'formato'].includes(k)) c[k] = [v];
    else if (k === 'con_stock') c[k] = v === 'true';
    else if (k === 'q') c[k] = v;
    else c[k] = Number(v);
  });
  return c;
}

export default function GestorEtiquetes({ etiquetes }) {
  const [etiquetaId, setEtiquetaId] = useState(etiquetes[0]?.id ?? null);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [applied, setApplied] = useState(EMPTY_FILTERS);
  const [onlyMissing, setOnlyMissing] = useState(false);
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  const etiqueta = etiquetes.find(e => e.id === etiquetaId);

  const load = useCallback(async () => {
    setLoading(true);
    const p = toQuery(applied);
    p.set('limit', PAGE);
    p.set('sort', 'creacion');
    p.set('dir', 'desc');
    const r = await authFetch(`/admin/releases?${p}`);
    if (r.ok) {
      const d = await r.json();
      setRows(d.releases);
      setTotal(d.total);
    }
    setLoading(false);
  }, [applied]);

  useEffect(() => { load(); setSelected(new Set()); }, [load]);

  const has = useCallback(
    r => r.etiquetes.some(e => e.id === etiquetaId),
    [etiquetaId],
  );
  const visible = useMemo(() => (onlyMissing ? rows.filter(r => !has(r)) : rows), [rows, onlyMissing, has]);

  function toggle(id) {
    setSelected(prev => {
      const n = new Set(prev);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  }
  function selectAllVisible() {
    setSelected(prev => (prev.size === visible.length ? new Set() : new Set(visible.map(r => r.id))));
  }

  async function assignar(body, okText) {
    setBusy(true); setMsg('');
    try {
      const r = await authFetch(`/admin/etiquetes/${etiquetaId}/assignar`, { method: 'POST', body: JSON.stringify(body) });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) { setMsg(d.detail || 'Error'); return; }
      setMsg(`${okText}: ${d.afectats} disc${d.afectats === 1 ? '' : 's'}`);
      setSelected(new Set());
      await load();
    } finally {
      setBusy(false);
    }
  }

  const byIds = accio => assignar(
    { accio, release_ids: [...selected] },
    accio === 'afegir' ? 'Etiquetats' : 'Etiqueta treta de',
  );

  function byCriteris(accio) {
    const verb = accio === 'afegir' ? 'Etiquetar' : 'Treure l\'etiqueta a';
    if (!confirm(`${verb} els ${total} discos que coincideixen amb els filtres amb «${etiqueta.name_ca}»?`)) return;
    assignar({ accio, criteris: toCriteris(applied) }, accio === 'afegir' ? 'Etiquetats' : 'Etiqueta treta de');
  }

  if (!etiquetes.length) {
    return <div className="p-12 text-center text-secondary-foreground text-sm">Crea primer alguna etiqueta.</div>;
  }

  return (
    <div className="space-y-4">
      <div className="bg-card rounded-2xl border border-outline-variant p-4 space-y-3">
        <div className="text-xs font-medium text-secondary-foreground">Etiqueta a assignar</div>
        <div className="flex flex-wrap gap-2">
          {etiquetes.map(e => (
            <button
              key={e.id}
              onClick={() => setEtiquetaId(e.id)}
              className={`rounded-full px-3 py-1 text-xs font-semibold text-white transition ${e.id === etiquetaId ? 'ring-2 ring-offset-2 ring-on-surface' : 'opacity-60 hover:opacity-100'}`}
              style={{ backgroundColor: e.color || '#94a3b8' }}
            >
              {e.name_ca}
            </button>
          ))}
        </div>
      </div>

      <form
        onSubmit={ev => { ev.preventDefault(); setApplied(filters); }}
        className="bg-card rounded-2xl border border-outline-variant p-4 space-y-3"
      >
        <div className="text-xs font-medium text-secondary-foreground">Criteris</div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
          {FIELDS.map(([k, label]) => (
            <input
              key={k}
              value={filters[k]}
              onChange={e => setFilters(p => ({ ...p, [k]: e.target.value }))}
              placeholder={label}
              aria-label={label}
              type={/anio|precio/.test(k) ? 'number' : 'text'}
              className="border border-outline-variant rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
          ))}
          <select
            value={filters.con_stock}
            onChange={e => setFilters(p => ({ ...p, con_stock: e.target.value }))}
            aria-label="Stock"
            className="border border-outline-variant rounded-xl px-3 py-2 text-sm bg-card"
          >
            <option value="">Amb i sense estoc</option>
            <option value="true">Només amb estoc</option>
            <option value="false">Només sense estoc</option>
          </select>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button size="sm" type="submit"><MIcon name="search" size={14} /> Filtrar</Button>
          <button
            type="button"
            onClick={() => { setFilters(EMPTY_FILTERS); setApplied(EMPTY_FILTERS); }}
            className="text-sm text-secondary-foreground hover:text-on-surface-variant"
          >
            Netejar
          </button>
          <label className="flex items-center gap-2 text-sm text-secondary-foreground ml-auto">
            <input type="checkbox" checked={onlyMissing} onChange={e => setOnlyMissing(e.target.checked)} />
            Només els que encara no la tenen
          </label>
        </div>
      </form>

      <div className="flex flex-wrap items-center gap-2 sticky top-0 z-10 bg-surface py-2">
        <span className="text-sm text-secondary-foreground">
          {total} coincidències{total > PAGE ? ` (es mostren ${PAGE})` : ''} · {selected.size} seleccionats
        </span>
        <div className="flex flex-wrap gap-2 ml-auto">
          <Button size="sm" disabled={busy || !selected.size} onClick={() => byIds('afegir')}>
            <MIcon name="label" size={14} /> Etiquetar seleccionats
          </Button>
          <Button size="sm" variant="outline" disabled={busy || !selected.size} onClick={() => byIds('treure')}>
            Treure als seleccionats
          </Button>
          <Button size="sm" variant="outline" disabled={busy || !total} onClick={() => byCriteris('afegir')}>
            Etiquetar tots els {total}
          </Button>
          <Button size="sm" variant="outline" disabled={busy || !total} onClick={() => byCriteris('treure')}>
            Treure a tots els {total}
          </Button>
        </div>
      </div>
      {msg && <p role="status" className="text-sm text-green-700">{msg}</p>}

      <div className="bg-card rounded-2xl border border-outline-variant overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-secondary-foreground text-sm">Carregant...</div>
        ) : visible.length === 0 ? (
          <div className="p-12 text-center text-secondary-foreground text-sm">Cap disc amb aquests criteris.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-surface-container-high text-xs text-secondary-foreground border-b border-outline-variant">
              <tr>
                <th className="px-4 py-3 w-8">
                  <input type="checkbox" aria-label="Seleccionar tots" checked={selected.size === visible.length} onChange={selectAllVisible} />
                </th>
                <th className="px-2 py-3 text-left font-medium">Disc</th>
                <th className="px-2 py-3 text-left font-medium hidden md:table-cell">Segell · any</th>
                <th className="px-2 py-3 text-left font-medium">Etiquetes</th>
                <th className="px-2 py-3 w-10" />
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant">
              {visible.map(r => {
                const tagged = has(r);
                return (
                  <tr
                    key={r.id}
                    onClick={() => toggle(r.id)}
                    className={`cursor-pointer hover:bg-surface-container-high ${selected.has(r.id) ? 'bg-surface-container' : ''}`}
                  >
                    <td className="px-4 py-2">
                      <input type="checkbox" aria-label={`Seleccionar ${r.titulo}`} checked={selected.has(r.id)} onChange={() => toggle(r.id)} onClick={e => e.stopPropagation()} />
                    </td>
                    <td className="px-2 py-2">
                      <div className="font-medium text-on-surface">{r.titulo}</div>
                      <div className="text-xs text-secondary-foreground">{r.artista} · {r.formato}</div>
                    </td>
                    <td className="px-2 py-2 text-xs text-secondary-foreground hidden md:table-cell">
                      {[r.sello, r.anio].filter(Boolean).join(' · ') || '—'}
                    </td>
                    <td className="px-2 py-2">
                      <div className="flex flex-wrap gap-1">
                        {r.etiquetes.map(e => (
                          <span key={e.id} className="rounded-full px-2 py-0.5 text-[11px] font-semibold text-white" style={{ backgroundColor: e.color || '#94a3b8' }}>
                            {e.nom_ca}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-2 py-2">
                      <button
                        title={tagged ? 'Treure l\'etiqueta' : 'Afegir l\'etiqueta'}
                        disabled={busy}
                        onClick={ev => { ev.stopPropagation(); assignar({ accio: tagged ? 'treure' : 'afegir', release_ids: [r.id] }, tagged ? 'Treta' : 'Etiquetat'); }}
                        className={`p-1.5 rounded-lg ${tagged ? 'text-green-600' : 'text-secondary-foreground hover:text-on-surface'}`}
                      >
                        <MIcon name={tagged ? 'check_circle' : 'add_circle'} size={18} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
