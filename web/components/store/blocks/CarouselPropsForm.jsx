'use client';

import { useEffect, useState } from 'react';
import { authFetch } from '../../../app/lib/auth';

// Formulari de props del bloc "carousel" — camps 1:1 amb
// api/app/blocks/registry.py::CarouselProps. `etiqueta_slug` es tria d'un
// select amb les etiquetes reals del tenant (GET /admin/etiquetes) perquè un
// slug inexistent produiria un carrusel sempre buit; si la crida falla es
// cau a un input de text lliure per no bloquejar l'edició.
export default function CarouselPropsForm({ props, onChange }) {
  const [etiquetes, setEtiquetes] = useState(null);

  useEffect(() => {
    let active = true;
    authFetch('/admin/etiquetes')
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data) => { if (active) setEtiquetes(data); })
      .catch(() => { if (active) setEtiquetes([]); });
    return () => { active = false; };
  }, []);

  function set(field, value) {
    onChange({ ...props, [field]: value });
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-xs font-medium text-zinc-600 mb-1">Títol</label>
        <input
          value={props.heading || ''}
          onChange={(e) => set('heading', e.target.value)}
          placeholder="Novetats"
          className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-zinc-600 mb-1">Subtítol</label>
        <input
          value={props.subtitle || ''}
          onChange={(e) => set('subtitle', e.target.value)}
          placeholder="Les últimes incorporacions al nostre catàleg."
          className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-zinc-600 mb-1">Text del enllaç</label>
        <input
          value={props.cta_label || ''}
          onChange={(e) => set('cta_label', e.target.value)}
          placeholder="Veure tot el catàleg"
          className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-zinc-600 mb-1">Etiqueta que alimenta el carrusel</label>
        {etiquetes === null ? (
          <p className="text-xs text-zinc-400">Carregant etiquetes…</p>
        ) : etiquetes.length > 0 ? (
          <select
            value={props.etiqueta_slug || ''}
            onChange={(e) => set('etiqueta_slug', e.target.value)}
            className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300 bg-white"
          >
            {etiquetes.map((et) => (
              <option key={et.id} value={et.slug}>{et.name_ca} ({et.slug})</option>
            ))}
          </select>
        ) : (
          <input
            value={props.etiqueta_slug || ''}
            onChange={(e) => set('etiqueta_slug', e.target.value)}
            placeholder="novetat"
            className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
          />
        )}
        <p className="text-xs text-zinc-400 mt-1">Només es mostraran discos que tinguin aquesta etiqueta assignada.</p>
      </div>
    </div>
  );
}
