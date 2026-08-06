'use client';

import { useState } from 'react';
import { Link } from '../../../i18n/navigation';
import { useTranslations } from 'next-intl';
import { ChevronRight } from 'lucide-react';

export default function ArchiveSidebar({ archive, currentYear, currentMonth, basePath = '/blog' }) {
  const t = useTranslations('blog');
  // Agrupar per any
  const byYear = {};
  for (const item of archive) {
    if (!byYear[item.year]) byYear[item.year] = [];
    byYear[item.year].push(item);
  }
  const years = Object.keys(byYear).map(Number).sort((a, b) => b - a);

  // Anys expandits: per defecte l'any actiu o el més recent
  const defaultOpen = currentYear ?? years[0];
  const [openYears, setOpenYears] = useState(new Set([defaultOpen]));

  function toggleYear(year) {
    setOpenYears(prev => {
      const next = new Set(prev);
      if (next.has(year)) next.delete(year);
      else next.add(year);
      return next;
    });
  }

  const total = archive.reduce((s, a) => s + a.count, 0);

  return (
    <aside className="w-52 shrink-0">
      <div className="sticky top-24 bg-white rounded-2xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] overflow-hidden">
        <div className="px-4 py-3 border-b border-zinc-50">
          <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">{t('archive')}</p>
        </div>

        <nav className="p-2 max-h-[70vh] overflow-y-auto">
          {/* Tots els posts */}
          <Link
            href={basePath}
            className={`flex items-center justify-between px-3 py-1.5 rounded-lg text-sm transition-colors mb-2 ${
              !currentYear && !currentMonth
                ? 'bg-zinc-900 text-white font-medium'
                : 'text-zinc-600 hover:bg-zinc-50'
            }`}
          >
            <span>{t('allPosts')}</span>
            <span className={`text-xs ${!currentYear ? 'text-zinc-300' : 'text-zinc-400'}`}>
              {total}
            </span>
          </Link>

          {/* Anys col·lapsables */}
          {years.map(year => {
            const isOpen = openYears.has(year);
            const isActiveYear = currentYear === year;
            const yearTotal = byYear[year].reduce((s, m) => s + m.count, 0);

            return (
              <div key={year} className="mb-0.5">
                {/* Capçalera de l'any */}
                <button
                  onClick={() => toggleYear(year)}
                  className={`w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-sm transition-colors group ${
                    isActiveYear
                      ? 'text-zinc-900 font-semibold'
                      : 'text-zinc-500 hover:bg-zinc-50 hover:text-zinc-800'
                  }`}
                >
                  <span className="flex items-center gap-1.5">
                    <ChevronRight
                      size={12}
                      className={`shrink-0 transition-transform duration-200 ${isOpen ? 'rotate-90' : ''} ${isActiveYear ? 'text-zinc-900' : 'text-zinc-300 group-hover:text-zinc-400'}`}
                    />
                    {year}
                  </span>
                  <span className="text-xs text-zinc-300">{yearTotal}</span>
                </button>

                {/* Mesos (expandits) */}
                {isOpen && (
                  <div className="pl-3 mt-0.5 mb-1 border-l-2 border-zinc-100 ml-4">
                    {byYear[year].map(item => {
                      const active = currentYear === item.year && currentMonth === item.month;
                      return (
                        <Link
                          key={`${item.year}-${item.month}`}
                          href={`${basePath}?year=${item.year}&month=${item.month}`}
                          className={`flex items-center justify-between px-2 py-1 rounded-lg text-xs transition-colors ${
                            active
                              ? 'bg-zinc-100 text-zinc-900 font-semibold'
                              : 'text-zinc-500 hover:bg-zinc-50 hover:text-zinc-800'
                          }`}
                        >
                          <span>{t(`monthsShort.${item.month}`)}</span>
                          <span className={`${active ? 'text-zinc-900' : 'text-zinc-300'}`}>
                            {item.count}
                          </span>
                        </Link>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </nav>
      </div>
    </aside>
  );
}
