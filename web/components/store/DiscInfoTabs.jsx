'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';

export default function DiscInfoTabs({ infoContent, spotifyAlbumId }) {
  const t = useTranslations('disc');
  const [tab, setTab] = useState('info');

  if (!spotifyAlbumId) return infoContent;

  return (
    <div>
      <div className="flex gap-1 bg-zinc-100 rounded-lg p-1 w-fit mb-4">
        <button onClick={() => setTab('info')}
          className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${tab === 'info' ? 'bg-white text-zinc-900 shadow-sm' : 'text-zinc-500 hover:text-zinc-700'}`}>
          {t('infoTab')}
        </button>
        <button onClick={() => setTab('spotify')}
          className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${tab === 'spotify' ? 'bg-white text-zinc-900 shadow-sm' : 'text-zinc-500 hover:text-zinc-700'}`}>
          {t('listenTab')}
        </button>
      </div>

      {tab === 'info' ? infoContent : (
        <iframe
          src={`https://open.spotify.com/embed/album/${spotifyAlbumId}?utm_source=generator`}
          width="100%"
          height="352"
          style={{ border: 0, borderRadius: 12 }}
          loading="lazy"
          allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"
        />
      )}
    </div>
  );
}
