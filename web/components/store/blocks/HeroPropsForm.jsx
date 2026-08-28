'use client';

import BackgroundFieldset from './BackgroundFieldset';
import VideoPicker from './VideoPicker';

// Mateixes claus que api/app/blocks/registry.py::HERO_LAYOUTS.
const LAYOUT_OPTIONS = [
  { value: 'image_right', label: 'Imatge a la dreta' },
  { value: 'image_left', label: 'Imatge a l’esquerra' },
  { value: 'dual_featured', label: 'Dos productes destacats' },
  { value: 'mosaic', label: 'Mosaic de fotos' },
  { value: 'background_center', label: 'Banner de fons, centrat' },
  { value: 'background_left', label: 'Banner de fons, text a l’esquerra' },
  { value: 'background_video', label: 'Vídeo de fons' },
  { value: 'solid_color', label: 'Bloc de color sòlid' },
  { value: 'no_image', label: 'Sense imatge' },
  { value: 'logo_tagline', label: 'Logo gran + eslògan' },
];

const TEXT_ALIGN_OPTIONS = [
  { value: 'center', label: 'Centrat' },
  { value: 'left', label: 'Esquerra' },
  { value: 'right', label: 'Dreta' },
];

const USES_FEATURED_LABEL = new Set(['image_right', 'image_left', 'dual_featured']);
const USES_BACKGROUND_FIELDSET = new Set(['background_center', 'background_left', 'solid_color']);

// Formulari de props del bloc "hero" dins del Sheet d'edició de
// web/app/admin/disseny-web — camps 1:1 amb api/app/blocks/registry.py::HeroProps.
export default function HeroPropsForm({ props, onChange, onFieldChange }) {
  const layout = props.layout || 'image_right';

  function set(field, value) {
    onChange({ ...props, [field]: value });
    onFieldChange?.(field, value);
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-xs font-medium text-zinc-600 mb-1">Disposició</label>
        <select
          value={layout}
          onChange={(e) => set('layout', e.target.value)}
          className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
        >
          {LAYOUT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

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

      {USES_FEATURED_LABEL.has(layout) && (
        <div>
          <label className="block text-xs font-medium text-zinc-600 mb-1">Etiqueta de la targeta flotant</label>
          <input
            value={props.featured_label || ''}
            onChange={(e) => set('featured_label', e.target.value)}
            placeholder="Ara sona"
            className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
          />
          <p className="text-xs text-zinc-400 mt-1">Per defecte "Ara sona". Canvia-ho si el teu negoci no ven discos, p. ex. "Producte destacat".</p>
        </div>
      )}

      {layout === 'background_video' && (
        <>
          <div>
            <label className="block text-xs font-medium text-zinc-600 mb-1">Vídeo de fons</label>
            <VideoPicker
              value={props.background_video_url}
              onChange={(url) => set('background_video_url', url)}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-zinc-600 mb-1">Alineació del text</label>
            <select
              value={props.text_align || 'center'}
              onChange={(e) => set('text_align', e.target.value)}
              className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
            >
              {TEXT_ALIGN_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
        </>
      )}

      {layout === 'logo_tagline' && (
        <p className="text-xs text-zinc-400">Fa servir el logo de la botiga (Configuració → Botiga). Si no en tens, es mostra el nom de la botiga.</p>
      )}

      {USES_BACKGROUND_FIELDSET.has(layout) && (
        <BackgroundFieldset props={props} onChange={onChange} onFieldChange={onFieldChange} />
      )}
    </div>
  );
}
