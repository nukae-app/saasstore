'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from '../../i18n/navigation';
import { useTranslations } from 'next-intl';
import Image from 'next/image';
import { ChevronLeft } from 'lucide-react';
import { api } from '../../app/lib/api';
import AddToCartButton from './AddToCartButton';

const PAGE_SIZE = 12;
const MAX_TILT_DEG = 18;

const GRADING = {
  M: 'Mint', NM: 'Near Mint', VG_PLUS: 'VG+', VG: 'Very Good',
  G_PLUS: 'G+', G: 'Good', F: 'Fair', P: 'Poor',
};

function ConditionBadge({ value }) {
  const label = GRADING[value] || value;
  const color =
    ['M', 'NM'].includes(value) ? 'bg-green-100 text-green-800' :
    ['VG_PLUS', 'VG'].includes(value) ? 'bg-amber-100 text-amber-800' :
    'bg-zinc-100 text-zinc-700';
  return <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${color}`}>{label}</span>;
}

function storageKey(seccioSlug, rang) {
  return `remena:${seccioSlug}:${rang || 'all'}`;
}

function loadCached(seccioSlug, rang) {
  try {
    const raw = sessionStorage.getItem(storageKey(seccioSlug, rang));
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveCached(seccioSlug, rang, snapshot) {
  try {
    sessionStorage.setItem(storageKey(seccioSlug, rang), JSON.stringify(snapshot));
  } catch {
    // Quota superada o sessionStorage no disponible: es perd només la restauració, no la navegació.
  }
}

const RANGES = [
  { key: '0-9', label: '0–9' },
  { key: 'A-D', label: 'A–D' },
  { key: 'E-H', label: 'E–H' },
  { key: 'I-L', label: 'I–L' },
  { key: 'M-P', label: 'M–P' },
  { key: 'Q-T', label: 'Q–T' },
  { key: 'U-Z', label: 'U–Z' },
];

export default function Crate({ seccio, onBack }) {
  const t = useTranslations('crate');
  const [rang, setRang] = useState(null);
  const [releases, setReleases] = useState([]);
  const [total, setTotal] = useState(null);
  const [loading, setLoading] = useState(false);
  const trackRef = useRef(null);
  const sentinelRef = useRef(null);
  const rafRef = useRef(null);
  const finePointerRef = useRef(false);

  useEffect(() => {
    finePointerRef.current =
      typeof window !== 'undefined' && window.matchMedia('(pointer: fine)').matches;
  }, []);

  // Ref amb l'estat viu perquè fetchNextPage no hagi de dependre de page/total/loading,
  // i còpia de "releases" per poder desar a sessionStorage sense esperar el re-render.
  const stateRef = useRef({ page: 0, total: null, loading: false });
  const releasesRef = useRef([]);
  const scrollSaveTimer = useRef(null);
  useEffect(() => { stateRef.current.loading = loading; }, [loading]);

  const fetchNextPage = useCallback(async () => {
    const { page: curPage, total: curTotal, loading: curLoading } = stateRef.current;
    if (curLoading) return;
    if (curTotal !== null && curPage * PAGE_SIZE >= curTotal) return;
    setLoading(true);
    const nextPage = curPage + 1;
    try {
      const qs = new URLSearchParams({
        seccio: seccio.slug, page: String(nextPage), page_size: String(PAGE_SIZE),
      });
      if (rang) qs.set('rang', rang);
      const data = await api(`/catalog?${qs}`);
      const merged = nextPage === 1 ? data.results : [...releasesRef.current, ...data.results];
      setReleases(merged);
      setTotal(data.total);
      releasesRef.current = merged;
      stateRef.current.page = nextPage;
      stateRef.current.total = data.total;
      saveCached(seccio.slug, rang, {
        releases: merged, total: data.total, page: nextPage,
        scrollTop: trackRef.current ? trackRef.current.scrollTop : 0,
      });
    } catch {
      // Silenciós: la cubeta simplement queda curta si l'API falla.
    } finally {
      setLoading(false);
    }
  }, [seccio.slug, rang]);

  // Nova cerca (canvi de cubeta o de tram alfabètic): restaura des de sessionStorage si
  // ja s'havia visitat abans en aquesta pestanya (p.ex. en tornar enrere des d'un disc),
  // o comença de zero si no.
  useEffect(() => {
    const cached = loadCached(seccio.slug, rang);
    if (cached?.releases?.length) {
      releasesRef.current = cached.releases;
      stateRef.current = { page: cached.page, total: cached.total, loading: false };
      setReleases(cached.releases);
      setTotal(cached.total);
      requestAnimationFrame(() => {
        if (trackRef.current) trackRef.current.scrollTop = cached.scrollTop || 0;
        applyTilt();
      });
    } else {
      releasesRef.current = [];
      stateRef.current = { page: 0, total: null, loading: false };
      setReleases([]);
      setTotal(null);
      if (trackRef.current) trackRef.current.scrollTo({ top: 0 });
      fetchNextPage();
    }
  }, [seccio.slug, rang, fetchNextPage]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const sentinel = sentinelRef.current;
    const track = trackRef.current;
    if (!sentinel || !track) return;
    const obs = new IntersectionObserver(
      entries => { if (entries[0].isIntersecting) fetchNextPage(); },
      { root: track, rootMargin: '0px 0px 600px 0px' }
    );
    obs.observe(sentinel);
    return () => obs.disconnect();
  }, [fetchNextPage]);

  const applyTilt = useCallback(() => {
    const track = trackRef.current;
    if (!track || !finePointerRef.current) return;
    const rect = track.getBoundingClientRect();
    const center = rect.top + rect.height / 2;
    track.querySelectorAll('[data-crate-card]').forEach(card => {
      const cardRect = card.getBoundingClientRect();
      const cardCenter = cardRect.top + cardRect.height / 2;
      const delta = Math.max(-1, Math.min(1, (cardCenter - center) / (rect.height / 2)));
      card.style.transform = `rotateX(${-delta * MAX_TILT_DEG}deg)`;
    });
  }, []);

  function onScroll() {
    if (rafRef.current === null) {
      rafRef.current = requestAnimationFrame(() => {
        applyTilt();
        rafRef.current = null;
      });
    }
    // Desa la posició (amb debounce) perquè en tornar d'un disc es restauri
    // encara que no s'hagi carregat cap pàgina nova mentre s'esperava.
    clearTimeout(scrollSaveTimer.current);
    scrollSaveTimer.current = setTimeout(() => {
      if (!trackRef.current || releasesRef.current.length === 0) return;
      saveCached(seccio.slug, rang, {
        releases: releasesRef.current, total: stateRef.current.total,
        page: stateRef.current.page, scrollTop: trackRef.current.scrollTop,
      });
    }, 250);
  }

  useEffect(() => { applyTilt(); }, [releases, applyTilt]);

  const hasMore = total === null || releases.length < total;

  return (
    <div className="flex flex-col" style={{ height: '80vh', minHeight: 560 }}>
      <div className="flex items-center gap-3 mb-4 px-1 shrink-0">
        <button onClick={onBack} className="flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-900 transition-colors">
          <ChevronLeft size={16} /> {t('crates')}
        </button>
        <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: seccio.color || '#94a3b8' }} />
        <h2 className="text-sm font-mono uppercase tracking-[0.25em] text-zinc-700">{seccio.name_ca}</h2>
        {total !== null && <span className="text-xs text-zinc-300">· {total}</span>}
      </div>

      <div
        ref={trackRef}
        onScroll={onScroll}
        style={{ perspective: '1000px' }}
        className="flex-1 min-h-0 overflow-y-auto snap-y snap-mandatory rounded-3xl bg-zinc-100 [&::-webkit-scrollbar]:hidden [scrollbar-width:none]"
      >
        {releases.map(r => <CrateCard key={r.id} release={r} />)}

        {hasMore && <div ref={sentinelRef} className="h-4" aria-hidden />}

        {releases.length === 0 && !loading && (
          <div className="flex items-center justify-center h-full text-sm text-zinc-400 px-6 text-center">
            {t('noRecordsInRange')}
          </div>
        )}
      </div>

      {/* Separadors alfabètics, com a la cubeta física */}
      <div className="flex justify-center gap-1.5 mt-4 flex-wrap shrink-0">
        <button
          onClick={() => setRang(null)}
          className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold border transition-colors ${!rang ? 'bg-zinc-900 text-white border-zinc-900' : 'border-zinc-200 text-zinc-600 hover:border-zinc-400'}`}
        >
          {t('all')}
        </button>
        {RANGES.map(rg => (
          <button
            key={rg.key}
            onClick={() => setRang(rg.key)}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold border transition-colors ${rang === rg.key ? 'bg-zinc-900 text-white border-zinc-900' : 'border-zinc-200 text-zinc-600 hover:border-zinc-400'}`}
          >
            {rg.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function CrateCard({ release: r }) {
  const t = useTranslations('crate');
  const td = useTranslations('disc');
  // Para nou (stock agregado), status se mantiene 'disponible' aunque no
  // quede ninguna unidad libre: hay que comprobar cantidad aparte.
  const disponibles = r.items.filter(i => i.condition === 'nou'
    ? i.status === 'disponible' && (i.quantity - i.reserved_quantity) > 0
    : i.status === 'disponible');
  const disponiblesNou = disponibles.filter(i => i.condition === 'nou');
  const disponiblesSegonaMa = disponibles.filter(i => i.condition !== 'nou');

  return (
    <div
      data-crate-card
      style={{ transformStyle: 'preserve-3d', transition: 'transform 120ms ease-out' }}
      className="snap-center flex flex-col items-center justify-center h-full w-full gap-3 px-6 py-6"
    >
      <Link href={`/disc/${r.id}`} className="relative block w-full max-w-md aspect-square rounded-2xl overflow-hidden shadow-2xl bg-zinc-300 shrink-0">
        {r.image_url ? (
          <Image src={r.image_url} alt={`${r.artista} — ${r.title}`} fill sizes="448px" className="object-cover" />
        ) : null}
        <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/40 to-transparent p-5 pt-20">
          <p className="text-white font-serif italic text-lg leading-snug truncate">{r.title}</p>
          <p className="text-white/80 text-sm font-medium truncate">{r.artista}</p>
        </div>
        {disponibles.length === 0 && (
          <div className="absolute inset-0 bg-white/60 flex items-center justify-center">
            <span className="text-xs font-medium text-zinc-500 bg-white px-2 py-1 rounded-full border">{t('soldOut')}</span>
          </div>
        )}
      </Link>

      <div className="w-full max-w-md shrink-0">
        <p className="flex items-center justify-center gap-1.5 text-xs text-zinc-500 mb-2 flex-wrap text-center">
          {[r.formato, r.sello, r.anio].filter(Boolean).join(' · ')}
        </p>

        {disponibles.length === 0 ? (
          <p className="text-center text-xs text-zinc-400 py-2">{t('noStockAvailable')}</p>
        ) : (
          <div className="space-y-1.5 max-h-24 overflow-y-auto">
            {disponiblesNou.map(item => (
              <div key={item.id} className="flex items-center justify-between gap-3 bg-white rounded-xl border border-zinc-200 px-3 py-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                    {td('newBadge')}
                  </span>
                  <span className="text-sm font-semibold text-zinc-900 shrink-0">
                    {parseFloat(item.price).toFixed(2)} €
                  </span>
                </div>
                <AddToCartButton itemId={item.id} className="px-3 py-1.5 text-xs shrink-0" />
              </div>
            ))}
            {disponiblesSegonaMa.map(item => (
              <div key={item.id} className="flex items-center justify-between gap-3 bg-white rounded-xl border border-zinc-200 px-3 py-2">
                <div className="flex items-center gap-2 min-w-0">
                  <ConditionBadge value={item.condition} />
                  <span className="text-sm font-semibold text-zinc-900 shrink-0">
                    {parseFloat(item.price).toFixed(2)} €
                  </span>
                </div>
                <AddToCartButton itemId={item.id} className="px-3 py-1.5 text-xs shrink-0" />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
