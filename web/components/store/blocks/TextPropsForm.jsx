'use client';

import { Plus, Trash2 } from 'lucide-react';
import BackgroundFieldset from './BackgroundFieldset';

// Mateixes claus que api/app/blocks/registry.py::TEXT_LAYOUTS.
const LAYOUT_OPTIONS = [
  { value: 'centered', label: 'Centrat' },
  { value: 'full_width', label: 'Ample complet' },
  { value: 'two_columns_image', label: 'Dues columnes amb imatge' },
  { value: 'two_columns_video', label: 'Dues columnes amb vídeo' },
  { value: 'background_image', label: 'Imatge de fons completa' },
  { value: 'stats', label: 'Amb estadístiques' },
  { value: 'pull_quote', label: 'Cita destacada' },
  { value: 'checklist', label: 'Llista de punts' },
  { value: 'cta_banner', label: 'Botó gran centrat' },
  { value: 'editorial_dropcap', label: 'Editorial, amb lletra capital' },
];

// Formulari de props del bloc "text" — camps 1:1 amb
// api/app/blocks/registry.py::TextProps.
export default function TextPropsForm({ props, onChange, onFieldChange }) {
  const layout = props.layout || 'centered';
  const stats = props.stats || [];

  function set(field, value) {
    onChange({ ...props, [field]: value });
    onFieldChange?.(field, value);
  }

  function updateStat(index, field, value) {
    const next = stats.map((s, i) => (i === index ? { ...s, [field]: value } : s));
    onChange({ ...props, stats: next });
  }

  function addStat() {
    onChange({ ...props, stats: [...stats, { value: '', label: '' }] });
  }

  function removeStat(index) {
    onChange({ ...props, stats: stats.filter((_, i) => i !== index) });
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
        <label className="block text-xs font-medium text-zinc-600 mb-1">
          {layout === 'pull_quote' ? 'Atribució (opcional)' : 'Títol'}
        </label>
        <input
          value={props.heading || ''}
          onChange={(e) => set('heading', e.target.value)}
          placeholder={layout === 'pull_quote' ? 'Nom del client' : 'Un títol per a aquesta franja'}
          className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-zinc-600 mb-1">
          {layout === 'pull_quote' ? 'Cita' : layout === 'checklist' ? 'Punts (una línia per punt)' : 'Text'}
        </label>
        <textarea
          value={props.body || ''}
          onChange={(e) => set('body', e.target.value)}
          rows={5}
          placeholder={layout === 'checklist' ? 'Enviament gratuït a partir de 50€\nDevolucions fàcils\n30 dies de garantia' : "El contingut d'aquesta franja..."}
          className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
        />
      </div>

      {layout === 'stats' && (
        <div className="space-y-3 border-t border-zinc-100 pt-4">
          <p className="text-xs font-medium text-zinc-600">Estadístiques (recomanat: 3)</p>
          {stats.map((s, i) => (
            <div key={i} className="grid grid-cols-[1fr_2fr_auto] gap-2 items-center">
              <input
                value={s.value}
                onChange={(e) => updateStat(i, 'value', e.target.value)}
                placeholder="500+"
                className="border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
              />
              <input
                value={s.label}
                onChange={(e) => updateStat(i, 'label', e.target.value)}
                placeholder="Discos al catàleg"
                className="border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
              />
              <button type="button" onClick={() => removeStat(i)} className="p-2 text-zinc-300 hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={addStat}
            className="flex items-center gap-1.5 text-sm text-zinc-600 hover:text-zinc-900 border border-zinc-200 rounded-xl px-3 py-2 hover:bg-zinc-50 transition-colors"
          >
            <Plus size={14} /> Afegir xifra
          </button>
        </div>
      )}

      {layout === 'two_columns_video' && (
        <div>
          <label className="block text-xs font-medium text-zinc-600 mb-1">Enllaç del vídeo</label>
          <input
            value={props.video_url || ''}
            onChange={(e) => set('video_url', e.target.value)}
            placeholder="https://www.youtube.com/watch?v=..."
            className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
          />
          <p className="text-xs text-zinc-400 mt-1">Enllaç normal de YouTube o Vimeo.</p>
        </div>
      )}

      {layout !== 'pull_quote' && layout !== 'checklist' && (
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
      )}
      <p className="text-xs text-zinc-400">El botó només es mostra si omples text i enllaç.</p>

      {layout === 'two_columns_image' && (
        <p className="text-xs text-zinc-400">La imatge de "Fons" de sota s&apos;usa aquí com la il·lustració al costat del text (no com a fons de la secció).</p>
      )}
      {layout === 'background_image' && (
        <p className="text-xs text-zinc-400">La imatge de "Fons" de sota ocupa tota la secció; el color no s&apos;aplica en aquesta disposició.</p>
      )}
      <BackgroundFieldset props={props} onChange={onChange} onFieldChange={onFieldChange} />
    </div>
  );
}
