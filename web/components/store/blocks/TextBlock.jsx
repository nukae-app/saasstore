import { Link } from '../../../i18n/navigation';
import { Check, Package } from 'lucide-react';
import { backgroundStyle } from './backgroundStyle';
import { videoEmbedUrl } from './videoEmbedUrl';

// Layouts que ja tenien el fons clàssic (BackgroundProps + backgroundStyle,
// overlay clar) abans de les 10 disposicions — "background_image" té el seu
// propi tractament (fons a pantalla completa amb degradat fosc, ver el
// switch de sota) i "two_columns_image" fa servir la mateixa imatge com a
// il·lustració real al costat del text, no com a fons de la secció.
const GENERIC_BACKGROUND_LAYOUTS = new Set([
  'centered', 'full_width', 'two_columns_video', 'stats',
  'pull_quote', 'checklist', 'cta_banner', 'editorial_dropcap',
]);

// Bloc "text" (ver api/app/blocks/registry.py::TextProps::TEXT_LAYOUTS per
// a les 10 disposicions) — franja de contingut lliure però estructurada:
// títol + cos + CTA opcional, tot copy del tenant, sense dades de catàleg.
export default function TextBlock({
  id, layout = 'centered', heading, body, cta_label, cta_href,
  video_url, stats = [], background_color, background_image_url,
}) {
  if (!heading && !body) return null;

  const sectionStyle = GENERIC_BACKGROUND_LAYOUTS.has(layout)
    ? {
        ...backgroundStyle(background_color, background_image_url),
        paddingTop: 'var(--spacing-density)',
        paddingBottom: 'var(--spacing-density)',
        borderTop: 'var(--section-divider, none)',
      }
    : {
        paddingTop: layout === 'background_image' ? undefined : 'var(--spacing-density)',
        paddingBottom: layout === 'background_image' ? undefined : 'var(--spacing-density)',
        borderTop: 'var(--section-divider, none)',
      };

  let body_jsx;
  switch (layout) {
    case 'two_columns_image':
      body_jsx = (
        <div className="max-w-[var(--content-width,1280px)] mx-auto grid grid-cols-1 lg:grid-cols-2 items-center gap-12 lg:gap-16">
          <div>
            <TextContent heading={heading} body={body} ctaLabel={cta_label} ctaHref={cta_href} align="left" />
          </div>
          <div style={{ borderRadius: 'var(--radius-card, 24px)' }} className="relative aspect-[4/3] overflow-hidden bg-zinc-100">
            {background_image_url ? (
              <img src={background_image_url} alt="" className="absolute inset-0 w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center"><Package size={40} className="text-zinc-300" /></div>
            )}
          </div>
        </div>
      );
      break;

    case 'two_columns_video': {
      const embedUrl = videoEmbedUrl(video_url);
      body_jsx = (
        <div className="max-w-[var(--content-width,1280px)] mx-auto grid grid-cols-1 lg:grid-cols-2 items-center gap-12 lg:gap-16">
          <div>
            <TextContent heading={heading} body={body} ctaLabel={cta_label} ctaHref={cta_href} align="left" />
          </div>
          {embedUrl ? (
            <div style={{ borderRadius: 'var(--radius-card, 24px)' }} className="relative aspect-video overflow-hidden bg-zinc-100">
              <iframe
                src={embedUrl}
                title={heading || 'Vídeo'}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
                className="absolute inset-0 w-full h-full border-0"
              />
            </div>
          ) : <div />}
        </div>
      );
      break;
    }

    case 'background_image':
      body_jsx = (
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
          <div
            style={{ paddingTop: 'var(--spacing-density)', paddingBottom: 'var(--spacing-density)' }}
            className="relative z-10 max-w-2xl mx-auto text-center"
          >
            <TextContent heading={heading} body={body} ctaLabel={cta_label} ctaHref={cta_href} align="center" dark />
          </div>
        </>
      );
      break;

    case 'stats':
      body_jsx = (
        <div className="max-w-3xl mx-auto text-center">
          <TextContent heading={heading} body={body} ctaLabel={cta_label} ctaHref={cta_href} align="center" />
          {stats.length > 0 && (
            <div className="mt-12 grid grid-cols-1 sm:grid-cols-3 gap-8">
              {stats.map((s, i) => (
                <div key={i}>
                  <p className="font-serif italic text-4xl md:text-5xl text-zinc-900">{s.value}</p>
                  <p
                    style={{ textTransform: 'var(--eyebrow-style, uppercase)' }}
                    className="mt-2 font-mono text-xs text-zinc-500 tracking-widest"
                  >
                    {s.label}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      );
      break;

    case 'pull_quote':
      body_jsx = (
        <div className="max-w-2xl mx-auto text-center">
          {body && (
            <p data-field="body" className="font-serif italic text-3xl md:text-4xl leading-snug text-zinc-900">
              “{body}”
            </p>
          )}
          {heading && (
            <p
              data-field="heading"
              style={{ textTransform: 'var(--eyebrow-style, uppercase)' }}
              className="mt-6 font-mono text-xs text-zinc-500 tracking-widest"
            >
              {heading}
            </p>
          )}
        </div>
      );
      break;

    case 'checklist': {
      const items = (body || '').split('\n').map((s) => s.trim()).filter(Boolean);
      body_jsx = (
        <div className="max-w-2xl mx-auto">
          {heading && <h2 data-field="heading" className="font-serif italic text-3xl md:text-4xl mb-6 text-zinc-900 text-center">{heading}</h2>}
          <ul className="space-y-3" data-field="body">
            {items.map((line, i) => (
              <li key={i} className="flex items-start gap-3">
                <Check size={18} className="text-zinc-900 shrink-0 mt-0.5" />
                <span className="text-zinc-500 leading-relaxed">{line}</span>
              </li>
            ))}
          </ul>
          {cta_label && cta_href && (
            <Link
              href={cta_href}
              style={{ textTransform: 'var(--eyebrow-style, uppercase)' }}
              className="inline-block mt-8 text-xs font-medium text-zinc-900 uppercase tracking-widest hover:tracking-[0.15em] transition-all"
            >
              {cta_label}
            </Link>
          )}
        </div>
      );
      break;
    }

    case 'cta_banner':
      body_jsx = (
        <div className="max-w-xl mx-auto text-center">
          {heading && <h2 data-field="heading" className="font-serif italic text-2xl md:text-3xl mb-6 text-zinc-900">{heading}</h2>}
          {body && <p data-field="body" className="text-zinc-500 leading-relaxed mb-8 whitespace-pre-line">{body}</p>}
          {cta_label && cta_href && (
            <Link
              href={cta_href}
              data-field="cta_href"
              data-attr="href"
              style={{ borderRadius: 'var(--radius-button, 9999px)' }}
              className="inline-block bg-primary text-white px-12 py-5 font-medium uppercase tracking-widest text-sm hover:opacity-90 transition-all active:scale-95 shadow-xl shadow-black/5"
            >
              <span data-field="cta_label">{cta_label}</span>
            </Link>
          )}
        </div>
      );
      break;

    case 'editorial_dropcap':
      body_jsx = (
        <div className="max-w-xl mx-auto">
          {heading && <h2 data-field="heading" className="font-serif italic text-3xl md:text-4xl mb-6 text-zinc-900">{heading}</h2>}
          {body && (
            <p
              data-field="body"
              className="text-zinc-500 leading-relaxed whitespace-pre-line first-letter:font-serif first-letter:not-italic first-letter:text-6xl first-letter:text-zinc-900 first-letter:float-left first-letter:leading-[0.8] first-letter:mr-3 first-letter:mt-1"
            >
              {body}
            </p>
          )}
        </div>
      );
      break;

    case 'full_width':
      body_jsx = (
        <div className="max-w-[var(--content-width,1280px)] mx-auto text-center">
          <TextContent heading={heading} body={body} ctaLabel={cta_label} ctaHref={cta_href} align="center" wide />
        </div>
      );
      break;

    case 'centered':
    default:
      body_jsx = (
        <div className="max-w-2xl mx-auto text-center">
          <TextContent heading={heading} body={body} ctaLabel={cta_label} ctaHref={cta_href} align="center" />
        </div>
      );
  }

  return (
    <section
      data-block-id={id}
      style={sectionStyle}
      className={`px-5 md:px-16 bg-white ${layout === 'background_image' ? 'relative overflow-hidden min-h-[50vh] flex items-center' : ''}`}
    >
      {body_jsx}
    </section>
  );
}

function TextContent({ heading, body, ctaLabel, ctaHref, align, dark, wide }) {
  return (
    <>
      {heading && (
        <h2
          data-field="heading"
          className={`font-serif italic mb-6 ${wide ? 'text-4xl md:text-5xl' : 'text-3xl md:text-4xl'} ${dark ? 'text-white' : 'text-zinc-900'}`}
        >
          {heading}
        </h2>
      )}
      {body && (
        <p
          data-field="body"
          className={`leading-relaxed whitespace-pre-line ${dark ? 'text-white/80' : 'text-zinc-500'}`}
        >
          {body}
        </p>
      )}
      {ctaLabel && ctaHref && (
        <Link
          href={ctaHref}
          data-field="cta_href"
          data-attr="href"
          style={{ textTransform: 'var(--eyebrow-style, uppercase)' }}
          className={`inline-block mt-8 text-xs font-medium uppercase tracking-widest hover:tracking-[0.15em] transition-all ${dark ? 'text-white' : 'text-zinc-900'}`}
        >
          <span data-field="cta_label">{ctaLabel}</span>
        </Link>
      )}
    </>
  );
}
