import { backgroundStyle } from './backgroundStyle';

// Bloc "testimonials" (ver api/app/blocks/registry.py::TestimonialsProps) —
// llista de cites, tot copy del tenant. A diferència de hero/carousel/text,
// els camps de cada element de la llista no tenen previsualització lletra a
// lletra (caldria un selector per índex); es veuen igualment després de
// guardar, ja que l'admin recarrega l'iframe en desar.
export default function TestimonialsBlock({ id, heading, items = [], background_color, background_image_url }) {
  if (!items || items.length === 0) return null;
  return (
    <section
      data-block-id={id}
      style={backgroundStyle(background_color, background_image_url)}
      className="py-24 md:py-32 px-5 md:px-16 bg-zinc-50"
    >
      <div className="max-w-[var(--content-width,1280px)] mx-auto">
        {heading && (
          <h2 className="font-serif italic text-3xl md:text-4xl text-center mb-16">{heading}</h2>
        )}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {items.map((item, i) => (
            <figure
              key={i}
              style={{
                borderRadius: 'var(--radius-card, 24px)',
                boxShadow: 'var(--shadow-card, 0 2px 24px -6px rgba(15,23,42,0.08))',
                border: 'var(--border-card, none)',
              }}
              className="bg-white p-8"
            >
              <blockquote className="text-zinc-700 leading-relaxed italic">
                “{item.quote}”
              </blockquote>
              {item.author && (
                <figcaption className="mt-4 text-sm text-zinc-400 font-medium">
                  {item.author}
                </figcaption>
              )}
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}
