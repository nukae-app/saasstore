import { getTranslations } from 'next-intl/server';
import { Link } from '../../i18n/navigation';
import { Music2, LayoutGrid, Zap, Mic2, Waves, Disc } from 'lucide-react';
import { api } from '../../app/lib/api';

// Icones purament decoratives, es reparteixen en cicle per gènere — ja no hi
// ha una relació fixa "Jazz→Music2" perquè el gènere ja no és una llista
// tancada (ver sota).
const ICONS = [Music2, LayoutGrid, Zap, Mic2, Waves, Disc];

// Bloc "genre_grid" — sense props configurables (EmptyProps), es resol
// sencer aquí mateix contra GET /catalog/generes: els gèneres reals amb
// estoc disponible del tenant, no una llista fixa al codi. Abans hi havia 6
// gèneres en dur (Jazz, Electronic, Rock...) que podien no existir al
// catàleg real d'un tenant concret i enllaçar a una pàgina buida.
export default async function GenreGrid({ id }) {
  const t = await getTranslations('genres');
  let generes = [];
  try {
    generes = await api('/catalog/generes?limit=6');
  } catch {}

  if (generes.length === 0) return null;

  return (
    <section
      data-block-id={id}
      style={{
        paddingTop: 'var(--spacing-density)',
        paddingBottom: 'var(--spacing-density)',
        borderTop: 'var(--section-divider, none)',
      }}
      className="px-5 md:px-16 bg-white"
    >
      <div className="max-w-[var(--content-width,1280px)] mx-auto">
        <h2
          style={{ textTransform: 'var(--eyebrow-style, uppercase)' }}
          className="font-mono text-xs text-zinc-500 text-center uppercase tracking-[0.4em] mb-16 md:mb-20"
        >
          {t('exploreByGenre')}
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-6 md:gap-8">
          {generes.map(({ genero }, i) => {
            const Icon = ICONS[i % ICONS.length];
            return (
              <Link
                key={genero}
                href={`/cataleg?genre=${encodeURIComponent(genero)}`}
                style={{
                  borderRadius: 'var(--radius-card, 24px)',
                  border: 'var(--border-card, 1px solid #e4e4e7)',
                }}
                className="bg-white py-12 text-center group hover:bg-zinc-50 transition-colors"
              >
                <Icon size={32} className="mx-auto mb-6 text-zinc-500 group-hover:text-zinc-900 transition-colors" />
                <p
                  style={{ textTransform: 'var(--eyebrow-style, uppercase)' }}
                  className="text-xs uppercase tracking-widest text-zinc-900 font-medium"
                >
                  {genero}
                </p>
              </Link>
            );
          })}
        </div>
      </div>
    </section>
  );
}
