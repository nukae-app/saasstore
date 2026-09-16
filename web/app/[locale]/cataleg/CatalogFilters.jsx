'use client';

import { useSearchParams } from 'next/navigation';
import { useRouter } from '../../../i18n/navigation';
import { useTranslations } from 'next-intl';
import { useEffect, useState, useTransition } from 'react';
import { X, Search } from 'lucide-react';
import { api } from '../../lib/api';

const FORMATS = ['LP', '12"', '10"', '7"', 'CD', 'Cassette', 'EP'];

// `layout="horizontal"` és la banda de filtres a dalt del catàleg sota
// Recordstore (ver [locale]/cataleg/page.jsx) — `layout="vertical"`
// (per defecte) és la barra lateral del tema per defecte I el panell
// mòbil (MobileFilterSheet.jsx sempre la fa servir, cap tema hi cap una
// banda horitzontal dins d'un sheet estret).
export default function CatalogFilters({ className = '', showFormatFilter = true, showGenreFilter = true, layout = 'vertical' }) {
  const t = useTranslations('cataleg');
  const router = useRouter();
  const searchParams = useSearchParams();
  const [, startTransition] = useTransition();
  const [etiquetes, setEtiquetes] = useState([]);
  const [generes, setGeneres] = useState([]);
  // Tema "Recordstore" (ver StorefrontNav.jsx per al mateix patró) — etiquetes
  // dels filtres en majúscules/negreta en comptes del "font-medium" gris pla
  // del tema per defecte.
  const [recordstore, setRecordstore] = useState(false);

  useEffect(() => {
    api('/catalog/etiquetes').then(setEtiquetes).catch(() => {});
    api('/catalog/generes?limit=24').then(setGeneres).catch(() => {});
    fetch('/api/config/public')
      .then(r => (r.ok ? r.json() : null))
      .then(data => { if (data?.theme?.preset === 'recordstore') setRecordstore(true); })
      .catch(() => {});
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

  if (recordstore && layout === 'horizontal') {
    return (
      <div className={`border-b-2 border-black pb-8 mb-10 ${className}`}>
        <div className="grid grid-cols-1 md:grid-cols-[140px_1fr] gap-4 md:gap-10">
          <div className="flex items-start justify-between md:block">
            <p className="font-serif text-2xl uppercase tracking-tight text-black">{t('filters')}</p>
            {hasFilters && (
              <button
                onClick={clearAll}
                className="flex items-center gap-1 text-xs font-bold uppercase tracking-wide text-zinc-500 hover:text-black transition-colors md:mt-3"
              >
                <X size={12} /> {t('clearFilters')}
              </button>
            )}
          </div>

          <div className="space-y-4">
            <div className="relative">
              <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400 pointer-events-none" />
              <input
                type="text"
                placeholder={t('searchPlaceholder')}
                defaultValue={getParam('q')}
                onKeyDown={e => { if (e.key === 'Enter') setParam('q', e.target.value); }}
                onBlur={e => setParam('q', e.target.value)}
                className="w-full border border-black pl-10 pr-3 py-3 text-sm uppercase tracking-wide placeholder:text-zinc-400 focus:outline-none"
              />
            </div>

            {showFormatFilter && (
              <FilterRow label={t('format')}>
                {FORMATS.map(f => {
                  const active = getParam('format') === f;
                  return (
                    <Pill key={f} active={active} onClick={() => setParam('format', active ? '' : f)}>
                      {f}
                    </Pill>
                  );
                })}
              </FilterRow>
            )}

            {etiquetes.length > 0 && (
              <FilterRow label={t('tags')}>
                {etiquetes.map(et => {
                  const active = getParam('etiqueta') === et.slug;
                  return (
                    <Pill key={et.id} active={active} onClick={() => setParam('etiqueta', active ? '' : et.slug)}>
                      {et.name_ca}
                    </Pill>
                  );
                })}
              </FilterRow>
            )}

            {showGenreFilter && (
              <FilterRow label={t('genre')}>
                <select
                  value={getParam('genre')}
                  onChange={e => setParam('genre', e.target.value)}
                  className="border border-black px-3 py-2 text-sm uppercase tracking-wide bg-white focus:outline-none"
                >
                  <option value="">{t('allGenres')}</option>
                  {generes.map(({ genero }) => (
                    <option key={genero} value={genero}>{genero}</option>
                  ))}
                </select>
              </FilterRow>
            )}

            <FilterRow label={t('priceEur')}>
              <input
                type="number"
                min="0"
                placeholder={t('min')}
                defaultValue={getParam('min')}
                onBlur={e => setParam('min', e.target.value)}
                className="w-24 border border-black px-3 py-2 text-sm placeholder:text-zinc-400 focus:outline-none"
              />
              <span className="text-zinc-400">–</span>
              <input
                type="number"
                min="0"
                placeholder={t('max')}
                defaultValue={getParam('max')}
                onBlur={e => setParam('max', e.target.value)}
                className="w-24 border border-black px-3 py-2 text-sm placeholder:text-zinc-400 focus:outline-none"
              />
            </FilterRow>
          </div>
        </div>
      </div>
    );
  }

  const labelClass = recordstore
    ? 'font-semibold text-black uppercase tracking-wide text-xs mb-2'
    : 'font-medium text-zinc-700 mb-2';

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
        <p className={labelClass}>{t('search')}</p>
        <input
          type="text"
          placeholder={t('searchPlaceholder')}
          defaultValue={getParam('q')}
          onKeyDown={e => { if (e.key === 'Enter') setParam('q', e.target.value); }}
          onBlur={e => setParam('q', e.target.value)}
          className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-900"
        />
      </div>

      {/* Format — vocabulari de format musical, només per a vinils */}
      {showFormatFilter && (
        <div>
          <p className={labelClass}>{t('format')}</p>
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
      )}

      {/* Etiquetes */}
      {etiquetes.length > 0 && (
        <div>
          <p className={labelClass}>{t('tags')}</p>
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
                  {et.name_ca}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Genre — vocabulari musical, només per a vinils */}
      {showGenreFilter && (
        <div>
          <p className={labelClass}>{t('genre')}</p>
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
      )}

      {/* Price */}
      <div>
        <p className={labelClass}>{t('priceEur')}</p>
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

function FilterRow({ label, children }) {
  return (
    <div className="flex flex-wrap items-center gap-3 md:gap-4">
      <span className="text-xs font-bold uppercase tracking-wide text-black w-20 shrink-0">{label}</span>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </div>
  );
}

function Pill({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-wide border-2 transition-colors ${
        active ? 'bg-black text-white border-black' : 'border-black text-black hover:bg-black hover:text-white'
      }`}
    >
      {children}
    </button>
  );
}
