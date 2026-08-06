'use client';

import { useSearchParams } from 'next/navigation';
import { useRouter } from '../../../i18n/navigation';
import { useTranslations } from 'next-intl';
import { useEffect, useState, useTransition } from 'react';
import { X } from 'lucide-react';
import { api } from '../../lib/api';

const FORMATS = ['LP', '12"', '10"', '7"', 'CD', 'Cassette', 'EP'];

export default function CatalogFilters({ className = '' }) {
  const t = useTranslations('cataleg');
  const router = useRouter();
  const searchParams = useSearchParams();
  const [, startTransition] = useTransition();
  const [etiquetes, setEtiquetes] = useState([]);

  useEffect(() => {
    api('/catalog/etiquetes').then(setEtiquetes).catch(() => {});
  }, []);

  function getParam(key) {
    return searchParams.get(key) || '';
  }

  function setParam(key, value) {
    const params = new URLSearchParams(searchParams.toString());
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    params.delete('page');
    startTransition(() => router.push(`/cataleg?${params.toString()}`));
  }

  function clearAll() {
    startTransition(() => router.push('/cataleg'));
  }

  const hasFilters = ['q', 'format', 'genre', 'etiqueta', 'min', 'max'].some(k => searchParams.has(k));

  return (
    <div className={`space-y-6 text-sm ${className}`}>
      {hasFilters && (
        <button
          onClick={clearAll}
          className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-700 transition-colors"
        >
          <X size={12} /> {t('clearFilters')}
        </button>
      )}

      {/* Search */}
      <div>
        <p className="font-medium text-zinc-700 mb-2">{t('search')}</p>
        <input
          type="text"
          placeholder={t('searchPlaceholder')}
          defaultValue={getParam('q')}
          onKeyDown={e => { if (e.key === 'Enter') setParam('q', e.target.value); }}
          onBlur={e => setParam('q', e.target.value)}
          className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-900"
        />
      </div>

      {/* Format */}
      <div>
        <p className="font-medium text-zinc-700 mb-2">{t('format')}</p>
        <div className="flex flex-wrap gap-1.5">
          {FORMATS.map(f => {
            const active = getParam('format') === f;
            return (
              <button
                key={f}
                onClick={() => setParam('format', active ? '' : f)}
                className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                  active
                    ? 'bg-zinc-900 text-white border-zinc-900'
                    : 'border-zinc-200 text-zinc-600 hover:border-zinc-400'
                }`}
              >
                {f}
              </button>
            );
          })}
        </div>
      </div>

      {/* Etiquetes */}
      {etiquetes.length > 0 && (
        <div>
          <p className="font-medium text-zinc-700 mb-2">{t('tags')}</p>
          <div className="flex flex-wrap gap-1.5">
            {etiquetes.map(et => {
              const active = getParam('etiqueta') === et.slug;
              return (
                <button
                  key={et.id}
                  onClick={() => setParam('etiqueta', active ? '' : et.slug)}
                  className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                    active ? 'text-white border-transparent' : 'text-zinc-600 bg-white border-zinc-200 hover:border-zinc-400'
                  }`}
                  style={active ? { backgroundColor: et.color || '#18181b', borderColor: et.color || '#18181b' } : {}}
                >
                  {et.nom_ca}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Genre */}
      <div>
        <p className="font-medium text-zinc-700 mb-2">{t('genre')}</p>
        <input
          type="text"
          placeholder="Jazz, Rock, Electronic…"
          aria-label={t('genre')}
          defaultValue={getParam('genre')}
          onKeyDown={e => { if (e.key === 'Enter') setParam('genre', e.target.value); }}
          onBlur={e => setParam('genre', e.target.value)}
          className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-900"
        />
      </div>

      {/* Price */}
      <div>
        <p className="font-medium text-zinc-700 mb-2">{t('priceEur')}</p>
        <div className="flex items-center gap-2">
          <input
            type="number"
            min="0"
            placeholder={t('min')}
            defaultValue={getParam('min')}
            onBlur={e => setParam('min', e.target.value)}
            className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-900"
          />
          <span className="text-zinc-500 shrink-0">–</span>
          <input
            type="number"
            min="0"
            placeholder={t('max')}
            defaultValue={getParam('max')}
            onBlur={e => setParam('max', e.target.value)}
            className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-900"
          />
        </div>
      </div>
    </div>
  );
}
