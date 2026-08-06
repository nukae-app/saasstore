'use client';

import { useLocale, useTranslations } from 'next-intl';

export default function ArchiveSelect({ archive, defaultValue, basePath = '/blog' }) {
  const locale = useLocale();
  const t = useTranslations('blog');
  const localizedBase = `/${locale}${basePath}`;
  return (
    <select
      defaultValue={defaultValue}
      onChange={e => {
        if (!e.target.value) window.location = localizedBase;
        else {
          const [y, m] = e.target.value.split('-');
          window.location = `${localizedBase}?year=${y}&month=${m}`;
        }
      }}
      className="w-full border border-zinc-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white"
    >
      <option value="">{t('allPosts')}</option>
      {archive.map(item => (
        <option key={`${item.year}-${item.month}`} value={`${item.year}-${item.month}`}>
          {item.label} ({item.count})
        </option>
      ))}
    </select>
  );
}
