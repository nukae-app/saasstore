'use client';

// Formulari de props del bloc "hero" dins del Sheet d'edició de
// web/app/admin/pagina-inici — camps 1:1 amb api/app/blocks/registry.py::HeroProps.
export default function HeroPropsForm({ props, onChange }) {
  function set(field, value) {
    onChange({ ...props, [field]: value });
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-xs font-medium text-zinc-600 mb-1">Eyebrow (text petit a sobre)</label>
        <input
          value={props.eyebrow || ''}
          onChange={(e) => set('eyebrow', e.target.value)}
          placeholder="Poblenou · Barcelona"
          className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-zinc-600 mb-1">Títol *</label>
        <input
          value={props.title || ''}
          onChange={(e) => set('title', e.target.value)}
          placeholder="Discos nous i de segona mà."
          className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-zinc-600 mb-1">Subtítol</label>
        <textarea
          value={props.subtitle || ''}
          onChange={(e) => set('subtitle', e.target.value)}
          rows={3}
          placeholder="Selecció cuidada de vinil, CD i cassette."
          className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-zinc-600 mb-1">Text del botó</label>
          <input
            value={props.cta_label || ''}
            onChange={(e) => set('cta_label', e.target.value)}
            placeholder="Explorar"
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
    </div>
  );
}
