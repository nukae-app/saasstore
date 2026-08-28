import { getTranslations } from 'next-intl/server';

// Bloc "about_strip" — sense props configurables en v1 (ver
// api/app/blocks/registry.py::EmptyProps), sempre llegeix `config` en viu:
// és exactament el mateix contingut que ja mostrava la franja final del
// home abans del constructor de blocs.
export default async function AboutStripBlock({ config }) {
  const t = await getTranslations('home');
  const isVinils = !config || config.vertical === 'records';
  return (
    <section className="py-24 px-5 md:px-16 bg-zinc-50">
      <div className="max-w-2xl mx-auto text-center">
        <h2 className="font-serif italic text-2xl md:text-3xl mb-4 text-zinc-900">
          {config?.nombre || ''}
        </h2>
        <p className="text-zinc-500 leading-relaxed mb-6">
          {config?.address ? config.address.split('\n').join(', ') : t('aboutText')}
        </p>
        {isVinils && config?.discogs_habilitat && (
          <p className="text-sm text-zinc-500">
            {t('alsoOn')}{' '}
            <a
              href="https://www.discogs.com"
              target="_blank"
              rel="noopener"
              className="text-zinc-900 hover:underline"
            >
              Discogs
            </a>
          </p>
        )}
      </div>
    </section>
  );
}
