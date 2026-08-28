import { getTranslations } from 'next-intl/server';
import { Link } from '../../i18n/navigation';
import Image from 'next/image';

// Bloc "hero" del constructor de home (ver api/app/blocks/registry.py::HeroProps)
// — eyebrow/title/subtitle/cta_label són copy que decideix el tenant des de
// l'admin, ja no una branca isVinils dins del component (aquesta lògica va
// passar a ser el valor per defecte que es sembra en crear el tenant, ver
// blocks/provisioning.py). `featured` segueix sent dada de catàleg en viu,
// la resol [locale]/page.jsx a cada request.
export default async function HomeHero({ id, eyebrow, title, subtitle, cta_label, cta_href = '/cataleg', featured }) {
  const t = await getTranslations('home');
  return (
    <section data-block-id={id} className="relative min-h-[70vh] flex items-center px-5 md:px-16 mb-16 md:mb-24">
      <div className="max-w-[1280px] mx-auto w-full grid grid-cols-1 lg:grid-cols-2 items-center gap-16 lg:gap-20 py-12">
        <div className="space-y-10">
          <div className="space-y-4">
            {eyebrow && (
              <span data-field="eyebrow" className="font-mono text-xs text-zinc-500 uppercase tracking-[0.3em] block">
                {eyebrow}
              </span>
            )}
            <h1 data-field="title" className="font-serif text-5xl md:text-7xl leading-[1.1] text-zinc-900 max-w-xl">
              {title}
            </h1>
            {subtitle && (
              <p data-field="subtitle" className="text-lg text-zinc-500 max-w-md leading-relaxed">
                {subtitle}
              </p>
            )}
          </div>
          <div className="flex flex-wrap gap-5">
            <Link
              href={cta_href}
              data-field="cta_href"
              data-attr="href"
              className="bg-primary text-white px-12 py-5 rounded-full font-medium uppercase tracking-widest text-sm hover:opacity-90 transition-all active:scale-95 shadow-xl shadow-black/5"
            >
              <span data-field="cta_label">{cta_label || t('explore')}</span>
            </Link>
            <Link
              href="/carret"
              className="bg-white border border-zinc-200 text-zinc-900 px-12 py-5 rounded-full font-medium uppercase tracking-widest text-sm hover:bg-zinc-50 transition-all active:scale-95"
            >
              {t('myCart')}
            </Link>
          </div>
        </div>

        {featured && (
          <div className="hidden lg:flex justify-end relative">
            <div className="relative group">
              <div className="rounded-[32px] overflow-hidden shadow-2xl shadow-black/10 relative z-10 w-[420px] h-[500px] bg-zinc-100">
                {featured.image_url ? (
                  <Image
                    src={featured.image_url}
                    alt={`${featured.artista} — ${featured.title}`}
                    fill
                    sizes="420px"
                    priority
                    className="object-cover grayscale-[15%] group-hover:grayscale-0 transition-all duration-700"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <svg viewBox="0 0 100 100" className="w-24 h-24 text-zinc-300" fill="currentColor">
                      <circle cx="50" cy="50" r="48" />
                      <circle cx="50" cy="50" r="34" fill="#fbf9f4" />
                      <circle cx="50" cy="50" r="14" />
                      <circle cx="50" cy="50" r="4" fill="#fbf9f4" />
                    </svg>
                  </div>
                )}
              </div>

              {/* Floating "Now Spinning" card */}
              <div className="absolute -bottom-10 -left-16 z-20 bg-white rounded-3xl shadow-[0_10px_40px_-10px_rgba(0,0,0,0.15)] p-8 border border-zinc-100 max-w-xs">
                <div className="flex items-center gap-4 mb-4">
                  <div className="w-12 h-12 rounded-full bg-black flex items-center justify-center border-4 border-zinc-100 shrink-0 animate-spin-slow">
                    <div className="w-2 h-2 rounded-full bg-white" />
                  </div>
                  <div className="min-w-0">
                    <p className="font-mono text-[10px] text-zinc-500 uppercase tracking-widest">{t('nowSpinning')}</p>
                    <p className="font-serif text-xl text-zinc-900 leading-none truncate">{featured.title}</p>
                  </div>
                </div>
                <p className="text-zinc-500 text-sm italic line-clamp-2">
                  {featured.description || `${featured.artista} · ${[featured.formato, featured.sello].filter(Boolean).join(' · ')}`}
                </p>
              </div>

              {/* Decorative soft glow */}
              <div className="absolute -top-10 -right-10 w-64 h-64 bg-zinc-100 rounded-full blur-[80px] -z-10 opacity-60" />
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
