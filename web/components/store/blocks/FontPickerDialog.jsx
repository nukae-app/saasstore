'use client';

import { useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import { authFetch } from '../../../app/lib/auth';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../../ui/dialog';

// Cercador de tipografies de Fontsource (ver api/app/services/fontsource.py)
// — en triar-ne una, el servidor la descarrega de veritat i queda
// autoallotjada; aquí només es cerca i es mostra una previsualització en
// viu carregant l'CSS de Fontsource temporalment (mai els fitxers reals,
// només mentre es navega el cercador).
export default function FontPickerDialog({ open, onOpenChange, role, onSelected }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectingId, setSelectingId] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    const handle = setTimeout(async () => {
      try {
        const r = await authFetch(`/admin/configuracio/fonts/cerca?q=${encodeURIComponent(query)}`);
        setResults(r.ok ? await r.json() : []);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => clearTimeout(handle);
  }, [open, query]);

  async function select(font) {
    setSelectingId(font.id);
    setError('');
    try {
      const r = await authFetch(`/admin/configuracio/fonts/${role}`, {
        method: 'POST',
        body: JSON.stringify({ font_id: font.id }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        setError(body.detail || "No s'ha pogut descarregar la tipografia.");
        return;
      }
      const config = await r.json();
      onSelected(config);
      onOpenChange(false);
      setQuery('');
    } finally {
      setSelectingId(null);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Cercar tipografia</DialogTitle>
          <DialogDescription>
            Catàleg de Fontsource (fonts gratuïtes i de codi obert). En triar-ne una es descarrega i queda allotjada al teu propi servidor.
          </DialogDescription>
        </DialogHeader>

        <div className="relative">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Playfair Display, Inter, Fraunces…"
            className="w-full border border-zinc-200 rounded-xl pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
          />
        </div>

        {error && <p className="text-xs text-red-600">{error}</p>}

        <div className="max-h-80 overflow-y-auto -mx-1 px-1 space-y-1">
          {loading && <p className="text-xs text-zinc-400 py-4 text-center">Cercant…</p>}
          {!loading && results.length === 0 && (
            <p className="text-xs text-zinc-400 py-4 text-center">
              {query ? 'Cap tipografia trobada.' : 'Escriu per cercar entre més de 1.500 tipografies.'}
            </p>
          )}
          {results.map((font) => (
            <FontRow key={font.id} font={font} onSelect={select} selecting={selectingId === font.id} disabled={!!selectingId} />
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function FontRow({ font, onSelect, selecting, disabled }) {
  return (
    <>
      <link rel="stylesheet" href={`https://cdn.jsdelivr.net/fontsource/css/${font.id}@latest/index.css`} />
      <button
        type="button"
        onClick={() => onSelect(font)}
        disabled={disabled}
        className="w-full flex items-center justify-between gap-3 p-3 rounded-xl border border-zinc-200 hover:border-zinc-900 text-left transition-colors disabled:opacity-50"
      >
        <div className="min-w-0">
          <p className="text-lg truncate" style={{ fontFamily: `'${font.family}', system-ui` }}>{font.family}</p>
          <p className="text-[10px] text-zinc-400 uppercase tracking-wide">{font.category}</p>
        </div>
        <span className="text-xs text-zinc-400 shrink-0">{selecting ? 'Descarregant…' : 'Triar'}</span>
      </button>
    </>
  );
}
