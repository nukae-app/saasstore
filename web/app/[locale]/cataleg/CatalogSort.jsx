'use client';

import { useSearchParams } from 'next/navigation';
import { useRouter } from '../../../i18n/navigation';
import { useTranslations } from 'next-intl';
import { useTransition } from 'react';

const SORTS = ['novetats', 'preu_asc', 'preu_desc', 'artista', 'titol', 'any_desc', 'any_asc'];

// Selector d'ordenació del catàleg. L'estat viu a la URL (?sort=) perquè el
// llistat es renderitza al servidor i l'enllaç sigui compartible.
export default function CatalogSort() {
  const t = useTranslations('cataleg');
  const router = useRouter();
  const searchParams = useSearchParams();
  const [, startTransition] = useTransition();
  const current = SORTS.includes(searchParams.get('sort')) ? searchParams.get('sort') : 'novetats';

  function onChange(e) {
    const params = new URLSearchParams(searchParams.toString());
    params.set('sort', e.target.value);
    params.delete('page');
    startTransition(() => router.push(`/cataleg?${params.toString()}`));
  }

  return (
    <label className="flex items-center gap-2 text-sm text-zinc-600">
      <span>{t('sortBy')}</span>
      <select
        value={current}
        onChange={onChange}
        className="border border-zinc-300 bg-white px-2 py-1.5 text-sm text-zinc-900 rounded-md"
      >
        {SORTS.map(s => (
          <option key={s} value={s}>{t(`sort.${s}`)}</option>
        ))}
      </select>
    </label>
  );
}
