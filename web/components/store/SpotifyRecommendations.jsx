'use client';

import { useState, useEffect } from 'react';
import { useTranslations } from 'next-intl';
import { Link } from '../../i18n/navigation';
import { Music2, Loader2, RefreshCw } from 'lucide-react';
import { useAuth } from './AuthProvider';
import { authFetch } from './AuthProvider';
import { useSpotifyEnabled } from './useSpotifyEnabled';
import ReleaseCard from './ReleaseCard';

export default function SpotifyRecommendations() {
  const t = useTranslations('spotify');
  const { user } = useAuth();
  const enabled = useSpotifyEnabled();
  const [state, setState] = useState('idle'); // idle | loading | ok | not-connected | error
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!user || !enabled) return;
    setState('loading');
    authFetch('/api/auth/spotify/recommendations')
      .then(async r => {
        if (r.status === 404) { setState('not-connected'); return; }
        if (!r.ok) { setState('error'); return; }
        const d = await r.json();
        if (!d.releases?.length) { setState('idle'); return; }
        setData(d);
        setState('ok');
      })
      .catch(() => setState('error'));
  }, [user, enabled]);

  if (!user || !enabled || state === 'idle') return null;

  if (state === 'loading') {
    return (
      <section className="container py-12">
        <div className="flex items-center gap-2 text-zinc-400 text-sm">
          <Loader2 size={14} className="animate-spin" />
          {t('searching')}
        </div>
      </section>
    );
  }

  if (state === 'not-connected') {
    return (
      <section className="container py-12">
        <div className="bg-zinc-50 text-zinc-900 rounded-3xl p-8 flex flex-col sm:flex-row items-center gap-6 shadow-[0_2px_24px_-6px_rgba(15,23,42,0.08)]">
          <div className="w-12 h-12 rounded-full bg-[#1DB954] flex items-center justify-center shrink-0">
            <Music2 size={22} className="text-black" />
          </div>
          <div className="flex-1 text-center sm:text-left">
            <h3 className="font-semibold text-lg mb-1">{t('discoverTitle')}</h3>
            <p className="text-zinc-500 text-sm">
              {t('discoverSubtitle')}
            </p>
          </div>
          <Link
            href="/compte"
            className="shrink-0 flex items-center gap-2 bg-[#1DB954] hover:bg-[#1ed760] text-black font-semibold px-5 py-2.5 rounded-full text-sm transition-colors"
          >
            <Music2 size={15} /> {t('connect')}
          </Link>
        </div>
      </section>
    );
  }

  if (state === 'error' || !data) return null;

  return (
    <section className="container py-16">
      <div className="flex items-baseline justify-between mb-8">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <div className="w-5 h-5 rounded-full bg-[#1DB954] flex items-center justify-center">
              <Music2 size={11} className="text-black" />
            </div>
            <span className="text-xs font-semibold text-[#1DB954] uppercase tracking-widest">
              {t('forYou')}
            </span>
          </div>
          <h2 className="font-serif italic text-3xl md:text-4xl">{t('recommendedForYou')}</h2>
        </div>
        <button
          onClick={() => { setState('loading'); authFetch('/api/auth/spotify/recommendations').then(async r => { if (!r.ok) { setState('error'); return; } const d = await r.json(); setData(d); setState('ok'); }).catch(() => setState('error')); }}
          className="text-zinc-400 hover:text-zinc-700 transition-colors p-1"
          title={t('refresh')}
        >
          <RefreshCw size={15} />
        </button>
      </div>

      {data.top_artists?.length > 0 && (
        <p className="text-sm text-zinc-500 mb-6">
          {t('basedOnArtists')}{' '}
          <span className="font-medium text-zinc-700">
            {data.top_artists.slice(0, 3).join(', ')}
          </span>
          {data.top_artists.length > 3 ? '…' : ''}
        </p>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4 md:gap-6">
        {data.releases.map(r => (
          <ReleaseCard key={r.id} release={r} />
        ))}
      </div>
    </section>
  );
}
