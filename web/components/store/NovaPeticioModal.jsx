'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { X, Check, Loader2 } from 'lucide-react';
import { authFetch } from './AuthProvider';

export default function NovaPeticioModal({ onClose, onSaved, initialArtista = '', initialTitulo = '' }) {
  const t = useTranslations('peticions');
  const [artista, setArtista] = useState(initialArtista);
  const [titulo, setTitulo] = useState(initialTitulo);
  const [notas, setNotas] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const res = await authFetch('/me/peticiones', {
        method: 'POST',
        body: JSON.stringify({ artista_lliure: artista, titulo_lliure: titulo, notas_cliente: notas || null }),
      });
      if (res.ok) {
        onSaved();
      } else {
        const d = await res.json().catch(() => ({}));
        setError(d.detail || t('couldNotSendRequest'));
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-xl max-w-md w-full p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-serif italic text-xl">{t('cantFindItIWantIt')}</h2>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600"><X size={18} /></button>
        </div>
        <p className="text-sm text-zinc-500 mb-4">
          {t('tellUsWhatYouAreLookingFor')}
        </p>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-zinc-600 mb-1">{t('artist')} *</label>
            <input value={artista} onChange={e => setArtista(e.target.value)} required
              className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <div>
            <label className="block text-xs font-medium text-zinc-600 mb-1">{t('titleField')} *</label>
            <input value={titulo} onChange={e => setTitulo(e.target.value)} required
              className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <div>
            <label className="block text-xs font-medium text-zinc-600 mb-1">{t('notesOptional')}</label>
            <textarea value={notas} onChange={e => setNotas(e.target.value)} rows={2}
              placeholder={t('formatEditionPlaceholder')}
              className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex gap-2 pt-1">
            <button type="submit" disabled={saving}
              className="flex items-center gap-1.5 bg-primary hover:bg-zinc-800 text-white px-4 py-2 rounded-full text-sm font-medium transition-colors disabled:opacity-60">
              {saving ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
              {saving ? t('sendingEllipsis') : t('sendRequest')}
            </button>
            <button type="button" onClick={onClose}
              className="flex items-center gap-1.5 border border-zinc-200 text-zinc-600 px-4 py-2 rounded-lg text-sm hover:bg-zinc-50 transition-colors">
              {t('cancel')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
