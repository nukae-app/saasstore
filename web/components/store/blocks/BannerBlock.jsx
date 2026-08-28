import { Link } from '../../../i18n/navigation';
import { backgroundStyle } from './backgroundStyle';

// Bloc "banner" (ver api/app/blocks/registry.py::BannerProps) — franja
// d'avís curta del tenant (horari especial, despeses d'enviament, tancament
// per vacances...), amb un enllaç opcional. Diferent del banner de
// manteniment fix del checkout (missatge "maintenanceBanner" a messages/*):
// aquest és contingut lliure que decideix el tenant, no un flag de sistema.
export default function BannerBlock({ id, text, cta_label, cta_href, background_color, background_image_url }) {
  if (!text) return null;
  return (
    <section
      data-block-id={id}
      style={{
        ...backgroundStyle(background_color, background_image_url),
        borderTop: 'var(--section-divider, none)',
      }}
      className="px-5 md:px-16 py-4 bg-zinc-100 text-center"
    >
      <p className="text-sm text-zinc-700">
        {text}
        {cta_label && cta_href && (
          <Link href={cta_href} className="ml-2 font-medium text-zinc-900 underline underline-offset-2 hover:no-underline">
            {cta_label}
          </Link>
        )}
      </p>
    </section>
  );
}
