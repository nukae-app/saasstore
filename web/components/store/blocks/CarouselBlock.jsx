import { Link } from '../../../i18n/navigation';
import ReleaseCarousel from '../ReleaseCarousel';

// Bloc "carousel" (ver api/app/blocks/registry.py::CarouselProps) — abans
// era la secció "New arrivals" fixa a [locale]/page.jsx. `heading`/`subtitle`/
// `cta_label` són copy del tenant; `releases` és el catàleg filtrat per
// `props.etiqueta_slug`, el resol page.jsx igual que fetchAllByEtiqueta() ja
// feia abans — mai dades de catàleg dins d'aquest component.
export default function CarouselBlock({ id, heading, subtitle, cta_label, releases = [] }) {
  if (releases.length === 0) return null;
  return (
    <section data-block-id={id} className="py-24 md:py-32 px-5 md:px-16 bg-white">
      <div className="max-w-[1280px] mx-auto">
        <div className="flex justify-between items-baseline mb-12 md:mb-16">
          <div>
            {heading && <h2 data-field="heading" className="font-serif italic text-3xl md:text-4xl">{heading}</h2>}
            {subtitle && <p data-field="subtitle" className="text-zinc-500 mt-2">{subtitle}</p>}
          </div>
          {cta_label && (
            <Link
              href="/cataleg"
              className="hidden sm:block text-xs font-medium text-zinc-900 uppercase tracking-widest hover:tracking-[0.15em] transition-all"
            >
              <span data-field="cta_label">{cta_label}</span>
            </Link>
          )}
        </div>
        <ReleaseCarousel releases={releases} />
      </div>
    </section>
  );
}
