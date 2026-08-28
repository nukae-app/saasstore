'use client';

import { videoEmbedUrl } from './videoEmbedUrl';

// Formulari de props del bloc "video" — camps 1:1 amb
// api/app/blocks/registry.py::VideoProps.
export default function VideoPropsForm({ props, onChange, onFieldChange }) {
  function set(field, value) {
    onChange({ ...props, [field]: value });
    onFieldChange?.(field, value);
  }

  const url = props.video_url || '';
  const recognized = url ? !!videoEmbedUrl(url) : true;

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-xs font-medium text-zinc-600 mb-1">Enllaç del vídeo</label>
        <input
          value={url}
          onChange={(e) => set('video_url', e.target.value)}
          placeholder="https://www.youtube.com/watch?v=..."
          className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
        />
        <p className={`text-xs mt-1 ${recognized ? 'text-zinc-400' : 'text-red-600'}`}>
          {recognized ? 'Enganxa l’enllaç normal de YouTube o Vimeo.' : 'No reconegut: comprova que sigui un enllaç de YouTube o Vimeo.'}
        </p>
      </div>
      <div>
        <label className="block text-xs font-medium text-zinc-600 mb-1">Títol (opcional)</label>
        <input
          value={props.heading || ''}
          onChange={(e) => set('heading', e.target.value)}
          placeholder="Un tastet de la botiga"
          className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-zinc-600 mb-1">Subtítol (opcional)</label>
        <input
          value={props.subtitle || ''}
          onChange={(e) => set('subtitle', e.target.value)}
          placeholder="Un recorregut per la tenda"
          className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
        />
      </div>
    </div>
  );
}
