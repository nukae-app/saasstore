'use client';

import { useRef } from 'react';
import { useTranslations } from 'next-intl';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import ReleaseCard from './ReleaseCard';

export default function ReleaseCarousel({ releases }) {
  const t = useTranslations('common');
  const trackRef = useRef(null);

  function scrollBy(dir) {
    const track = trackRef.current;
    if (!track) return;
    track.scrollBy({ left: dir * track.clientWidth * 0.9, behavior: 'smooth' });
  }

  return (
    <div className="relative group">
      <div
        ref={trackRef}
        className="flex gap-4 md:gap-6 overflow-x-auto snap-x snap-mandatory scroll-smooth pb-2 -mx-1 px-1 [&::-webkit-scrollbar]:hidden [scrollbar-width:none]"
      >
        {releases.map(r => (
          <div key={r.id} className="w-[42%] sm:w-[30%] md:w-[22%] shrink-0 snap-start">
            <ReleaseCard release={r} />
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={() => scrollBy(-1)}
        aria-label={t('previous')}
        className="hidden md:flex items-center justify-center absolute -left-4 top-1/3 -translate-y-1/2 w-9 h-9 rounded-full bg-white border border-zinc-200 shadow-md text-zinc-600 hover:text-zinc-900 opacity-0 group-hover:opacity-100 transition-opacity"
      >
        <ChevronLeft size={18} />
      </button>
      <button
        type="button"
        onClick={() => scrollBy(1)}
        aria-label={t('next')}
        className="hidden md:flex items-center justify-center absolute -right-4 top-1/3 -translate-y-1/2 w-9 h-9 rounded-full bg-white border border-zinc-200 shadow-md text-zinc-600 hover:text-zinc-900 opacity-0 group-hover:opacity-100 transition-opacity"
      >
        <ChevronRight size={18} />
      </button>
    </div>
  );
}
