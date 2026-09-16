'use client';

import { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';

export default function DiscInfoTabs({ infoContent, spotifyAlbumId }) {
  const t = useTranslations('disc');
  const [tab, setTab] = useState('info');
  // Mateix patró client-side que ReleaseCard/CatalogFilters — l'únic control
  // d'aquesta fitxa que encara quedava sense tocar sota Recordstore.
  const [recordstore, setRecordstore] = useState(false);
  useEffect(() => {
    fetch('/api/config/public')
      .then(r => (r.ok ? r.json() : null))
      .then(data => { if (data?.theme?.preset === 'recordstore') setRecordstore(true); })
      .catch(() => {});
  }, []);

  if (!spotifyAlbumId) return infoContent;

  return (
    <div>
      {recordstore ? (
        <div className="flex items-center gap-3 mb-4 text-sm font-bold uppercase tracking-wide">
          <button onClick={() => setTab('info')} className={tab === 'info' ? 'text-black' : 'text-zinc-400 hover:text-black transition-colors'}>
            {t('infoTab')}
          </button>
          <span className="text-zinc-300">•</span>
          <button onClick={() => setTab('spotify')} className={tab === 'spotify' ? 'text-black' : 'text-zinc-400 hover:text-black transition-colors'}>
            {t('listenTab')}
          </button>
        </div>
      ) : (
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
      )}

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
