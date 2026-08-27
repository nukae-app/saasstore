'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { SlidersHorizontal } from 'lucide-react';
import { Sheet, SheetContent, SheetTitle } from '../ui/sheet';
import CatalogFilters from '../../app/[locale]/cataleg/CatalogFilters';

export default function MobileFilterSheet({ isVinils = true }) {
  const t = useTranslations('cataleg');
  const [open, setOpen] = useState(false);
  const searchParams = useSearchParams();

  // Cualquier cambio de filtro navega (router.push dentro de CatalogFilters),
  // así que cerramos el sheet en cuanto la URL cambia en vez de exigir un
  // botón "Aplicar" aparte.
  useEffect(() => {
    setOpen(false);
  }, [searchParams]);

  const hasFilters = ['q', 'format', 'genre', 'etiqueta', 'min', 'max'].some(k => searchParams.has(k));

  return (
    <div className="md:hidden mb-6">
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-2 h-11 px-4 rounded-lg border border-zinc-200 text-sm font-medium text-zinc-700"
      >
        <SlidersHorizontal size={16} />
        {t('filters')}
        {hasFilters && <span className="w-2 h-2 rounded-full bg-zinc-900" />}
      </button>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="bottom" className="max-h-[85vh] overflow-y-auto rounded-t-2xl">
          <SheetTitle className="mb-2">{t('filters')}</SheetTitle>
          <CatalogFilters isVinils={isVinils} />
        </SheetContent>
      </Sheet>
    </div>
  );
}
