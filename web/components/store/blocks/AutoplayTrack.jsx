'use client';

import { useEffect, useRef } from 'react';
import ReleaseCard from '../ReleaseCard';

// Variant "autoplay" del bloc "carousel" — mateixa targeta que "classic"
// (ReleaseCard, ver ReleaseCarousel.jsx), però la pista es desplaça sola
// cada pocs segons i es para en passar-hi el ratolí per sobre.
export default function AutoplayTrack({ releases }) {
  const trackRef = useRef(null);
  const pausedRef = useRef(false);

  useEffect(() => {
    const track = trackRef.current;
    if (!track) return;
    const interval = setInterval(() => {
      if (pausedRef.current) return;
      const atEnd = track.scrollLeft + track.clientWidth >= track.scrollWidth - 4;
      track.scrollBy({ left: atEnd ? -track.scrollLeft : track.clientWidth * 0.6, behavior: 'smooth' });
    }, 3500);
    return () => clearInterval(interval);
  }, []);

  return (
    <div
      ref={trackRef}
      onMouseEnter={() => { pausedRef.current = true; }}
      onMouseLeave={() => { pausedRef.current = false; }}
      className="flex gap-4 md:gap-6 overflow-x-auto snap-x snap-mandatory scroll-smooth pb-2 -mx-1 px-1 [&::-webkit-scrollbar]:hidden [scrollbar-width:none]"
    >
      {releases.map((r) => (
        <div key={r.id} className="w-[42%] sm:w-[30%] md:w-[22%] shrink-0 snap-start">
          <ReleaseCard release={r} />
        </div>
      ))}
    </div>
  );
}
