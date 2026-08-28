import { videoEmbedUrl } from './videoEmbedUrl';

// Bloc "video" (ver api/app/blocks/registry.py::VideoProps) — un vídeo
// destacat (YouTube/Vimeo) incrustat en 16:9. Si `video_url` no és una URL
// reconeguda, no es renderitza res en lloc de trencar l'embed.
export default function VideoBlock({ id, heading, subtitle, video_url }) {
  const embedUrl = videoEmbedUrl(video_url);
  if (!embedUrl) return null;

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
      <div className="max-w-3xl mx-auto">
        {(heading || subtitle) && (
          <div className="text-center mb-10 md:mb-12">
            {heading && <h2 className="font-serif italic text-3xl md:text-4xl mb-3">{heading}</h2>}
            {subtitle && <p className="text-zinc-500">{subtitle}</p>}
          </div>
        )}
        <div
          style={{ borderRadius: 'var(--radius-card, 24px)' }}
          className="relative aspect-video overflow-hidden bg-zinc-100"
        >
          <iframe
            src={embedUrl}
            title={heading || 'Vídeo'}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            className="absolute inset-0 w-full h-full border-0"
          />
        </div>
      </div>
    </section>
  );
}
