'use client';

import { useEffect, useMemo, useState } from 'react';
import MIcon from '../../ui/m-icon';
import { Checkbox } from '../../ui/checkbox';
import { cn } from '../../lib/utils';

export const EMPTY_ADV = {
  artista: [], sello: [], formato: [], anio: [],
  genero: [], estilo: [], pais: [], etiqueta: [], seccio: [],
  condicion: [], estado_disco: [], status: [],
  precio_min: '', precio_max: '',
  con_stock: '', stock_bajo: false, sin_imagen: '', sin_discogs: '', sin_seccio: '',
};

const MULTI_KEYS = ['artista', 'sello', 'formato', 'anio', 'genero', 'estilo', 'pais', 'etiqueta', 'seccio', 'condicion', 'estado_disco', 'status'];
const SCALAR_KEYS = ['precio_min', 'precio_max', 'con_stock', 'sin_imagen', 'sin_discogs', 'sin_seccio'];

/** Afegeix a `params` (URLSearchParams) els filtres de GET /admin/releases per a l'estat `adv`. */
export function advToParams(adv, params) {
  for (const key of MULTI_KEYS) adv[key].forEach(v => params.append(key, v));
  for (const key of SCALAR_KEYS) {
    if (adv[key] !== '') params.set(key, adv[key]);
  }
  if (adv.stock_bajo) params.set('stock_bajo', 'true');
}

export function advCount(adv) {
  let n = MULTI_KEYS.reduce((acc, k) => acc + adv[k].length, 0);
  n += SCALAR_KEYS.filter(k => adv[k] !== '').length;
  return n + (adv.stock_bajo ? 1 : 0);
}

// Opcions fixes (el valor és el que entén el servidor).
const CONDICIONS = [{ value: 'nou', label: 'Nou' }, { value: 'segona_ma', label: 'Segona mà' }];
const STATUSES = [
  { value: 'disponible', label: 'Disponible' }, { value: 'reservado', label: 'Reservat' },
  { value: 'vendido', label: 'Venut' }, { value: 'retirado', label: 'Retirat' },
];

const MAX_VISIBLE = 150; // sense cercar, no pintem més opcions que aquestes

function multiSections(facets, gradings) {
  const plain = list => (list ?? []).map(v => ({ value: String(v), label: String(v) }));
  const named = list => (list ?? []).map(o => ({ value: o.slug, label: o.nom }));
  return [
    // Artista: no té llista (n'hi ha milers); s'hi escriu el nom i es filtra per coincidència.
    { key: 'artista', label: 'Artista', options: [], text: true, open: true },
    { key: 'formato', label: 'Format', options: plain(facets.formato), open: true },
    { key: 'genero', label: 'Gènere', options: plain(facets.genero), open: true },
    { key: 'anio', label: 'Any', options: plain([...(facets.anio ?? [])].reverse()) },
    { key: 'sello', label: 'Segell', options: plain(facets.sello) },
    { key: 'estilo', label: 'Estil', options: plain(facets.estilo) },
    { key: 'pais', label: 'País', options: plain(facets.pais) },
    { key: 'etiqueta', label: 'Etiqueta', options: named(facets.etiqueta) },
    { key: 'seccio', label: 'Secció', options: named(facets.seccio) },
    { key: 'condicion', label: 'Condició', options: CONDICIONS },
    { key: 'estado_disco', label: 'Estat del disc', options: (gradings ?? []).map(g => ({ value: g, label: g })) },
    { key: 'status', label: 'Estat de la còpia', options: STATUSES },
  ];
}

const FLAGS = [
  { key: 'con_stock', label: 'Stock', yes: 'Amb stock', no: 'Sense stock' },
  { key: 'sin_imagen', label: 'Caràtula', yes: 'Sense caràtula', no: 'Amb caràtula' },
  { key: 'sin_discogs', label: 'Discogs', yes: 'Sense vincular', no: 'Vinculats' },
  { key: 'sin_seccio', label: 'Secció', yes: 'Sense secció', no: 'Amb secció' },
];

/** Xips dels filtres actius, per mostrar-los sobre la taula. */
function buildChips(adv, onChange, facets, gradings) {
  const set = (key, value) => onChange({ ...adv, [key]: value });
  const chips = [];
  for (const sec of multiSections(facets, gradings)) {
    adv[sec.key].forEach(v => chips.push({
      id: `${sec.key}:${v}`,
      text: `${sec.label}: ${sec.options.find(o => o.value === v)?.label ?? v}`,
      remove: () => set(sec.key, adv[sec.key].filter(x => x !== v)),
    }));
  }
  if (adv.precio_min !== '') chips.push({ id: 'pmin', text: `Preu ≥ ${adv.precio_min} €`, remove: () => set('precio_min', '') });
  if (adv.precio_max !== '') chips.push({ id: 'pmax', text: `Preu ≤ ${adv.precio_max} €`, remove: () => set('precio_max', '') });
  for (const f of FLAGS) {
    if (adv[f.key] !== '') chips.push({ id: f.key, text: adv[f.key] === 'true' ? f.yes : f.no, remove: () => set(f.key, '') });
  }
  if (adv.stock_bajo) chips.push({ id: 'stock_bajo', text: 'Stock baix', remove: () => set('stock_bajo', false) });
  return chips;
}

export function ActiveFilterChips({ facets, gradings, adv, onChange }) {
  const chips = buildChips(adv, onChange, facets, gradings);
  if (chips.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      {chips.map(c => (
        <span key={c.id} className="flex items-center gap-1 pl-2.5 pr-1 py-1 rounded-full bg-primary/10 text-xs text-on-surface">
          {c.text}
          <button type="button" onClick={c.remove} aria-label={`Treure ${c.text}`}
            className="p-0.5 rounded-full hover:bg-primary/20">
            <MIcon name="close" size={12} />
          </button>
        </span>
      ))}
      <button type="button" onClick={() => onChange(EMPTY_ADV)}
        className="text-xs text-secondary-foreground hover:text-on-surface underline underline-offset-2">
        Netejar filtres
      </button>
    </div>
  );
}

function Section({ title, count = 0, defaultOpen = false, children }) {
  return (
    <details open={defaultOpen || count > 0} className="group border-b border-outline-variant last:border-b-0">
      <summary className="flex items-center justify-between gap-2 py-2.5 cursor-pointer select-none list-none text-sm font-medium text-on-surface">
        <span className="flex items-center gap-2">
          {title}
          {count > 0 && (
            <span className="px-1.5 rounded-full bg-primary text-primary-foreground text-[10px] leading-4 tabular-nums">{count}</span>
          )}
        </span>
        <MIcon name="expand_more" size={14} className="transition-transform group-open:rotate-180 text-secondary-foreground" />
      </summary>
      <div className="pb-3">{children}</div>
    </details>
  );
}

// Camp de text: Enter afegeix el valor com a filtre (es poden afegir diversos).
function TextAdd({ placeholder, selected, onChange }) {
  const [draft, setDraft] = useState('');
  const add = () => {
    const v = draft.trim();
    if (v && !selected.includes(v)) onChange([...selected, v]);
    setDraft('');
  };
  return (
    <div className="space-y-1.5">
      <input
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); add(); } }}
        onBlur={add}
        placeholder={placeholder}
        className="w-full px-2 py-1.5 text-xs border border-outline-variant rounded-lg bg-card focus:outline-none focus:ring-2 focus:ring-primary"
      />
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {selected.map(v => (
            <span key={v} className="flex items-center gap-1 pl-2 pr-1 py-0.5 rounded-full bg-primary/10 text-xs text-on-surface">
              {v}
              <button type="button" onClick={() => onChange(selected.filter(x => x !== v))} aria-label={`Treure ${v}`}
                className="p-0.5 rounded-full hover:bg-primary/20"><MIcon name="close" size={10} /></button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function CheckList({ options, selected, onChange }) {
  const [q, setQ] = useState('');
  const visible = useMemo(() => {
    const ql = q.trim().toLowerCase();
    const list = ql ? options.filter(o => o.label.toLowerCase().includes(ql)) : options;
    return ql ? list : list.slice(0, MAX_VISIBLE);
  }, [options, q]);

  const toggle = value =>
    onChange(selected.includes(value) ? selected.filter(v => v !== value) : [...selected, value]);

  if (options.length === 0) return <p className="text-xs text-secondary-foreground">Sense valors.</p>;
  return (
    <div className="space-y-1.5">
      {options.length > 8 && (
        <div className="relative">
          <MIcon name="search" size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-secondary-foreground" />
          <input
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="Cercar..."
            className="w-full pl-6 pr-2 py-1.5 text-xs border border-outline-variant rounded-lg bg-card focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
      )}
      <div className="max-h-48 overflow-y-auto space-y-0.5 pr-1">
        {visible.length === 0 && <p className="text-xs text-secondary-foreground px-1 py-1">Cap resultat.</p>}
        {visible.map(o => (
          <label key={o.value} className="flex items-center gap-2 px-1 py-1 rounded hover:bg-surface-container-high cursor-pointer text-xs text-on-surface-variant">
            <Checkbox checked={selected.includes(o.value)} onCheckedChange={() => toggle(o.value)} />
            <span className="truncate">{o.label}</span>
          </label>
        ))}
        {!q.trim() && options.length > MAX_VISIBLE && (
          <p className="text-[11px] text-secondary-foreground px-1 pt-1">Mostrant {MAX_VISIBLE} de {options.length}: cerca per veure la resta.</p>
        )}
      </div>
    </div>
  );
}

// El preu es confirma en sortir del camp o amb Enter, no a cada tecla.
function PriceInput({ placeholder, value, onCommit }) {
  const [draft, setDraft] = useState(value);
  useEffect(() => { setDraft(value); }, [value]);
  const commit = () => { if (draft !== value) onCommit(draft); };
  return (
    <input
      type="number" min="0" step="0.01" inputMode="decimal"
      value={draft} placeholder={placeholder} aria-label={placeholder}
      onChange={e => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={e => { if (e.key === 'Enter') commit(); }}
      className="w-full min-w-0 px-2 py-1.5 border border-outline-variant rounded-lg text-xs bg-card focus:outline-none focus:ring-2 focus:ring-primary"
    />
  );
}

/**
 * Barra lateral fixa de filtres del catàleg d'admin (estil Discogs): seccions
 * plegables amb llistes de caselles, preu i interruptors d'estat. A pantalles
 * petites es plega darrere d'un botó.
 *
 * facets: resposta de GET /admin/releases/facets · gradings: llista d'estats de disc
 * adv / onChange: estat dels filtres (vegeu EMPTY_ADV) i el seu setter.
 */
export default function AdminCatalogFilters({ facets, gradings, adv, onChange }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const count = advCount(adv);
  const set = (key, value) => onChange({ ...adv, [key]: value });
  const flagCount = FLAGS.filter(f => adv[f.key] !== '').length + (adv.stock_bajo ? 1 : 0);
  const priceCount = (adv.precio_min !== '' ? 1 : 0) + (adv.precio_max !== '' ? 1 : 0);

  return (
    <aside className="lg:w-64 lg:shrink-0 lg:sticky lg:top-0 lg:self-start">
      <button
        type="button"
        onClick={() => setMobileOpen(o => !o)}
        aria-expanded={mobileOpen}
        className="lg:hidden w-full flex items-center justify-between px-3 py-2 border border-outline-variant rounded-xl bg-card text-sm text-on-surface"
      >
        <span className="flex items-center gap-2"><MIcon name="tune" size={14} /> Filtres{count > 0 && ` (${count})`}</span>
        <MIcon name={mobileOpen ? 'expand_less' : 'expand_more'} size={14} />
      </button>

      <div className={cn(
        'bg-card border border-outline-variant rounded-2xl px-4 shadow-sm mt-2 lg:mt-0',
        'lg:block lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto',
        mobileOpen ? 'block' : 'hidden',
      )}>
        <div className="flex items-center justify-between py-3 border-b border-outline-variant">
          <span className="flex items-center gap-2 text-sm font-semibold text-on-surface">
            <MIcon name="tune" size={14} /> Filtres
          </span>
          {count > 0 && (
            <button type="button" onClick={() => onChange(EMPTY_ADV)}
              className="text-xs text-secondary-foreground hover:text-on-surface underline underline-offset-2">
              Netejar ({count})
            </button>
          )}
        </div>

        <Section title="Estat" count={flagCount} defaultOpen>
          <div className="space-y-2">
            {FLAGS.map(f => (
              <label key={f.key} className="flex items-center justify-between gap-2 text-xs text-on-surface-variant">
                {f.label}
                <select
                  value={adv[f.key]}
                  onChange={e => set(f.key, e.target.value)}
                  className={cn(
                    'w-32 px-2 py-1.5 border rounded-lg text-xs bg-card focus:outline-none focus:ring-2 focus:ring-primary',
                    adv[f.key] !== '' ? 'border-primary bg-primary/10 font-medium' : 'border-outline-variant',
                  )}
                >
                  <option value="">Tots</option>
                  <option value="true">{f.yes}</option>
                  <option value="false">{f.no}</option>
                </select>
              </label>
            ))}
            <label className="flex items-center gap-2 text-xs text-on-surface-variant cursor-pointer">
              <Checkbox checked={adv.stock_bajo} onCheckedChange={v => set('stock_bajo', v === true)} />
              Només stock baix
            </label>
          </div>
        </Section>

        <Section title="Preu" count={priceCount} defaultOpen>
          <div className="flex items-center gap-1.5 text-xs text-on-surface-variant">
            <PriceInput placeholder="mín" value={adv.precio_min} onCommit={v => set('precio_min', v)} />
            –
            <PriceInput placeholder="màx" value={adv.precio_max} onCommit={v => set('precio_max', v)} />
            €
          </div>
        </Section>

        {multiSections(facets, gradings).map(sec => (
          <Section key={sec.key} title={sec.label} count={adv[sec.key].length} defaultOpen={!!sec.open}>
            {sec.text
              ? <TextAdd placeholder="Escriu i prem Enter" selected={adv[sec.key]} onChange={v => set(sec.key, v)} />
              : <CheckList options={sec.options} selected={adv[sec.key]} onChange={v => set(sec.key, v)} />}
          </Section>
        ))}
      </div>
    </aside>
  );
}
