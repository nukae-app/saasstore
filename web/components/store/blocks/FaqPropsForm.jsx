'use client';

import { Plus, Trash2 } from 'lucide-react';

// Formulari de props del bloc "faq" — camps 1:1 amb
// api/app/blocks/registry.py::FaqProps.
export default function FaqPropsForm({ props, onChange, onFieldChange }) {
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
    onChange({ ...props, items: [...items, { question: '', answer: '' }] });
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
          placeholder="Preguntes freqüents"
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
              <label className="block text-xs font-medium text-zinc-600 mb-1">Pregunta</label>
              <input
                value={item.question}
                onChange={(e) => updateItem(i, 'question', e.target.value)}
                placeholder="Feu enviaments fora de Barcelona?"
                className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-600 mb-1">Resposta</label>
              <textarea
                value={item.answer}
                onChange={(e) => updateItem(i, 'answer', e.target.value)}
                rows={3}
                placeholder="Sí, enviem a tota la península..."
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
        <Plus size={14} /> Afegir pregunta
      </button>
    </div>
  );
}
