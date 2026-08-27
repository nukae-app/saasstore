'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useRouter } from '../../i18n/navigation';
import { useTranslations } from 'next-intl';
import Image from 'next/image';
import { api } from '../../app/lib/api';
import Crate from './Crate';

export default function CrateBrowser() {
  return (
    <Suspense>
      <CrateBrowserInner />
    </Suspense>
  );
}

function CrateBrowserInner() {
  const t = useTranslations('crate');
  const router = useRouter();
  const searchParams = useSearchParams();
  const cubetaSlug = searchParams.get('cubeta');
  const [seccions, setSeccions] = useState(null);

  useEffect(() => {
    api('/catalog/seccions').then(setSeccions).catch(() => setSeccions([]));
  }, []);

  if (seccions === null) {
    return <p className="text-sm text-zinc-400 py-16 text-center">{t('loading')}</p>;
  }

  if (seccions.length === 0) {
    return (
      <p className="text-sm text-zinc-400 py-16 text-center">
        {t('noneConfigured')}
      </p>
    );
  }

  const SENSE_CLASSIFICAR = {
    id: 'sense-classificar',
    slug: 'sense-classificar',
    name_ca: t('unclassified'),
    color: '#d4d4d8',
  };
  const totes = [...seccions, SENSE_CLASSIFICAR];

  function pick(slug) {
    const qs = new URLSearchParams(searchParams.toString());
    qs.set('cubeta', slug);
    router.push(`/cataleg?${qs.toString()}`);
  }

  function back() {
    const qs = new URLSearchParams(searchParams.toString());
    qs.delete('cubeta');
    router.push(`/cataleg?${qs.toString()}`);
  }

  const seccio = totes.find(s => s.slug === cubetaSlug);

  if (!seccio) {
    return <CubetaSelector seccions={totes} onPick={pick} />;
  }

  return <Crate seccio={seccio} onBack={back} />;
}

function CubetaSelector({ seccions, onPick }) {
  const t = useTranslations('crate');
  return (
    <div>
      <p className="text-sm text-zinc-500 mb-6 max-w-md">
        {t('pickPrompt')}
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        {seccions.map(s => (
          <CubetaTile key={s.slug} seccio={s} onPick={onPick} />
        ))}
      </div>
    </div>
  );
}

function CubetaTile({ seccio, onPick }) {
  const t = useTranslations('crate');
  const [total, setTotal] = useState(null);
  const [covers, setCovers] = useState([]);

  useEffect(() => {
    const qs = new URLSearchParams({ seccio: seccio.slug, page: '1', page_size: '4' });
    api(`/catalog?${qs}`)
      .then(data => {
        setTotal(data.total);
        setCovers(data.results.map(r => r.image_url).filter(Boolean));
      })
      .catch(() => {});
  }, [seccio.slug]);

  // La cubeta "Sense classificar" només té sentit mostrar-la si de fet hi ha discos a classificar.
  if (seccio.slug === 'sense-classificar' && total === 0) return null;

  return (
    <button
      onClick={() => onPick(seccio.slug)}
      className="group relative block w-full aspect-[4/3] rounded-3xl overflow-hidden shadow-sm hover:shadow-xl transition-shadow bg-zinc-200"
    >
      <div className="absolute inset-0 grid grid-cols-2 grid-rows-2 gap-0.5">
        {[0, 1, 2, 3].map(i => (
          <div key={i} className="relative bg-zinc-300 overflow-hidden">
            {covers[i] && (
              <Image
                src={covers[i]}
                alt=""
                fill
                sizes="(max-width: 640px) 50vw, 33vw"
                className="object-cover transition-transform duration-500 group-hover:scale-105"
              />
            )}
          </div>
        ))}
      </div>

      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/35 to-transparent p-5 pt-16">
        <p className="flex items-center gap-2 font-serif italic text-2xl text-white leading-snug">
          <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: seccio.color || '#94a3b8' }} />
          {seccio.name_ca}
        </p>
        <p className="text-white/70 text-xs mt-0.5">{total !== null ? t('recordCount', { count: total }) : ' '}</p>
      </div>
    </button>
  );
}
