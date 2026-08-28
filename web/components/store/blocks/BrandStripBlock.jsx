import { Link } from '../../../i18n/navigation';

// Bloc "brand_strip" (ver api/app/blocks/registry.py::BrandStripProps) —
// franja de logos (segells, marques amb qui es col·labora...), cadascun amb
// enllaç opcional. <img> pla, no next/image: mateix motiu que
// GalleryBlock.jsx (els fitxers pujats viuen a /uploads, fora del `public/`
// de Next).
export default function BrandStripBlock({ id, heading, items = [] }) {
  if (!items || items.length === 0) return null;

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
        {heading && (
          <h2
            style={{ textTransform: 'var(--eyebrow-style, uppercase)' }}
            className="font-mono text-xs text-zinc-500 text-center tracking-[0.4em] mb-12"
          >
            {heading}
          </h2>
        )}
        <div className="flex flex-wrap items-center justify-center gap-x-12 gap-y-8">
          {items.map((item, i) => {
            const Wrapper = item.href ? Link : 'div';
            const wrapperProps = item.href ? { href: item.href } : {};
            return (
              <Wrapper
                key={i}
                {...wrapperProps}
                className="block h-10 opacity-60 hover:opacity-100 transition-opacity"
              >
                {item.image_url && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={item.image_url} alt="" className="h-full w-auto object-contain grayscale" />
                )}
              </Wrapper>
            );
          })}
        </div>
      </div>
    </section>
  );
}
