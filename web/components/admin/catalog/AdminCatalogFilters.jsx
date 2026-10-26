'use client';

import { useEffect, useMemo, useState } from 'react';
import MIcon from '../../ui/m-icon';
import { Popover, PopoverTrigger, PopoverContent } from '../../ui/popover';
import { Checkbox } from '../../ui/checkbox';
import { cn } from '../../lib/utils';

export const EMPTY_ADV = {
  genero: [], estilo: [], pais: [], etiqueta: [], seccio: [],
  condicion: [], estado_disco: [], status: [],
  precio_min: '', precio_max: '',
  con_stock: '', stock_bajo: false, sin_imagen: '', sin_discogs: '', sin_seccio: '',
};

const MULTI_KEYS = ['genero', 'estilo', 'pais', 'etiqueta', 'seccio', 'condicion', 'estado_disco', 'status'];
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

function MultiFilter({ label, options, selected, onChange }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const visible = useMemo(() => {
    const ql = q.trim().toLowerCase();
    return ql ? options.filter(o => o.label.toLowerCase().includes(ql)) : options;
  }, [options, q]);

  function toggle(value) {
    onChange(selected.includes(value) ? selected.filter(v => v !== value) : [...selected, value]);
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            'flex items-center gap-1.5 px-3 py-1.5 border rounded-lg text-xs transition-colors',
            selected.length
              ? 'border-primary bg-primary/10 text-on-surface font-medium'
              : 'border-outline-variant bg-card text-on-surface-variant hover:bg-surface-container-high',
          )}
        >
          {label}{selected.length > 0 && <span className="tabular-nums">· {selected.length}</span>}
          <MIcon name="expand_more" size={12} />
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-60 normal-case font-normal">
        {options.length > 8 && (
          <div className="relative mb-2">
            <MIcon name="search" size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-secondary-foreground" />
            <input
              value={q}
              onChange={e => setQ(e.target.value)}
              placeholder="Cercar..."
              className="w-full pl-6 pr-2 py-1.5 text-xs border border-outline-variant rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
        )}
        <div className="max-h-56 overflow-y-auto space-y-0.5">
          {visible.length === 0 && <p className="text-xs text-secondary-foreground px-1 py-1">Cap resultat.</p>}
          {visible.map(o => (
            <label key={o.value} className="flex items-center gap-2 px-1 py-1 rounded hover:bg-surface-container-high cursor-pointer text-xs text-on-surface-variant">
              <Checkbox checked={selected.includes(o.value)} onCheckedChange={() => toggle(o.value)} />
              <span className="truncate">{o.label}</span>
            </label>
          ))}
        </div>
        {selected.length > 0 && (
          <button type="button" onClick={() => onChange([])}
            className="mt-2 text-xs text-secondary-foreground hover:text-on-surface">
            Netejar
          </button>
        )}
      </PopoverContent>
    </Popover>
  );
}

function TriState({ label, value, onChange, yes, no }) {
  return (
    <label className="flex items-center gap-1.5 text-xs text-on-surface-variant">
      {label}
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className={cn(
          'px-2 py-1.5 border rounded-lg text-xs bg-card focus:outline-none focus:ring-2 focus:ring-primary',
          value !== '' ? 'border-primary bg-primary/10 font-medium' : 'border-outline-variant',
        )}
      >
        <option value="">Tots</option>
        <option value="true">{yes}</option>
        <option value="false">{no}</option>
      </select>
    </label>
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
      value={draft} placeholder={placeholder}
      onChange={e => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={e => { if (e.key === 'Enter') commit(); }}
      className="w-20 px-2 py-1.5 border border-outline-variant rounded-lg text-xs bg-card focus:outline-none focus:ring-2 focus:ring-primary"
    />
  );
}

/**
 * Panell de filtres del catàleg d'admin (estil Discogs): selectors múltiples,
 * preu, interruptors d'estat i xips dels filtres actius.
 *
 * facets: resposta de GET /admin/releases/facets · gradings: llista d'estats de disc
 * adv / onChange: estat dels filtres (vegeu EMPTY_ADV) i el seu setter.
 */
export default function AdminCatalogFilters({ facets, gradings, adv, onChange }) {
  const [open, setOpen] = useState(false);
  const count = advCount(adv);
  const set = (key, value) => onChange({ ...adv, [key]: value });

  const plain = list => (list ?? []).map(v => ({ value: String(v), label: String(v) }));
  const named = list => (list ?? []).map(o => ({ value: o.slug, label: o.nom }));

  const multi = [
    ['genero', 'Gènere', plain(facets.genero)],
    ['estilo', 'Estil', plain(facets.estilo)],
    ['pais', 'País', plain(facets.pais)],
    ['etiqueta', 'Etiqueta', named(facets.etiqueta)],
    ['seccio', 'Secció', named(facets.seccio)],
    ['condicion', 'Condició', CONDICIONS],
    ['estado_disco', 'Estat disc', (gradings ?? []).map(g => ({ value: g, label: g }))],
    ['status', 'Estat', STATUSES],
  ];

  // Xips: un per valor seleccionat i un per cada interruptor actiu.
  const chips = [];
  const labelOf = (opts, v) => opts.find(o => o.value === v)?.label ?? v;
  for (const [key, label, opts] of multi) {
    adv[key].forEach(v => chips.push({
      id: `${key}:${v}`, text: `${label}: ${labelOf(opts, v)}`,
      remove: () => set(key, adv[key].filter(x => x !== v)),
    }));
  }
  if (adv.precio_min !== '') chips.push({ id: 'pmin', text: `Preu ≥ ${adv.precio_min} €`, remove: () => set('precio_min', '') });
  if (adv.precio_max !== '') chips.push({ id: 'pmax', text: `Preu ≤ ${adv.precio_max} €`, remove: () => set('precio_max', '') });
  const flagChip = (key, yes, no) => {
    if (adv[key] !== '') chips.push({ id: key, text: adv[key] === 'true' ? yes : no, remove: () => set(key, '') });
  };
  flagChip('con_stock', 'Amb stock', 'Sense stock');
  flagChip('sin_imagen', 'Sense caràtula', 'Amb caràtula');
  flagChip('sin_discogs', 'Sense vincular a Discogs', 'Vinculats a Discogs');
  flagChip('sin_seccio', 'Sense secció', 'Amb secció');
  if (adv.stock_bajo) chips.push({ id: 'stock_bajo', text: 'Stock baix', remove: () => set('stock_bajo', false) });

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => setOpen(o => !o)}
          aria-expanded={open}
          className={cn(
            'flex items-center gap-1.5 px-3 py-1.5 border rounded-lg text-sm transition-colors',
            count ? 'border-primary text-on-surface font-medium' : 'border-outline-variant text-on-surface-variant hover:bg-surface-container-high',
          )}
        >
          <MIcon name="tune" size={14} /> Filtres{count > 0 && <span className="tabular-nums">({count})</span>}
          <MIcon name={open ? 'expand_less' : 'expand_more'} size={14} />
        </button>
        {chips.map(c => (
          <span key={c.id} className="flex items-center gap-1 pl-2.5 pr-1 py-1 rounded-full bg-primary/10 text-xs text-on-surface">
            {c.text}
            <button type="button" onClick={c.remove} aria-label={`Treure ${c.text}`}
              className="p-0.5 rounded-full hover:bg-primary/20">
              <MIcon name="close" size={12} />
            </button>
          </span>
        ))}
        {count > 0 && (
          <button type="button" onClick={() => onChange(EMPTY_ADV)}
            className="text-xs text-secondary-foreground hover:text-on-surface underline underline-offset-2">
            Netejar filtres
          </button>
        )}
      </div>

      {open && (
        <div className="bg-card border border-outline-variant rounded-2xl p-4 space-y-3 shadow-sm">
          <div className="flex flex-wrap items-center gap-2">
            {multi.map(([key, label, opts]) => (
              <MultiFilter key={key} label={label} options={opts}
                selected={adv[key]} onChange={v => set(key, v)} />
            ))}
            <span className="flex items-center gap-1.5 text-xs text-on-surface-variant">
              Preu
              <PriceInput placeholder="mín" value={adv.precio_min} onCommit={v => set('precio_min', v)} />
              –
              <PriceInput placeholder="màx" value={adv.precio_max} onCommit={v => set('precio_max', v)} />
              €
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
            <TriState label="Stock" value={adv.con_stock} onChange={v => set('con_stock', v)} yes="Amb stock" no="Sense stock" />
            <TriState label="Caràtula" value={adv.sin_imagen} onChange={v => set('sin_imagen', v)} yes="Sense caràtula" no="Amb caràtula" />
            <TriState label="Discogs" value={adv.sin_discogs} onChange={v => set('sin_discogs', v)} yes="Sense vincular" no="Vinculats" />
            <TriState label="Secció" value={adv.sin_seccio} onChange={v => set('sin_seccio', v)} yes="Sense secció" no="Amb secció" />
            <label className="flex items-center gap-1.5 text-xs text-on-surface-variant cursor-pointer">
              <Checkbox checked={adv.stock_bajo} onCheckedChange={v => set('stock_bajo', v === true)} />
              Només stock baix
            </label>
          </div>
        </div>
      )}
    </div>
  );
}
