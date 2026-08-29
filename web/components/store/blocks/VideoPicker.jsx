'use client';

import { useState } from 'react';
import { Film, Trash2, Upload } from 'lucide-react';
import { authFetch } from '../../../app/lib/auth';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import VideoTrimmer from './VideoTrimmer';

function formatSize(bytes) {
  if (!bytes) return '';
  const mb = bytes / (1024 * 1024);
  return `${mb.toFixed(1)} MB`;
}

// Mini gestor de contingut per a vídeos de fons (avui només Hero
// background_video, ver api/app/blocks/registry.py::HeroProps) — puja un
// vídeo nou (POST /admin/home-blocks/upload-video) o el tria d'una petita
// biblioteca amb els vídeos ja pujats abans (GET .../videos), perquè no
// calgui tornar a pujar el mateix fitxer cada cop que es reutilitza.
export default function VideoPicker({ value, onChange }) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [videos, setVideos] = useState(null);
  const [videosError, setVideosError] = useState('');
  const [pendingFile, setPendingFile] = useState(null);

  function pickFile(e) {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setError('');
    setPendingFile(file);
  }

  function cancelTrim() {
    setPendingFile(null);
    setError('');
  }

  async function uploadTrimmed(start, end) {
    setUploading(true);
    setError('');
    try {
      const fd = new FormData();
      fd.append('file', pendingFile);
      fd.append('start', String(start));
      fd.append('end', String(end));
      const r = await authFetch('/admin/home-blocks/upload-video', { method: 'POST', body: fd });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        setError(body.detail || "No s'ha pogut pujar el vídeo.");
        return;
      }
      const video = await r.json();
      onChange(video.url);
      setVideos((prev) => (prev ? [video, ...prev] : prev));
      setPendingFile(null);
    } finally {
      setUploading(false);
    }
  }

  async function openLibrary() {
    setLibraryOpen(true);
    if (videos !== null) return;
    setVideosError('');
    try {
      const r = await authFetch('/admin/home-blocks/videos');
      if (!r.ok) throw new Error();
      setVideos(await r.json());
    } catch {
      setVideos([]);
      setVideosError('No s\'ha pogut carregar la biblioteca de vídeos.');
    }
  }

  function selectVideo(video) {
    onChange(video.url);
    setLibraryOpen(false);
  }

  async function deleteVideo(video, e) {
    e.stopPropagation();
    if (!confirm(`Eliminar "${video.filename}"? Deixarà de funcionar allà on s'estigui fent servir.`)) return;
    const r = await authFetch(`/admin/home-blocks/videos/${video.id}`, { method: 'DELETE' });
    if (r.ok || r.status === 404) {
      setVideos((prev) => (prev || []).filter((v) => v.id !== video.id));
    }
  }

  if (pendingFile) {
    return (
      <VideoTrimmer
        file={pendingFile}
        onCancel={cancelTrim}
        onConfirm={uploadTrimmed}
        uploading={uploading}
        error={error}
      />
    );
  }

  return (
    <div className="space-y-2">
      {value && (
        <video src={value} muted loop playsInline className="w-full aspect-video rounded-xl border border-zinc-200 object-cover bg-zinc-100" />
      )}

      <div className="flex items-center gap-2">
        <label className="flex items-center gap-1.5 text-xs font-medium text-zinc-700 border border-zinc-200 rounded-xl px-3 py-2 cursor-pointer hover:bg-zinc-50 transition-colors">
          <Upload size={14} />
          {value ? 'Pujar un altre' : 'Pujar vídeo'}
          <input type="file" accept=".mp4,.webm,.mov,.mkv,.avi" className="hidden" onChange={pickFile} />
        </label>
        {value && (
          <button
            type="button"
            onClick={() => onChange(null)}
            className="text-xs text-zinc-400 hover:text-red-500 transition-colors"
          >
            Treure
          </button>
        )}
        <button
          type="button"
          onClick={openLibrary}
          className="flex items-center gap-1.5 text-xs font-medium text-zinc-700 border border-zinc-200 rounded-xl px-3 py-2 hover:bg-zinc-50 transition-colors"
        >
          <Film size={14} />
          Biblioteca de vídeos
        </button>
      </div>
      <p className="text-xs text-zinc-400">En pujar-lo podràs triar quin tram (fins a 50s) es comprimeix (sense so, pes final ~3MB).</p>

      <Dialog open={libraryOpen} onOpenChange={setLibraryOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Biblioteca de vídeos</DialogTitle>
          </DialogHeader>
          {videosError && <p className="text-xs text-red-600">{videosError}</p>}
          {videos === null ? (
            <p className="text-sm text-zinc-400">Carregant…</p>
          ) : videos.length === 0 ? (
            <p className="text-sm text-zinc-400">Encara no has pujat cap vídeo.</p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {videos.map((video) => (
                <div
                  key={video.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => selectVideo(video)}
                  onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && selectVideo(video)}
                  className={`group relative text-left border rounded-xl overflow-hidden transition-colors cursor-pointer ${
                    value === video.url ? 'border-zinc-900 ring-2 ring-zinc-900' : 'border-zinc-200 hover:border-zinc-400'
                  }`}
                >
                  <video src={video.url} muted className="w-full aspect-video object-cover bg-zinc-100" />
                  <div className="p-2">
                    <p className="text-xs font-medium text-zinc-900 truncate">{video.filename}</p>
                    <p className="text-[10px] text-zinc-400">{formatSize(video.size_bytes)}</p>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => deleteVideo(video, e)}
                    className="absolute top-2 right-2 p-1.5 rounded-lg bg-white/90 text-zinc-400 opacity-0 group-hover:opacity-100 hover:text-red-500 transition-all"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
