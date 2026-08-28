import { Link } from '../../../i18n/navigation';

// Bloc "gallery" (ver api/app/blocks/registry.py::GalleryProps) — graella
// d'imatges lliures (lookbook, racó de la botiga, esdeveniments...), cadascuna
// amb peu de foto i enllaç opcionals. Tot copy/imatges del tenant, mai dades
// de catàleg. Imatge amb <img> pla, no next/image: els fitxers pujats viuen
// al volum /uploads compartit amb Caddy (ver upload-background al router),
// fora del `public/` de Next — l'optimitzador de next/image només sap
// llegir rutes relatives del seu propi filesystem i respon 400 ("isn't a
// valid image") per a qualsevol altra, mateix motiu pel qual els fons
// (backgroundStyle.js) ja s'apliquen amb CSS `url()` pla, mai amb <Image>.
export default function GalleryBlock({ id, heading, items = [] }) {
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
            className="font-mono text-xs text-zinc-500 text-center tracking-[0.4em] mb-16 md:mb-20"
          >
            {heading}
          </h2>
        )}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-6 md:gap-8">
          {items.map((item, i) => {
            const Wrapper = item.href ? Link : 'div';
            const wrapperProps = item.href ? { href: item.href } : {};
            return (
              <Wrapper
                key={i}
                {...wrapperProps}
                style={{
                  borderRadius: 'var(--radius-card, 24px)',
                  border: 'var(--border-card, none)',
                }}
                className="group relative block aspect-square overflow-hidden bg-zinc-100"
              >
                {item.image_url && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={item.image_url}
                    alt={item.caption || ''}
                    style={{ filter: 'var(--image-treatment, none)' }}
                    className="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-1000"
                  />
                )}
                {item.caption && (
                  <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent p-4 flex items-end">
                    <p className="text-white text-sm font-medium leading-snug">{item.caption}</p>
                  </div>
                )}
              </Wrapper>
            );
          })}
        </div>
      </div>
    </section>
  );
}
