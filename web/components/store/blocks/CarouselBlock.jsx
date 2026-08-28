import { Link } from '../../../i18n/navigation';
import Image from 'next/image';
import { Package } from 'lucide-react';
import ReleaseCarousel from '../ReleaseCarousel';
import ReleaseCard from '../ReleaseCard';
import AutoplayTrack from './AutoplayTrack';

const MAX_GRID = 8;
const MAX_LIST = 6;
const MAX_FEATURED_SIDE = 4;

// Bloc "carousel" (ver api/app/blocks/registry.py::CarouselProps
// ::CAROUSEL_LAYOUTS per a les 8 disposicions). `heading`/`subtitle`/
// `cta_label` són copy del tenant; `releases` és el catàleg filtrat per
// `props.etiqueta_slug`, el resol page.jsx igual que fetchAllByEtiqueta() ja
// feia abans — mai dades de catàleg dins d'aquest component.
export default function CarouselBlock({ id, layout = 'classic', heading, subtitle, cta_label, releases = [] }) {
  if (releases.length === 0) return null;

  let body;
  switch (layout) {
    case 'overlay':
      body = <OverlayTrack releases={releases} />;
      break;
    case 'featured_large':
      body = <FeaturedLarge releases={releases} />;
      break;
    case 'list_rows':
      body = <ListRows releases={releases.slice(0, MAX_LIST)} />;
      break;
    case 'minimal':
      body = <MinimalTrack releases={releases} />;
      break;
    case 'grid':
      body = <StaticGrid releases={releases.slice(0, MAX_GRID)} />;
      break;
    case 'autoplay':
      body = <AutoplayTrack releases={releases} />;
      break;
    case 'oferta':
      body = <OfertaTrack releases={releases} />;
      break;
    case 'classic':
    default:
      body = <ReleaseCarousel releases={releases} />;
  }

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
        <div className="flex justify-between items-baseline mb-12 md:mb-16">
          <div>
            {heading && <h2 data-field="heading" className="font-serif italic text-3xl md:text-4xl">{heading}</h2>}
            {subtitle && <p data-field="subtitle" className="text-zinc-500 mt-2">{subtitle}</p>}
          </div>
          {cta_label && (
            <Link
              href="/cataleg"
              style={{ textTransform: 'var(--eyebrow-style, uppercase)' }}
              className="hidden sm:block text-xs font-medium text-zinc-900 uppercase tracking-widest hover:tracking-[0.15em] transition-all"
            >
              <span data-field="cta_label">{cta_label}</span>
            </Link>
          )}
        </div>
        {body}
      </div>
    </section>
  );
}

function minPriceOf(release) {
  const disponibles = release.items.filter((i) => (i.condition === 'nou'
    ? i.status === 'disponible' && (i.quantity - i.reserved_quantity) > 0
    : i.status === 'disponible'));
  const prices = disponibles.map((i) => parseFloat(i.price));
  return prices.length ? Math.min(...prices) : null;
}

// Targetes amb el text sobre la imatge (degradat) — mateix estil que
// "Selecció del curador" (CuratorSelection.jsx).
function OverlayTrack({ releases }) {
  return (
    <div className="flex gap-4 md:gap-6 overflow-x-auto snap-x snap-mandatory scroll-smooth pb-2 -mx-1 px-1 [&::-webkit-scrollbar]:hidden [scrollbar-width:none]">
      {releases.map((r) => (
        <Link
          key={r.id}
          href={`/disc/${r.id}`}
          style={{
            borderRadius: 'var(--radius-card, 24px)',
            boxShadow: 'var(--shadow-card, 0 10px 40px -10px rgba(0,0,0,0.12))',
            border: 'var(--border-card, none)',
          }}
          className="group relative shrink-0 snap-start overflow-hidden bg-zinc-100 w-[70%] sm:w-[42%] md:w-[30%] h-[420px]"
        >
          {r.image_url ? (
            <Image
              src={r.image_url}
              alt=""
              fill
              sizes="(max-width: 768px) 70vw, 30vw"
              style={{ filter: 'var(--image-treatment, none)' }}
              className="object-cover group-hover:scale-110 transition-transform duration-1000"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center"><Package size={32} className="text-zinc-300" /></div>
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/15 to-transparent p-6 flex flex-col justify-end">
            <span
              style={{ textTransform: 'var(--eyebrow-style, uppercase)' }}
              className="font-mono text-[10px] text-white/70 tracking-widest mb-2"
            >
              {[r.formato, r.sello].filter(Boolean).join(' · ')}
            </span>
            <h3 className="font-serif italic text-xl text-white leading-snug mb-1 line-clamp-2">{r.title}</h3>
            <p className="text-white/80 text-sm truncate">{r.artista}</p>
          </div>
        </Link>
      ))}
    </div>
  );
}

// Un disc gran destacat + fins a 4 de més petits al costat.
function FeaturedLarge({ releases }) {
  const [first, ...rest] = releases;
  const side = rest.slice(0, MAX_FEATURED_SIDE);
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
      <Link href={`/disc/${first.id}`} className="group block">
        <div
          style={{ borderRadius: 'var(--radius-card, 24px)', boxShadow: 'var(--shadow-card, 0 10px 40px -10px rgba(0,0,0,0.12))' }}
          className="relative aspect-square overflow-hidden bg-zinc-100 mb-4"
        >
          {first.image_url ? (
            <Image src={first.image_url} alt="" fill sizes="(max-width: 1024px) 100vw, 50vw" className="object-cover hero-featured-image group-hover:scale-105 transition-transform duration-500" />
          ) : (
            <div className="w-full h-full flex items-center justify-center"><Package size={40} className="text-zinc-300" /></div>
          )}
        </div>
        <p className="font-medium text-zinc-900 group-hover:text-zinc-500 transition-colors">{first.artista}</p>
        <p className="font-serif italic text-zinc-500">{first.title}</p>
      </Link>
      {side.length > 0 && (
        <div className="grid grid-cols-2 gap-4 md:gap-6">
          {side.map((r) => (
            <Link key={r.id} href={`/disc/${r.id}`} className="group block">
              <div style={{ borderRadius: 'var(--radius-card, 16px)' }} className="relative aspect-square overflow-hidden bg-zinc-100 mb-2">
                {r.image_url ? (
                  <Image src={r.image_url} alt="" fill sizes="25vw" className="object-cover hero-featured-image group-hover:scale-105 transition-transform duration-500" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center"><Package size={20} className="text-zinc-300" /></div>
                )}
              </div>
              <p className="text-sm font-medium text-zinc-900 truncate">{r.artista}</p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

// Llista vertical, una fila per disc — portada petita a l'esquerra.
function ListRows({ releases }) {
  return (
    <div className="divide-y divide-zinc-200 border-t border-b border-zinc-200">
      {releases.map((r) => {
        const minPrice = minPriceOf(r);
        return (
          <Link key={r.id} href={`/disc/${r.id}`} className="flex items-center gap-4 py-4 group">
            <div style={{ borderRadius: 'var(--radius-card, 12px)' }} className="relative w-16 h-16 shrink-0 overflow-hidden bg-zinc-100">
              {r.image_url ? (
                <Image src={r.image_url} alt="" fill sizes="64px" className="object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center"><Package size={16} className="text-zinc-300" /></div>
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-medium text-zinc-900 truncate group-hover:text-zinc-500 transition-colors">{r.artista}</p>
              <p className="font-serif italic text-sm text-zinc-500 truncate">{r.title}</p>
            </div>
            {minPrice !== null && <span className="text-sm font-semibold text-zinc-900 shrink-0">{minPrice.toFixed(2)} €</span>}
          </Link>
        );
      })}
    </div>
  );
}

// Igual que "classic" però sense preu/format/segell — només imatge, artista
// i títol, més editorial.
function MinimalTrack({ releases }) {
  return (
    <div className="flex gap-4 md:gap-6 overflow-x-auto snap-x snap-mandatory scroll-smooth pb-2 -mx-1 px-1 [&::-webkit-scrollbar]:hidden [scrollbar-width:none]">
      {releases.map((r) => (
        <Link key={r.id} href={`/disc/${r.id}`} className="w-[42%] sm:w-[30%] md:w-[22%] shrink-0 snap-start group block">
          <div style={{ borderRadius: 'var(--radius-card, 24px)' }} className="relative aspect-square overflow-hidden bg-zinc-100 mb-4">
            {r.image_url ? (
              <Image
                src={r.image_url}
                alt=""
                fill
                sizes="(max-width: 640px) 42vw, 22vw"
                style={{ filter: 'var(--image-treatment, none)' }}
                className="object-cover group-hover:scale-105 transition-transform duration-500"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center"><Package size={28} className="text-zinc-300" /></div>
            )}
          </div>
          <p className="font-medium text-sm text-zinc-900 truncate group-hover:text-zinc-500 transition-colors">{r.artista}</p>
          <p className="font-serif italic text-sm text-zinc-500 truncate">{r.title}</p>
        </Link>
      ))}
    </div>
  );
}

// Les targetes clàssiques del catàleg, en graella fixa sense scroll.
function StaticGrid({ releases }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-6 md:gap-8">
      {releases.map((r) => <ReleaseCard key={r.id} release={r} />)}
    </div>
  );
}

// Com "classic" però amb el preu destacat sobre la imatge.
function OfertaTrack({ releases }) {
  return (
    <div className="flex gap-4 md:gap-6 overflow-x-auto snap-x snap-mandatory scroll-smooth pb-2 -mx-1 px-1 [&::-webkit-scrollbar]:hidden [scrollbar-width:none]">
      {releases.map((r) => {
        const minPrice = minPriceOf(r);
        return (
          <Link key={r.id} href={`/disc/${r.id}`} className="w-[42%] sm:w-[30%] md:w-[22%] shrink-0 snap-start group block">
            <div style={{ borderRadius: 'var(--radius-card, 24px)' }} className="relative aspect-square overflow-hidden bg-zinc-100 mb-4">
              {r.image_url ? (
                <Image src={r.image_url} alt="" fill sizes="(max-width: 640px) 42vw, 22vw" className="object-cover group-hover:scale-105 transition-transform duration-500" />
              ) : (
                <div className="w-full h-full flex items-center justify-center"><Package size={28} className="text-zinc-300" /></div>
              )}
              {minPrice !== null && (
                <span
                  style={{ borderRadius: 'var(--radius-button, 9999px)' }}
                  className="absolute bottom-3 left-3 bg-primary text-white text-sm font-bold px-3 py-1.5 shadow-lg"
                >
                  {minPrice.toFixed(2)} €
                </span>
              )}
            </div>
            <p className="font-medium text-sm text-zinc-900 truncate">{r.artista}</p>
            <p className="font-serif italic text-sm text-zinc-500 truncate">{r.title}</p>
          </Link>
        );
      })}
    </div>
  );
}
