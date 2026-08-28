'use client';

import { Plus, Trash2 } from 'lucide-react';
import { FEATURE_GRID_ICON_MAP } from './FeatureGridBlock';

// Mateixes claus que api/app/blocks/registry.py::FEATURE_GRID_ICONS, amb
// l'etiqueta en català per al selector.
const ICON_OPTIONS = [
  { value: 'music', label: 'Música' },
  { value: 'disc', label: 'Disc' },
  { value: 'truck', label: 'Enviament' },
  { value: 'gift', label: 'Regal' },
  { value: 'tag', label: 'Etiqueta' },
  { value: 'percent', label: 'Descompte' },
  { value: 'map-pin', label: 'Ubicació' },
  { value: 'phone', label: 'Telèfon' },
  { value: 'mail', label: 'Correu' },
  { value: 'heart', label: 'Preferit' },
  { value: 'star', label: 'Destacat' },
  { value: 'sparkles', label: 'Novetat' },
];

// Formulari de props del bloc "feature_grid" — camps 1:1 amb
// api/app/blocks/registry.py::FeatureGridProps.
export default function FeatureGridPropsForm({ props, onChange, onFieldChange }) {
  const items = props.items || [];

  function setHeading(value) {
    onChange({ ...props, heading: value });
    onFieldChange?.('heading', value);
  }

  function updateItem(index, field, value) {
    const next = items.map((it, i) => (i === index ? { ...it, [field]: value } : it));
    onChange({ ...props, items: next });
  }

  function addItem() {
    onChange({ ...props, items: [...items, { icon: 'music', label: '', href: '' }] });
  }

  function removeItem(index) {
    onChange({ ...props, items: items.filter((_, i) => i !== index) });
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-xs font-medium text-zinc-600 mb-1">Títol</label>
        <input
          value={props.heading || ''}
          onChange={(e) => setHeading(e.target.value)}
          placeholder="Per què comprar-nos"
          className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
        />
      </div>

      <div className="space-y-3">
        {items.map((item, i) => {
          const Icon = FEATURE_GRID_ICON_MAP[item.icon] || FEATURE_GRID_ICON_MAP.music;
          return (
            <div key={i} className="border border-zinc-200 rounded-xl p-3 space-y-2 relative">
              <button
                type="button"
                onClick={() => removeItem(i)}
                className="absolute top-2 right-2 p-1 text-zinc-300 hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors"
              >
                <Trash2 size={13} />
              </button>
              <div className="flex items-center gap-2">
                <div className="w-9 h-9 rounded-lg border border-zinc-200 flex items-center justify-center shrink-0 text-zinc-600">
                  <Icon size={16} />
                </div>
                <select
                  value={item.icon}
                  onChange={(e) => updateItem(i, 'icon', e.target.value)}
                  className="flex-1 border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
                >
                  {ICON_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-zinc-600 mb-1">Text</label>
                <input
                  value={item.label}
                  onChange={(e) => updateItem(i, 'label', e.target.value)}
                  placeholder="Enviament en 24-48h"
                  className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-zinc-600 mb-1">Enllaç (opcional)</label>
                <input
                  value={item.href || ''}
                  onChange={(e) => updateItem(i, 'href', e.target.value)}
                  placeholder="/enviaments"
                  className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
                />
              </div>
            </div>
          );
        })}
      </div>

      <button
        type="button"
        onClick={addItem}
        className="flex items-center gap-1.5 text-sm text-zinc-600 hover:text-zinc-900 border border-zinc-200 rounded-xl px-3 py-2 hover:bg-zinc-50 transition-colors"
      >
        <Plus size={14} /> Afegir element
      </button>
    </div>
  );
}
