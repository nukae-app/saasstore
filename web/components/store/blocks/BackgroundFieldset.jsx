'use client';

import { useState } from 'react';
import { Trash2 } from 'lucide-react';
import { authFetch } from '../../../app/lib/auth';

// Camps de fons (color + imatge) compartits entre hero/text/testimonials —
// ver api/app/blocks/registry.py::BackgroundProps. Es fa servir dins de
// cada PropsForm passant-li tot el `props` del bloc; només llegeix/escriu
// `background_color`/`background_image_url`, la resta de camps els deixa
// intactes en fer spread.
export default function BackgroundFieldset({ props, onChange, onFieldChange }) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');

  function set(field, value) {
    onChange({ ...props, [field]: value });
    onFieldChange?.(field, value);
  }

  async function uploadImage(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
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
      set('background_image_url', url);
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  }

  return (
    <div className="space-y-3 border-t border-zinc-100 pt-4">
      <p className="text-xs font-medium text-zinc-600">Fons</p>

      <div className="flex items-center gap-2">
        <input
          type="color"
          value={props.background_color || '#ffffff'}
          onChange={(e) => set('background_color', e.target.value)}
          className="w-9 h-9 rounded border border-zinc-300 shrink-0 cursor-pointer"
        />
        <input
          value={props.background_color || ''}
          onChange={(e) => set('background_color', e.target.value || null)}
          placeholder="Sense color propi"
          className="flex-1 border border-zinc-200 rounded-xl px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-zinc-300"
        />
        {props.background_color && (
          <button type="button" onClick={() => set('background_color', null)} className="p-2 text-zinc-300 hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors shrink-0">
            <Trash2 size={14} />
          </button>
        )}
      </div>

      <div className="flex items-center gap-3">
        {props.background_image_url && (
          <img src={props.background_image_url} alt="" className="w-14 h-14 rounded-lg border border-zinc-200 object-cover shrink-0" />
        )}
        <label className="text-xs font-medium text-zinc-700 border border-zinc-200 rounded-xl px-3 py-2 cursor-pointer hover:bg-zinc-50 transition-colors">
          {uploading ? 'Pujant…' : props.background_image_url ? 'Canviar imatge' : 'Pujar imatge'}
          <input type="file" accept=".png,.jpg,.jpeg,.webp" className="hidden" disabled={uploading} onChange={uploadImage} />
        </label>
        {props.background_image_url && (
          <button type="button" onClick={() => set('background_image_url', null)} className="text-xs text-zinc-400 hover:text-red-500 transition-colors">
            Treure
          </button>
        )}
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <p className="text-xs text-zinc-400">La imatge, si n&apos;hi ha, substitueix el color.</p>
    </div>
  );
}
