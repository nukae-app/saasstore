'use client';

import { useEffect, useState } from 'react';
import { Link } from '../../../../i18n/navigation';
import { useTranslations } from 'next-intl';
import { Music2, ChevronLeft, Disc3 } from 'lucide-react';
import { authFetch } from '../../../../components/store/AuthProvider';
import { useSpotifyEnabled } from '../../../../components/store/useSpotifyEnabled';
import NovaPeticioModal from '../../../../components/store/NovaPeticioModal';

const ESTAT_COLOR = {
  exacte: 'text-emerald-700 bg-emerald-50 border-emerald-200',
  artista: 'text-amber-700 bg-amber-50 border-amber-200',
  cap: 'text-zinc-500 bg-zinc-50 border-zinc-200',
};

function Avatar({ src, size }) {
  return (
    <div className="rounded-full overflow-hidden bg-zinc-100 flex items-center justify-center shrink-0" style={{ width: size, height: size }}>
      {src ? <img src={src} alt="" className="w-full h-full object-cover" /> : <Music2 size={size * 0.35} className="text-zinc-300" />}
    </div>
  );
}

function ArtistTile({ artist, onOpen }) {
  const t = useTranslations('artistes');
  const color = ESTAT_COLOR[artist.estat];
  return (
    <button onClick={() => onOpen(artist)}
      className="bg-white shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] rounded-xl p-3 flex flex-col items-center text-center hover:border-zinc-300 transition-colors">
      <Avatar src={artist.image_url} size={80} />
      <p className="font-medium text-sm text-zinc-900 truncate w-full mt-3" title={artist.name}>{artist.name}</p>
      {artist.genres?.length > 0 && (
        <p className="text-xs text-zinc-400 truncate w-full mb-2">{artist.genres.slice(0, 2).join(', ')}</p>
      )}
      <span className={`mt-auto pt-2 inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full border ${color}`}>
        {t(`estat.${artist.estat}`)}
      </span>
    </button>
  );
}

function AlbumTile({ album, artistName, onDemana, escoltat }) {
  const t = useTranslations('artistes');
  const color = ESTAT_COLOR[album.estat];
  return (
    <div className="bg-white shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] rounded-xl overflow-hidden">
      <div className="aspect-square bg-zinc-100 flex items-center justify-center relative">
        {album.imagen_url ? (
          <img src={album.imagen_url} alt={album.titulo} className="w-full h-full object-cover" />
        ) : (
          <Disc3 size={28} className="text-zinc-300" />
        )}
        {escoltat && (
          <span className="absolute top-2 left-2 inline-flex items-center gap-1 text-[10px] font-medium text-white bg-zinc-900/80 px-2 py-0.5 rounded-full">
            <Music2 size={10} /> {t('youListenToThis')}
          </span>
        )}
      </div>
      <div className="p-3">
        <p className="font-medium text-sm text-zinc-900 truncate" title={album.titulo}>{album.titulo}</p>
        <p className="text-xs text-zinc-400 truncate mb-2">{album.any || ''}</p>
        {album.estat === 'exacte' ? (
          <Link href={`/disc/${album.release.id}`}
            className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full border ${color} hover:opacity-80 transition-opacity`}>
            {t(`estat.${album.estat}`)}
          </Link>
        ) : (
          <button onClick={() => onDemana({ artista: artistName, titulo: album.titulo })}
            className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full border text-zinc-500 bg-zinc-50 border-zinc-200 hover:bg-zinc-100 hover:text-zinc-900 hover:border-zinc-300 transition-colors">
            {t('requestIt')}
          </button>
        )}
      </div>
    </div>
  );
}

function ArtistDetail({ artist, onBack, onDemana }) {
  const t = useTranslations('artistes');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [albums, setAlbums] = useState([]);
  const escoltats = new Set(artist.albums.map(al => al.spotify_album_id));

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    const qs = new URLSearchParams({ artist_name: artist.name });
    authFetch(`/api/auth/spotify/artists/${artist.spotify_id}/albums?${qs}`)
      .then(async r => {
        if (cancelled) return;
        if (!r.ok) { setError(true); return; }
        setAlbums(await r.json());
      })
      .catch(() => { if (!cancelled) setError(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [artist.spotify_id]);

  return (
    <div>
      <button onClick={onBack} className="flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-800 mb-4">
        <ChevronLeft size={16} /> {t('allArtists')}
      </button>
      <div className="flex items-center gap-4 mb-6">
        <Avatar src={artist.image_url} size={64} />
        <div>
          <h2 className="font-serif italic text-xl">{artist.name}</h2>
          {artist.genres?.length > 0 && <p className="text-xs text-zinc-400">{artist.genres.slice(0, 3).join(', ')}</p>}
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="animate-pulse bg-zinc-100 rounded-xl h-52" />
          ))}
        </div>
      ) : error ? (
        <p className="text-sm text-zinc-400">{t('couldNotLoadDiscography')}</p>
      ) : albums.length === 0 ? (
        <p className="text-sm text-zinc-400">{t('noDiscographyFound')}</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
          {albums.map(al => (
            <AlbumTile key={al.spotify_album_id} album={al} artistName={artist.name} onDemana={onDemana}
              escoltat={escoltats.has(al.spotify_album_id)} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function ArtistesPage() {
  const t = useTranslations('artistes');
  const TIME_RANGES = [
    { value: 'short_term', label: t('lastMonth') },
    { value: 'medium_term', label: t('last6Months') },
    { value: 'long_term', label: t('allTime') },
  ];
  const ESTAT_FILTERS = [
    { value: 'tots', label: t('all') },
    { value: 'exacte', label: t('exactRecord') },
    { value: 'artista', label: t('artistOnly') },
    { value: 'cap', label: t('neitherOne') },
  ];
  const enabled = useSpotifyEnabled();
  const [status, setStatus] = useState('loading'); // loading | not-connected | ok | error
  const [artists, setArtists] = useState([]);
  const [timeRange, setTimeRange] = useState('medium_term');
  const [filter, setFilter] = useState('tots');
  const [selected, setSelected] = useState(null);
  const [peticio, setPeticio] = useState(null); // { artista, titulo }
  const [peticioSaved, setPeticioSaved] = useState(false);

  useEffect(() => {
    if (enabled === null) return; // encara no sabem si el mòdul està actiu
    if (!enabled) { setStatus('disabled'); return; }
    let cancelled = false;
    setStatus('loading');
    setSelected(null);
    authFetch(`/api/auth/spotify/library?time_range=${timeRange}`)
      .then(async r => {
        if (cancelled) return;
        if (r.status === 404) { setStatus('not-connected'); return; }
        if (!r.ok) { setStatus('error'); return; }
        setArtists(await r.json());
        setStatus('ok');
      })
      .catch(() => { if (!cancelled) setStatus('error'); });
    return () => { cancelled = true; };
  }, [timeRange, enabled]);

  const visible = artists.filter(a => filter === 'tots' || a.estat === filter);
  const counts = {
    tots: artists.length,
    exacte: artists.filter(a => a.estat === 'exacte').length,
    artista: artists.filter(a => a.estat === 'artista').length,
    cap: artists.filter(a => a.estat === 'cap').length,
  };

  return (
    <div>
      <h1 className="font-serif italic text-2xl md:text-3xl mb-2">{t('myArtists')}</h1>
      <p className="text-sm text-zinc-500 mb-6">
        {t('myArtistsSubtitle')}
      </p>

      {status === 'disabled' && (
        <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] p-10 text-center">
          <Music2 size={32} className="text-zinc-200 mx-auto mb-3" />
          <p className="text-zinc-500 text-sm">{t('featureNotAvailable')}</p>
        </div>
      )}

      {status === 'not-connected' && (
        <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] p-10 text-center">
          <Music2 size={32} className="text-zinc-200 mx-auto mb-3" />
          <p className="text-zinc-500 text-sm mb-4">{t('spotifyNotConnectedYet')}</p>
          <Link href="/compte"
            className="inline-flex items-center gap-1.5 bg-primary hover:bg-zinc-800 text-white px-4 py-2 rounded-full text-sm font-medium transition-colors">
            {t('connectSpotify')}
          </Link>
        </div>
      )}

      {status === 'error' && (
        <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] p-10 text-center">
          <p className="text-zinc-500 text-sm">{t('couldNotLoadArtists')}</p>
        </div>
      )}

      {(status === 'loading' || status === 'ok') && !selected && (
        <>
          <div className="flex flex-wrap items-center gap-3 mb-6">
            <div className="flex gap-1 bg-zinc-100 rounded-lg p-1">
              {TIME_RANGES.map(tr => (
                <button key={tr.value} onClick={() => setTimeRange(tr.value)}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${timeRange === tr.value ? 'bg-white text-zinc-900 shadow-sm' : 'text-zinc-500 hover:text-zinc-700'}`}>
                  {tr.label}
                </button>
              ))}
            </div>
            {status === 'ok' && (
              <div className="flex gap-1 bg-zinc-100 rounded-lg p-1 flex-wrap">
                {ESTAT_FILTERS.map(f => (
                  <button key={f.value} onClick={() => setFilter(f.value)}
                    className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${filter === f.value ? 'bg-white text-zinc-900 shadow-sm' : 'text-zinc-500 hover:text-zinc-700'}`}>
                    {f.label} ({counts[f.value]})
                  </button>
                ))}
              </div>
            )}
          </div>

          {peticioSaved && (
            <div className="text-xs rounded-lg px-3 py-2 mb-4 bg-emerald-50 text-emerald-700">
              {t('requestSent')}
            </div>
          )}

          {status === 'loading' ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
              {Array.from({ length: 10 }).map((_, i) => (
                <div key={i} className="animate-pulse bg-zinc-100 rounded-xl h-40" />
              ))}
            </div>
          ) : visible.length === 0 ? (
            <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] p-10 text-center">
              <p className="text-zinc-400 text-sm">{t('noArtistsInFilter')}</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
              {visible.map(a => (
                <ArtistTile key={a.spotify_id} artist={a} onOpen={setSelected} />
              ))}
            </div>
          )}
        </>
      )}

      {status === 'ok' && selected && (
        <ArtistDetail artist={selected} onBack={() => setSelected(null)} onDemana={setPeticio} />
      )}

      {peticio && (
        <NovaPeticioModal
          initialArtista={peticio.artista}
          initialTitulo={peticio.titulo}
          onClose={() => setPeticio(null)}
          onSaved={() => { setPeticio(null); setPeticioSaved(true); }}
        />
      )}
    </div>
  );
}
