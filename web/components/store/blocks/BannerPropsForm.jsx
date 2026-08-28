'use client';

import BackgroundFieldset from './BackgroundFieldset';

// Formulari de props del bloc "banner" — camps 1:1 amb
// api/app/blocks/registry.py::BannerProps.
export default function BannerPropsForm({ props, onChange, onFieldChange }) {
  function set(field, value) {
    onChange({ ...props, [field]: value });
    onFieldChange?.(field, value);
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-xs font-medium text-zinc-600 mb-1">Text de l&apos;avís</label>
        <input
          value={props.text || ''}
          onChange={(e) => set('text', e.target.value)}
          placeholder="Tanquem per vacances del 10 al 20 d'agost."
          className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-zinc-600 mb-1">Text de l&apos;enllaç</label>
          <input
            value={props.cta_label || ''}
            onChange={(e) => set('cta_label', e.target.value)}
            placeholder="Més informació"
            className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-zinc-600 mb-1">Enllaç</label>
          <input
            value={props.cta_href || ''}
            onChange={(e) => set('cta_href', e.target.value)}
            placeholder="/agenda"
            className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
          />
        </div>
      </div>
      <p className="text-xs text-zinc-400">L&apos;enllaç només es mostra si omples text i URL.</p>
      <BackgroundFieldset props={props} onChange={onChange} onFieldChange={onFieldChange} />
    </div>
  );
}
