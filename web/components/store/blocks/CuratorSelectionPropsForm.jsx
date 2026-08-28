'use client';

import { useEffect, useState } from 'react';
import { authFetch } from '../../../app/lib/auth';

// Formulari de props del bloc "curator_selection" — camp 1:1 amb
// api/app/blocks/registry.py::CuratorSelectionProps. Mateix patró que
// CarouselPropsForm: select amb les etiquetes reals del tenant, amb
// fallback a text lliure si la crida falla.
export default function CuratorSelectionPropsForm({ props, onChange, onFieldChange }) {
  const [etiquetes, setEtiquetes] = useState(null);

  useEffect(() => {
    let active = true;
    authFetch('/admin/etiquetes')
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data) => { if (active) setEtiquetes(data); })
      .catch(() => { if (active) setEtiquetes([]); });
    return () => { active = false; };
  }, []);

  function set(value) {
    onChange({ ...props, etiqueta_slug: value });
    onFieldChange?.('etiqueta_slug', value);
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-xs font-medium text-zinc-600 mb-1">Etiqueta que alimenta la selecció</label>
        {etiquetes === null ? (
          <p className="text-xs text-zinc-400">Carregant etiquetes…</p>
        ) : etiquetes.length > 0 ? (
          <select
            value={props.etiqueta_slug || ''}
            onChange={(e) => set(e.target.value)}
            className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300 bg-white"
          >
            {etiquetes.map((et) => (
              <option key={et.id} value={et.slug}>{et.name_ca} ({et.slug})</option>
            ))}
          </select>
        ) : (
          <input
            value={props.etiqueta_slug || ''}
            onChange={(e) => set(e.target.value)}
            placeholder="recomanat"
            className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
          />
        )}
        <p className="text-xs text-zinc-400 mt-1">Només es mostraran discos que tinguin aquesta etiqueta assignada (sense comptar el que ja surt a la capçalera).</p>
      </div>
    </div>
  );
}
