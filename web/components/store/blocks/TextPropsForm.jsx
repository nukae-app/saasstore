'use client';

import BackgroundFieldset from './BackgroundFieldset';

// Formulari de props del bloc "text" — camps 1:1 amb
// api/app/blocks/registry.py::TextProps.
export default function TextPropsForm({ props, onChange, onFieldChange }) {
  function set(field, value) {
    onChange({ ...props, [field]: value });
    onFieldChange?.(field, value);
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-xs font-medium text-zinc-600 mb-1">Títol</label>
        <input
          value={props.heading || ''}
          onChange={(e) => set('heading', e.target.value)}
          placeholder="Un títol per a aquesta franja"
          className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-zinc-600 mb-1">Text</label>
        <textarea
          value={props.body || ''}
          onChange={(e) => set('body', e.target.value)}
          rows={5}
          placeholder="El contingut d'aquesta franja..."
          className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-zinc-600 mb-1">Text del botó</label>
          <input
            value={props.cta_label || ''}
            onChange={(e) => set('cta_label', e.target.value)}
            placeholder="Descobreix més"
            className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-zinc-600 mb-1">Enllaç del botó</label>
          <input
            value={props.cta_href || ''}
            onChange={(e) => set('cta_href', e.target.value)}
            placeholder="/cataleg"
            className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
          />
        </div>
      </div>
      <p className="text-xs text-zinc-400">El botó només es mostra si omples text i enllaç.</p>
      <BackgroundFieldset props={props} onChange={onChange} onFieldChange={onFieldChange} />
    </div>
  );
}
