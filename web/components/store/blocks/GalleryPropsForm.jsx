'use client';

import { useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { authFetch } from '../../../app/lib/auth';

// Formulari de props del bloc "gallery" — camps 1:1 amb
// api/app/blocks/registry.py::GalleryProps. Cada ítem puja la seva pròpia
// imatge amb el mateix endpoint genèric que BackgroundFieldset.jsx.
export default function GalleryPropsForm({ props, onChange, onFieldChange }) {
  const items = props.items || [];
  const [uploadingIndex, setUploadingIndex] = useState(null);
  const [error, setError] = useState('');

  function setHeading(value) {
    onChange({ ...props, heading: value });
    onFieldChange?.('heading', value);
  }

  function updateItem(index, field, value) {
    const next = items.map((it, i) => (i === index ? { ...it, [field]: value } : it));
    onChange({ ...props, items: next });
  }

  function addItem() {
    onChange({ ...props, items: [...items, { image_url: '', caption: '', href: '' }] });
  }

  function removeItem(index) {
    onChange({ ...props, items: items.filter((_, i) => i !== index) });
  }

  async function uploadImage(index, e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingIndex(index);
    setError('');
    try {
      const fd = new FormData();
      fd.append('file', file);
      const r = await authFetch('/admin/home-blocks/upload-background', { method: 'POST', body: fd });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        setError(body.detail || "No s'ha pogut pujar la imatge.");
        return;
      }
      const { url } = await r.json();
      updateItem(index, 'image_url', url);
    } finally {
      setUploadingIndex(null);
      e.target.value = '';
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-xs font-medium text-zinc-600 mb-1">Títol</label>
        <input
          value={props.heading || ''}
          onChange={(e) => setHeading(e.target.value)}
          placeholder="Un títol per a la galeria"
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
            <div className="flex items-center gap-3">
              {item.image_url && (
                <img src={item.image_url} alt="" className="w-14 h-14 rounded-lg border border-zinc-200 object-cover shrink-0" />
              )}
              <label className="text-xs font-medium text-zinc-700 border border-zinc-200 rounded-xl px-3 py-2 cursor-pointer hover:bg-zinc-50 transition-colors">
                {uploadingIndex === i ? 'Pujant…' : item.image_url ? 'Canviar imatge' : 'Pujar imatge'}
                <input type="file" accept=".png,.jpg,.jpeg,.webp" className="hidden" disabled={uploadingIndex === i} onChange={(e) => uploadImage(i, e)} />
              </label>
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-600 mb-1">Peu de foto (opcional)</label>
              <input
                value={item.caption || ''}
                onChange={(e) => updateItem(i, 'caption', e.target.value)}
                placeholder="Descripció curta"
                className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-600 mb-1">Enllaç (opcional)</label>
              <input
                value={item.href || ''}
                onChange={(e) => updateItem(i, 'href', e.target.value)}
                placeholder="/cataleg?genre=..."
                className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
              />
            </div>
          </div>
        ))}
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}

      <button
        type="button"
        onClick={addItem}
        className="flex items-center gap-1.5 text-sm text-zinc-600 hover:text-zinc-900 border border-zinc-200 rounded-xl px-3 py-2 hover:bg-zinc-50 transition-colors"
      >
        <Plus size={14} /> Afegir imatge
      </button>
    </div>
  );
}
