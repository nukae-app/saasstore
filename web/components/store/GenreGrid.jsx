import { getTranslations } from 'next-intl/server';
import { Link } from '../../i18n/navigation';
import { Music2, LayoutGrid, Zap, Mic2, Waves, Disc } from 'lucide-react';

const GENRES = [
  { key: 'jazz', genre: 'Jazz', icon: Music2 },
  { key: 'electronic', genre: 'Electronic', icon: LayoutGrid },
  { key: 'rock', genre: 'Rock', icon: Zap },
  { key: 'hiphop', genre: 'Hip-Hop', icon: Mic2 },
  { key: 'ambient', genre: 'Ambient', icon: Waves },
  { key: 'classical', genre: 'Classical', icon: Disc },
];

export default async function GenreGrid({ id }) {
  const t = await getTranslations('genres');
  return (
    <section data-block-id={id} className="py-24 md:py-32 px-5 md:px-16 bg-white">
      <div className="max-w-[1280px] mx-auto">
        <h2 className="font-mono text-xs text-zinc-500 text-center uppercase tracking-[0.4em] mb-16 md:mb-20">
          {t('exploreByGenre')}
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-6 md:gap-8">
          {GENRES.map(({ key, genre, icon: Icon }) => (
            <Link
              key={genre}
              href={`/cataleg?genre=${encodeURIComponent(genre)}`}
              className="rounded-3xl border border-zinc-200 bg-white py-12 text-center group hover:bg-zinc-50 hover:border-zinc-300 transition-colors"
            >
              <Icon size={32} className="mx-auto mb-6 text-zinc-500 group-hover:text-zinc-900 transition-colors" />
              <p className="text-xs uppercase tracking-widest text-zinc-900 font-medium">{t(key)}</p>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
