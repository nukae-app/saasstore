import { Link } from '../../../i18n/navigation';

// Bloc "text" (ver api/app/blocks/registry.py::TextProps) — franja de
// contingut lliure però estructurada: títol + cos + CTA opcional, tot copy
// del tenant, sense dades de catàleg.
export default function TextBlock({ id, heading, body, cta_label, cta_href }) {
  if (!heading && !body) return null;
  return (
    <section data-block-id={id} className="py-24 px-5 md:px-16 bg-white">
      <div className="max-w-2xl mx-auto text-center">
        {heading && (
          <h2 data-field="heading" className="font-serif italic text-3xl md:text-4xl mb-6 text-zinc-900">
            {heading}
          </h2>
        )}
        {body && (
          <p data-field="body" className="text-zinc-500 leading-relaxed whitespace-pre-line">
            {body}
          </p>
        )}
        {cta_label && cta_href && (
          <Link
            href={cta_href}
            data-field="cta_href"
            data-attr="href"
            className="inline-block mt-8 text-xs font-medium text-zinc-900 uppercase tracking-widest hover:tracking-[0.15em] transition-all"
          >
            <span data-field="cta_label">{cta_label}</span>
          </Link>
        )}
      </div>
    </section>
  );
}
