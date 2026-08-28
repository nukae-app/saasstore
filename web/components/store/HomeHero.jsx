import { getTranslations } from 'next-intl/server';
import { Link } from '../../i18n/navigation';
import Image from 'next/image';
import { Package } from 'lucide-react';
import { backgroundStyle } from './blocks/backgroundStyle';

// Layouts que ja existien abans de les 10 disposicions (o que hi són molt
// a prop) — hi apliquem el mateix color/imatge de fons clàssic que ja
// tenien tots (BackgroundProps), perquè un tenant que ja l'hagués triat amb
// el layout per defecte no perdi res en canviar aquest component. "no_image"
// en queda fora a propòsit: és l'opció deliberadament plana/neutra (ver
// HeroPropsForm.jsx, que per això no li mostra el selector de fons), no ha
// d'heretar un color/imatge que l'admin hagi deixat d'una altra disposició.
const GENERIC_BACKGROUND_LAYOUTS = new Set(['image_right', 'image_left', 'dual_featured', 'mosaic']);

// Bloc "hero" del constructor de home (ver api/app/blocks/registry.py::HeroProps
// ::HERO_LAYOUTS per a les 10 disposicions). `featured`/`featured2`/
// `mosaicReleases`/`config` segueixen sent dades en viu (catàleg/config del
// tenant), les resol [locale]/page.jsx a cada request — mai props d'admin.
export default async function HomeHero({
  id, layout = 'image_right', eyebrow, title, subtitle, cta_label, cta_href = '/cataleg',
  featured, featured2, mosaicReleases = [], config,
  featured_label, background_color, background_image_url, background_video_url, text_align,
}) {
  const t = await getTranslations('home');
  const dark = layout === 'background_center' || layout === 'background_left' || layout === 'background_video';
  const align = layout === 'background_center' || layout === 'solid_color' || layout === 'no_image' || layout === 'logo_tagline'
    ? 'center' : 'left';

  const textContent = (
    <TextContent eyebrow={eyebrow} title={title} subtitle={subtitle} align={align} dark={dark} />
  );
  const ctaButtons = (
    <CtaButtons cta_href={cta_href} cta_label={cta_label} t={t} dark={dark} align={align} />
  );

  // background_video és l'únic layout amb alineació triable per l'admin
  // (centre/esquerra/dreta, ver HeroPropsForm.jsx) — la resta de layouts ja
  // porten la seva alineació fixada pel propi disseny.
  const videoAlign = text_align === 'left' || text_align === 'right' ? text_align : 'center';
  const videoTextContent = (
    <TextContent eyebrow={eyebrow} title={title} subtitle={subtitle} align={videoAlign} dark />
  );
  const videoCtaButtons = (
    <CtaButtons cta_href={cta_href} cta_label={cta_label} t={t} dark align={videoAlign} />
  );

  let body;
  switch (layout) {
    case 'image_left':
      body = (
        <div className="max-w-[var(--content-width,1280px)] mx-auto w-full grid grid-cols-1 lg:grid-cols-2 items-center gap-16 lg:gap-20 py-12">
          <div className="hidden lg:flex justify-start relative lg:order-1">
            <FeaturedCard featured={featured} label={featured_label} t={t} corner="right" />
          </div>
          <div className="space-y-10 lg:order-2">
            {textContent}
            {ctaButtons}
          </div>
        </div>
      );
      break;

    case 'dual_featured':
      body = (
        <div className="max-w-[var(--content-width,1280px)] mx-auto w-full grid grid-cols-1 lg:grid-cols-2 items-center gap-16 lg:gap-20 py-12">
          <div className="space-y-10">
            {textContent}
            {ctaButtons}
          </div>
          <div className="hidden lg:flex justify-end gap-5">
            <DualCard release={featured} />
            <DualCard release={featured2} className="mt-10" />
          </div>
        </div>
      );
      break;

    case 'mosaic':
      body = (
        <div className="max-w-[var(--content-width,1280px)] mx-auto w-full grid grid-cols-1 lg:grid-cols-2 items-center gap-16 lg:gap-20 py-12">
          <div className="space-y-10">
            {textContent}
            {ctaButtons}
          </div>
          <div className="hidden lg:block">
            <MosaicGrid releases={mosaicReleases} />
          </div>
        </div>
      );
      break;

    case 'background_center':
    case 'background_left':
      body = (
        <>
          <div
            className="absolute inset-0"
            style={{
              backgroundImage: background_image_url ? `url(${background_image_url})` : undefined,
              backgroundSize: 'cover',
              backgroundPosition: 'center',
            }}
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/35 to-black/45" />
          <div className={`relative z-10 max-w-[var(--content-width,1280px)] mx-auto w-full py-12 ${layout === 'background_center' ? 'text-center' : ''}`}>
            <div className={`space-y-10 ${layout === 'background_center' ? 'mx-auto max-w-2xl flex flex-col items-center' : 'max-w-xl'}`}>
              {textContent}
              {ctaButtons}
            </div>
          </div>
        </>
      );
      break;

    case 'background_video':
      body = (
        <>
          {background_video_url && (
            <video
              autoPlay
              muted
              loop
              playsInline
              className="absolute inset-0 w-full h-full object-cover"
            >
              <source src={background_video_url} />
            </video>
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/35 to-black/45" />
          <div className="relative z-10 max-w-[var(--content-width,1280px)] mx-auto w-full py-12">
            <div
              className={`space-y-10 max-w-2xl flex flex-col ${
                videoAlign === 'left' ? 'items-start' : videoAlign === 'right' ? 'items-end ml-auto' : 'items-center mx-auto'
              }`}
            >
              {videoTextContent}
              {videoCtaButtons}
            </div>
          </div>
        </>
      );
      break;

    case 'solid_color':
      body = (
        <div className="relative z-10 max-w-[var(--content-width,1280px)] mx-auto w-full py-12 text-center">
          <div className="space-y-10 mx-auto max-w-2xl flex flex-col items-center">
            {textContent}
            {ctaButtons}
          </div>
        </div>
      );
      break;

    case 'no_image':
      body = (
        <div className="max-w-[var(--content-width,1280px)] mx-auto w-full py-12 text-center">
          <div className="space-y-10 mx-auto max-w-2xl flex flex-col items-center">
            {textContent}
            {ctaButtons}
          </div>
        </div>
      );
      break;

    case 'logo_tagline':
      body = (
        <div className="max-w-[var(--content-width,1280px)] mx-auto w-full py-12 text-center">
          <div className="space-y-10 mx-auto max-w-2xl flex flex-col items-center">
            {config?.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={config.logo_url} alt={config?.nombre || ''} className="h-16 md:h-24 w-auto object-contain" />
            ) : (
              <p className="font-serif italic text-3xl text-zinc-900">{config?.nombre || ''}</p>
            )}
            {textContent}
            {ctaButtons}
          </div>
        </div>
      );
      break;

    case 'image_right':
    default:
      body = (
        <div className="max-w-[var(--content-width,1280px)] mx-auto w-full grid grid-cols-1 lg:grid-cols-2 items-center gap-16 lg:gap-20 py-12">
          <div className="space-y-10">
            {textContent}
            {ctaButtons}
          </div>
          <div className="hidden lg:flex justify-end relative">
            <FeaturedCard featured={featured} label={featured_label} t={t} corner="left" />
          </div>
        </div>
      );
  }

  const sectionStyle = GENERIC_BACKGROUND_LAYOUTS.has(layout)
    ? backgroundStyle(background_color, background_image_url)
    : layout === 'solid_color'
      ? { backgroundColor: background_color || 'var(--accent, #f2f2f2)' }
      : undefined;

  return (
    <section
      data-block-id={id}
      style={sectionStyle}
      className="relative min-h-[70vh] flex items-center px-5 md:px-16 mb-16 md:mb-24 overflow-hidden"
    >
      {body}
    </section>
  );
}

function TextContent({ eyebrow, title, subtitle, align, dark }) {
  const textAlignClass = align === 'center' ? 'text-center' : align === 'right' ? 'text-right' : '';
  const boxAlignClass = align === 'center' ? 'mx-auto' : align === 'right' ? 'ml-auto max-w-xl' : 'max-w-xl';
  const subtitleAlignClass = align === 'center' ? 'mx-auto max-w-md' : align === 'right' ? 'ml-auto max-w-md' : 'max-w-md';
  return (
    <div className={`space-y-4 ${textAlignClass}`}>
      {eyebrow && (
        <span
          data-field="eyebrow"
          style={{ textTransform: 'var(--eyebrow-style, uppercase)' }}
          className={`font-mono text-xs uppercase tracking-[0.3em] block ${dark ? 'text-white/70' : 'text-zinc-500'}`}
        >
          {eyebrow}
        </span>
      )}
      <h1
        data-field="title"
        className={`font-serif text-5xl md:text-7xl leading-[1.1] ${boxAlignClass} ${dark ? 'text-white' : 'text-zinc-900'}`}
      >
        {title}
      </h1>
      {subtitle && (
        <p
          data-field="subtitle"
          className={`text-lg leading-relaxed ${subtitleAlignClass} ${dark ? 'text-white/80' : 'text-zinc-500'}`}
        >
          {subtitle}
        </p>
      )}
    </div>
  );
}

function CtaButtons({ cta_href, cta_label, t, dark, align }) {
  const justifyClass = align === 'center' ? 'justify-center' : align === 'right' ? 'justify-end' : '';
  return (
    <div className={`flex flex-wrap gap-5 ${justifyClass}`}>
      <Link
        href={cta_href}
        data-field="cta_href"
        data-attr="href"
        style={{ borderRadius: 'var(--radius-button, 9999px)' }}
        className={`px-12 py-5 font-medium uppercase tracking-widest text-sm transition-all active:scale-95 shadow-xl shadow-black/5 ${
          dark ? 'bg-white text-zinc-900 hover:opacity-90' : 'bg-primary text-white hover:opacity-90'
        }`}
      >
        <span data-field="cta_label">{cta_label || t('explore')}</span>
      </Link>
      <Link
        href="/carret"
        style={{ borderRadius: 'var(--radius-button, 9999px)' }}
        className={`px-12 py-5 font-medium uppercase tracking-widest text-sm transition-all active:scale-95 ${
          dark ? 'bg-white/10 border border-white/40 text-white hover:bg-white/20' : 'bg-white border border-zinc-200 text-zinc-900 hover:bg-zinc-50'
        }`}
      >
        {t('myCart')}
      </Link>
    </div>
  );
}

// Targeta de producte destacat + placa flotant amb `label` (per defecte
// "Ara sona", sobreescrivible amb `featured_label` per a verticals que no
// són discos) — reutilitzada per image_right/image_left.
function FeaturedCard({ featured, label, t, corner }) {
  if (!featured) return null;
  const cornerClass = corner === 'left' ? '-bottom-10 -left-16' : '-bottom-10 -right-16';
  const glowClass = corner === 'left' ? '-top-10 -right-10' : '-top-10 -left-10';
  return (
    <div className="relative group">
      <div
        style={{
          borderRadius: 'var(--radius-card, 32px)',
          boxShadow: 'var(--shadow-card, 0 25px 50px -12px rgba(0,0,0,0.25))',
        }}
        className="overflow-hidden relative z-10 w-[420px] h-[500px] bg-zinc-100"
      >
        {featured.image_url ? (
          <Image
            src={featured.image_url}
            alt={`${featured.artista} — ${featured.title}`}
            fill
            sizes="420px"
            priority
            className="object-cover hero-featured-image transition-all duration-700"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Package size={40} className="text-zinc-300" />
          </div>
        )}
      </div>

      <div
        style={{
          borderRadius: 'var(--radius-card, 24px)',
          boxShadow: 'var(--shadow-card, 0 10px 40px -10px rgba(0,0,0,0.15))',
          border: 'var(--border-card, 1px solid #f4f4f5)',
        }}
        className={`absolute z-20 bg-white p-8 max-w-xs ${cornerClass}`}
      >
        <div className="flex items-center gap-4 mb-4">
          <div className="w-12 h-12 rounded-full bg-black flex items-center justify-center border-4 border-zinc-100 shrink-0 animate-spin-slow">
            <div className="w-2 h-2 rounded-full bg-white" />
          </div>
          <div className="min-w-0">
            <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-widest">{label || t('nowSpinning')}</p>
            <p className="font-serif text-xl text-zinc-900 leading-none truncate">{featured.title}</p>
          </div>
        </div>
        <p className="text-zinc-500 text-sm italic line-clamp-2">
          {featured.description || `${featured.artista} · ${[featured.formato, featured.sello].filter(Boolean).join(' · ')}`}
        </p>
      </div>

      <div className={`absolute w-64 h-64 bg-zinc-100 rounded-full blur-[80px] -z-10 opacity-60 ${glowClass}`} />
    </div>
  );
}

function DualCard({ release, className = '' }) {
  if (!release) return null;
  return (
    <div className={`relative w-[45%] max-w-[220px] ${className}`}>
      <div
        style={{
          borderRadius: 'var(--radius-card, 24px)',
          boxShadow: 'var(--shadow-card, 0 20px 40px -12px rgba(0,0,0,0.2))',
        }}
        className="overflow-hidden relative aspect-square bg-zinc-100"
      >
        {release.image_url ? (
          <Image
            src={release.image_url}
            alt={`${release.artista} — ${release.title}`}
            fill
            sizes="220px"
            className="object-cover hero-featured-image"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Package size={28} className="text-zinc-300" />
          </div>
        )}
      </div>
      <p className="mt-3 text-sm font-medium text-zinc-900 truncate">{release.artista}</p>
      <p className="font-serif italic text-sm text-zinc-500 truncate">{release.title}</p>
    </div>
  );
}

function MosaicGrid({ releases }) {
  if (!releases || releases.length === 0) return null;
  return (
    <div className="grid grid-cols-3 gap-3 max-w-md ml-auto">
      {releases.slice(0, 6).map((r, i) => (
        <div
          key={r.id}
          style={{ borderRadius: 'var(--radius-card, 16px)' }}
          className={`relative aspect-square overflow-hidden bg-zinc-100 ${i % 3 === 1 ? 'mt-6' : ''}`}
        >
          <Image
            src={r.image_url}
            alt=""
            fill
            sizes="150px"
            className="object-cover hero-featured-image"
          />
        </div>
      ))}
    </div>
  );
}
