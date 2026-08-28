'use client';

import { Plus, Trash2 } from 'lucide-react';
import BackgroundFieldset from './BackgroundFieldset';

// Formulari de props del bloc "testimonials" — camps 1:1 amb
// api/app/blocks/registry.py::TestimonialsProps. Els ítems no tenen
// previsualització lletra a lletra (ver TestimonialsBlock.jsx); es veuen en
// desar, ja que el panell recarrega l'iframe després de guardar.
export default function TestimonialsPropsForm({ props, onChange, onFieldChange }) {
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
    onChange({ ...props, items: [...items, { quote: '', author: '' }] });
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
          placeholder="El que diuen de nosaltres"
          className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
        />
      </div>

      <div className="space-y-3">
        {items.map((item, i) => (
          <div key={i} className="border border-zinc-200 rounded-xl p-3 space-y-2 relative">
            <button
              type="button"
              onClick={() => removeItem(i)}
              className="absolute top-2 right-2 p-1 text-zinc-300 hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors"
            >
              <Trash2 size={13} />
            </button>
            <div>
              <label className="block text-xs font-medium text-zinc-600 mb-1">Cita</label>
              <textarea
                value={item.quote}
                onChange={(e) => updateItem(i, 'quote', e.target.value)}
                rows={2}
                placeholder="El millor lloc per trobar vinils del barri..."
                className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-600 mb-1">Autor/a</label>
              <input
                value={item.author}
                onChange={(e) => updateItem(i, 'author', e.target.value)}
                placeholder="Nom del client"
                className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
              />
            </div>
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={addItem}
        className="flex items-center gap-1.5 text-sm text-zinc-600 hover:text-zinc-900 border border-zinc-200 rounded-xl px-3 py-2 hover:bg-zinc-50 transition-colors"
      >
        <Plus size={14} /> Afegir testimoni
      </button>
      <BackgroundFieldset props={props} onChange={onChange} onFieldChange={onFieldChange} />
    </div>
  );
}
