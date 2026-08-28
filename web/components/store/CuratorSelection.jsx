'use client';

import { useRef } from 'react';
import { useTranslations } from 'next-intl';
import { Link } from '../../i18n/navigation';
import Image from 'next/image';
import { ChevronLeft, ChevronRight } from 'lucide-react';

const CARD_SIZE = 'w-[70%] sm:w-[42%] lg:w-[30%] h-[420px] md:h-[520px]';

export default function CuratorSelection({ id, releases }) {
  const t = useTranslations('home');
  const trackRef = useRef(null);

  if (!releases || releases.length === 0) return null;

  function scrollBy(dir) {
    const track = trackRef.current;
    if (!track) return;
    track.scrollBy({ left: dir * track.clientWidth * 0.8, behavior: 'smooth' });
  }

  return (
    <section
      data-block-id={id}
      style={{
        paddingTop: 'var(--spacing-density)',
        paddingBottom: 'var(--spacing-density)',
        borderTop: 'var(--section-divider, none)',
      }}
      className="px-5 md:px-16 bg-background"
    >
      <div className="max-w-[var(--content-width,1280px)] mx-auto">
        <div className="flex items-end justify-between mb-10 md:mb-12">
          <h2 className="font-serif italic text-3xl md:text-4xl">{t('curatorSelection')}</h2>
          <div className="hidden md:flex gap-2">
            <button
              type="button"
              onClick={() => scrollBy(-1)}
              aria-label={t('previous')}
              className="w-10 h-10 rounded-full border border-zinc-200 flex items-center justify-center text-zinc-600 hover:text-zinc-900 hover:border-zinc-300 transition-colors"
            >
              <ChevronLeft size={18} />
            </button>
            <button
              type="button"
              onClick={() => scrollBy(1)}
              aria-label={t('next')}
              className="w-10 h-10 rounded-full border border-zinc-200 flex items-center justify-center text-zinc-600 hover:text-zinc-900 hover:border-zinc-300 transition-colors"
            >
              <ChevronRight size={18} />
            </button>
          </div>
        </div>

        <div
          ref={trackRef}
          className="flex gap-6 md:gap-8 overflow-x-auto snap-x snap-mandatory scroll-smooth pb-2 -mx-1 px-1 [&::-webkit-scrollbar]:hidden [scrollbar-width:none]"
        >
          {releases.map(r => (
            <Link
              key={r.id}
              href={`/disc/${r.id}`}
              style={{
                borderRadius: 'var(--radius-card, 24px)',
                boxShadow: 'var(--shadow-card, 0 10px 40px -10px rgba(0,0,0,0.12))',
                border: 'var(--border-card, none)',
              }}
              className={`group relative shrink-0 snap-start overflow-hidden bg-zinc-100 ${CARD_SIZE}`}
            >
              {r.image_url && (
                <Image
                  src={r.image_url}
                  alt=""
                  fill
                  sizes="(max-width: 768px) 70vw, 30vw"
                  style={{ filter: 'var(--image-treatment, none)' }}
                  className="object-cover group-hover:scale-110 transition-transform duration-1000"
                />
              )}
              <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/15 to-transparent p-6 md:p-8 flex flex-col justify-end">
                <span
                  style={{ textTransform: 'var(--eyebrow-style, uppercase)' }}
                  className="font-mono text-[10px] text-white/70 uppercase tracking-widest mb-2"
                >
                  {[r.formato, r.sello].filter(Boolean).join(' · ')}
                </span>
                <h3 className="font-serif italic text-xl md:text-2xl text-white leading-snug mb-1 line-clamp-2">
                  {r.title}
                </h3>
                <p className="text-white/80 text-sm truncate">{r.artista}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
