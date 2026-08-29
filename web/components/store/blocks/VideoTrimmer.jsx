'use client';

import { useEffect, useRef, useState } from 'react';

// Ha de coincidir amb api/app/services/video.py::MAX_DURATION_SECONDS —
// és un límit de qualitat (bitrate per segon), no de cost, ver conversa
// amb l'usuari sobre per què no cal ser més estrictes.
const MAX_DURATION = 50;
const MIN_DURATION = 1;
const THUMB_COUNT = 12;
const THUMB_HEIGHT = 64;

function formatTime(s) {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${String(sec).padStart(2, '0')}`;
}

function seekTo(video, t) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      video.removeEventListener('seeked', onSeeked);
      reject(new Error('timeout'));
    }, 8000);
    function onSeeked() {
      clearTimeout(timeout);
      video.removeEventListener('seeked', onSeeked);
      resolve();
    }
    video.addEventListener('seeked', onSeeked);
    video.currentTime = t;
  });
}

// Editor de tall estil "recorte de vídeo" d'iPhone: tira de miniatures +
// dos tiradors per triar quin tram (fins a MAX_DURATION segons) del vídeo
// original es puja. Tot això és local al navegador (URL.createObjectURL,
// mai es puja res encara mentre l'admin retalla) — el tall real
// (`ffmpeg -ss/-t`) el fa el servidor amb els segons que triï aquí (ver
// api/app/services/video.py::transcode_for_web).
export default function VideoTrimmer({ file, onCancel, onConfirm, uploading, error }) {
  const [url] = useState(() => URL.createObjectURL(file));
  const [duration, setDuration] = useState(0);
  const [thumbnails, setThumbnails] = useState(null);
  const [thumbError, setThumbError] = useState(false);
  const [start, setStart] = useState(0);
  const [end, setEnd] = useState(0);
  const [dragging, setDragging] = useState(null); // 'start' | 'end' | null

  const videoRef = useRef(null);
  const stripRef = useRef(null);

  useEffect(() => () => URL.revokeObjectURL(url), [url]);

  // Si el navegador no pot ni carregar els metadades (còdec/contenidor no
  // suportat, fitxer corrupte...) `onLoadedMetadata` no arriba mai — sense
  // aquest avís es quedaria penjat a "Carregant miniatures…" per sempre.
  useEffect(() => {
    const timeout = setTimeout(() => {
      if (!duration) setThumbError(true);
    }, 10000);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function onLoadedMetadata() {
    const d = videoRef.current.duration;
    setDuration(d);
    setEnd(Math.min(d, MAX_DURATION));
    generateThumbnails(d);
  }

  async function generateThumbnails(d) {
    // Cada miniatura es captura per separat: si UNA sola tarda massa a
    // buscar (habitual en vídeos reals/mòbils, no en els curts sintètics
    // de prova) no s'ha de tirar a perdre tot l'editor — es deixa un forat
    // (placeholder gris) en aquella posició i es continua amb la resta.
    // El tall en si (arrossegar els tiradors, pujar) no depèn de les
    // miniatures, només de `duration`.
    const video = videoRef.current;
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const thumbs = [];
    for (let i = 0; i < THUMB_COUNT; i++) {
      try {
        // eslint-disable-next-line no-await-in-loop
        await seekTo(video, (d * i) / THUMB_COUNT);
        const w = Math.round((video.videoWidth / video.videoHeight) * THUMB_HEIGHT) || THUMB_HEIGHT;
        canvas.width = w;
        canvas.height = THUMB_HEIGHT;
        ctx.drawImage(video, 0, 0, w, THUMB_HEIGHT);
        thumbs.push(canvas.toDataURL('image/jpeg', 0.6));
      } catch {
        thumbs.push(null);
      }
    }
    setThumbnails(thumbs);
    video.currentTime = 0;
  }

  function pointerToTime(clientX) {
    const rect = stripRef.current.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    return ratio * duration;
  }

  useEffect(() => {
    if (!dragging) return undefined;
    function onMove(e) {
      const t = pointerToTime(e.clientX);
      if (dragging === 'start') {
        let next = Math.min(t, end - MIN_DURATION);
        next = Math.max(next, 0, end - MAX_DURATION);
        setStart(next);
        videoRef.current.currentTime = next;
      } else {
        let next = Math.max(t, start + MIN_DURATION);
        next = Math.min(next, duration, start + MAX_DURATION);
        setEnd(next);
        videoRef.current.currentTime = next;
      }
    }
    function onUp() {
      setDragging(null);
    }
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dragging, start, end, duration]);

  const startPct = duration ? (start / duration) * 100 : 0;
  const endPct = duration ? (end / duration) * 100 : 100;

  return (
    <div className="space-y-3">
      <video
        ref={videoRef}
        src={url}
        onLoadedMetadata={onLoadedMetadata}
        onError={() => setThumbError(true)}
        muted
        playsInline
        className="w-full aspect-video rounded-xl bg-black object-contain"
      />

      {thumbError ? (
        <p className="text-xs text-red-600">No s&apos;ha pogut previsualitzar aquest vídeo al navegador. Prova amb un altre fitxer (MP4 recomanat).</p>
      ) : !thumbnails ? (
        <p className="text-xs text-zinc-400">Carregant miniatures…</p>
      ) : (
        <div ref={stripRef} className="relative h-16 rounded-lg overflow-hidden flex select-none touch-none">
          {thumbnails.map((src, i) =>
            src ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img key={i} src={src} alt="" className="flex-1 h-full object-cover pointer-events-none" />
            ) : (
              <div key={i} className="flex-1 h-full bg-zinc-300 pointer-events-none" />
            ),
          )}
          <div className="absolute inset-y-0 left-0 bg-black/60" style={{ width: `${startPct}%` }} />
          <div className="absolute inset-y-0 right-0 bg-black/60" style={{ width: `${100 - endPct}%` }} />
          <div
            onPointerDown={(e) => { e.preventDefault(); setDragging('start'); }}
            className="absolute inset-y-0 w-3 bg-white rounded-sm cursor-ew-resize shadow"
            style={{ left: `calc(${startPct}% - 6px)` }}
          />
          <div
            onPointerDown={(e) => { e.preventDefault(); setDragging('end'); }}
            className="absolute inset-y-0 w-3 bg-white rounded-sm cursor-ew-resize shadow"
            style={{ left: `calc(${endPct}% - 6px)` }}
          />
        </div>
      )}

      <p className="text-xs text-zinc-500">
        {formatTime(start)} – {formatTime(end)} · {(end - start).toFixed(1)}s (màxim {MAX_DURATION}s)
      </p>
      {error && <p className="text-xs text-red-600">{error}</p>}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={onCancel}
          disabled={uploading}
          className="text-xs font-medium text-zinc-700 border border-zinc-200 rounded-xl px-3 py-2 hover:bg-zinc-50 transition-colors disabled:opacity-50"
        >
          Cancel·lar
        </button>
        <button
          type="button"
          onClick={() => onConfirm(start, end)}
          disabled={uploading || !duration}
          className="flex-1 text-xs font-medium text-white bg-zinc-900 rounded-xl px-3 py-2 hover:bg-zinc-700 transition-colors disabled:opacity-50"
        >
          {uploading ? 'Comprimint…' : 'Pujar aquest tram'}
        </button>
      </div>
    </div>
  );
}
