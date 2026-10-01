'use client';

// UI de la Fase 3 (docs/ARQUITECTURA_DISENY_FIGMA.md §4) — connectar Figma
// i importar estils de color/tipografia cap al tema del tenant. Escrit
// sense credencials OAuth reals (FIGMA_CLIENT_ID buit a l'API): el botó
// "Connectar Figma" no s'ha pogut provar en viu, ver docs/CONTINUAR_DISENY_FIGMA.md.
import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { authFetch } from '../../lib/auth';
import MIcon from '../../../components/ui/m-icon';

const COLOR_FIELDS = [
  ['primary', 'Primari'], ['primary_foreground', 'Text sobre primari'],
  ['secondary', 'Secundari'], ['secondary_foreground', 'Text sobre secundari'],
  ['accent', 'Accent'], ['accent_foreground', 'Text sobre accent'],
  ['background', 'Fons'], ['foreground', 'Text principal'],
  ['muted', 'Atenuat'], ['muted_foreground', 'Text atenuat'],
  ['border', 'Vora'],
];
const FONT_FIELDS = [['font_headline', 'Tipografia de titulars'], ['font_body', 'Tipografia de cos']];

export default function FigmaAdminPage() {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);

  const [fileKey, setFileKey] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [styles, setStyles] = useState([]);
  const [mapping, setMapping] = useState({});
  const [applying, setApplying] = useState(false);
  const [applyMessage, setApplyMessage] = useState('');

  // --- Fase 4: import estructural (frames -> pàgina) ---
  const [frames, setFrames] = useState([]);
  const [selectedFrame, setSelectedFrame] = useState('');
  const [searchingFrames, setSearchingFrames] = useState(false);
  const [framesError, setFramesError] = useState('');
  const [pages, setPages] = useState([]);
  const [targetPageId, setTargetPageId] = useState('');
  const [job, setJob] = useState(null);
  const [importing, setImporting] = useState(false);
  const [applyingJob, setApplyingJob] = useState(false);
  const pollRef = useRef(null);

  useEffect(() => {
    authFetch('/admin/pages').then((r) => r.json()).then(setPages).catch(() => {});
    return () => clearTimeout(pollRef.current);
  }, []);

  function loadStatus() {
    setLoading(true);
    authFetch('/admin/figma/status').then((r) => r.json()).then(setStatus).finally(() => setLoading(false));
  }

  useEffect(() => { loadStatus(); }, []);

  const justConnected = searchParams.get('connected') === '1';

  async function connect() {
    setConnecting(true);
    try {
      const r = await authFetch('/admin/figma/connect-init', { method: 'POST' });
      if (!r.ok) { setConnecting(false); return; }
      window.location.href = '/api/figma/connect';
    } catch {
      setConnecting(false);
    }
  }

  async function disconnect() {
    if (!confirm('Desconnectar Figma? Caldrà tornar a autoritzar per importar estils.')) return;
    setDisconnecting(true);
    try {
      await authFetch('/admin/figma/connection', { method: 'DELETE' });
      setStyles([]);
      setMapping({});
      loadStatus();
    } finally { setDisconnecting(false); }
  }

  // Accepta tant una clau nua com una URL sencera de Figma
  // (figma.com/file/<key>/...) — s'extreu la clau si cal.
  function extractFileKey(raw) {
    const match = raw.match(/figma\.com\/(?:file|design)\/([a-zA-Z0-9]+)/);
    return match ? match[1] : raw.trim();
  }

  async function searchStyles() {
    if (!fileKey.trim()) return;
    setSearching(true); setSearchError(''); setStyles([]); setMapping({});
    try {
      const key = extractFileKey(fileKey);
      const r = await authFetch('/admin/figma/styles', { method: 'POST', body: JSON.stringify({ file_key: key }) });
      const body = await r.json();
      if (!r.ok) { setSearchError(body.detail || 'Error cercant estils'); return; }
      setStyles(body);
    } finally { setSearching(false); }
  }

  async function searchFrames() {
    if (!fileKey.trim()) return;
    setSearchingFrames(true); setFramesError(''); setFrames([]); setSelectedFrame(''); setJob(null);
    try {
      const key = extractFileKey(fileKey);
      const r = await authFetch(`/admin/figma/frames?file_key=${encodeURIComponent(key)}`);
      const body = await r.json();
      if (!r.ok) { setFramesError(body.detail || 'Error cercant frames'); return; }
      setFrames(body);
    } finally { setSearchingFrames(false); }
  }

  function pollJob(jobId) {
    authFetch(`/admin/figma/import-jobs/${jobId}`).then((r) => r.json()).then((body) => {
      setJob(body);
      if (body.status === 'pending' || body.status === 'processing') {
        pollRef.current = setTimeout(() => pollJob(jobId), 2000);
      }
    });
  }

  async function startImport() {
    if (!selectedFrame) return;
    setImporting(true); setJob(null);
    try {
      const key = extractFileKey(fileKey);
      const r = await authFetch('/admin/figma/import-jobs', {
        method: 'POST',
        body: JSON.stringify({ file_key: key, node_id: selectedFrame }),
      });
      const body = await r.json();
      if (!r.ok) { setJob({ status: 'error', error_message: body.detail }); return; }
      setJob(body);
      pollJob(body.id);
    } finally { setImporting(false); }
  }

  async function applyJob() {
    if (!job || !targetPageId) return;
    setApplyingJob(true);
    try {
      const r = await authFetch(`/admin/figma/import-jobs/${job.id}/apply`, {
        method: 'POST',
        body: JSON.stringify({ target_page_id: Number(targetPageId) }),
      });
      const body = await r.json();
      if (!r.ok) { setJob((j) => ({ ...j, error_message: body.detail })); return; }
      setJob(body);
    } finally { setApplyingJob(false); }
  }

  async function applyToTheme() {
    const payload = {};
    for (const style of styles) {
      const target = mapping[style.figma_style_id];
      if (target) payload[target] = style.value;
    }
    if (Object.keys(payload).length === 0) { setApplyMessage('Tria almenys un mapeig abans d\'aplicar.'); return; }
    setApplying(true); setApplyMessage('');
    try {
      const r = await authFetch('/admin/configuracio/theme', { method: 'PATCH', body: JSON.stringify(payload) });
      if (!r.ok) { const b = await r.json(); setApplyMessage(b.detail || 'Error aplicant el tema'); return; }
      setApplyMessage('Tema actualitzat.');
    } finally { setApplying(false); }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <MIcon name="progress_activity" size={20} className="animate-spin text-secondary-foreground" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-on-surface">Figma (beta)</h1>
        <p className="text-sm text-secondary-foreground mt-0.5">
          Connecta el teu compte de Figma per importar colors i tipografies cap al tema de la botiga.
        </p>
      </div>

      {justConnected && (
        <div className="bg-green-50 text-green-700 text-sm rounded-xl px-4 py-3 mb-4">Figma connectat correctament.</div>
      )}

      <div className="bg-card rounded-2xl border border-outline-variant p-6 mb-6 shadow-sm">
        {status?.connected ? (
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-on-surface">Connectat com a {status.figma_handle || 'desconegut'}</p>
              <p className="text-xs text-secondary-foreground">des de {new Date(status.connected_at).toLocaleDateString('ca')}</p>
            </div>
            <button onClick={disconnect} disabled={disconnecting}
              className="text-sm px-4 py-2 rounded-xl border border-outline-variant hover:bg-surface-container-high disabled:opacity-50 transition-colors">
              {disconnecting ? 'Desconnectant…' : 'Desconnectar'}
            </button>
          </div>
        ) : (
          <div className="flex items-center justify-between">
            <p className="text-sm text-secondary-foreground">No hi ha cap compte de Figma connectat.</p>
            <button onClick={connect} disabled={connecting}
              className="bg-primary text-white text-sm px-4 py-2 rounded-xl hover:opacity-90 disabled:opacity-50 transition-colors">
              {connecting ? 'Connectant…' : 'Connectar Figma'}
            </button>
          </div>
        )}
      </div>

      {status?.connected && (
        <div className="bg-card rounded-2xl border border-outline-variant p-6 shadow-sm">
          <h2 className="font-semibold text-on-surface mb-3">Importar estils d&apos;un fitxer</h2>
          <div className="flex gap-2 mb-4">
            <input
              value={fileKey}
              onChange={(e) => setFileKey(e.target.value)}
              placeholder="URL o clau del fitxer de Figma"
              className="flex-1 border border-outline-variant rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <button onClick={searchStyles} disabled={searching}
              className="text-sm px-4 py-2 rounded-xl border border-outline-variant hover:bg-surface-container-high disabled:opacity-50 transition-colors">
              {searching ? 'Cercant…' : 'Cercar estils'}
            </button>
          </div>
          {searchError && <p className="text-red-500 text-sm mb-3">{searchError}</p>}

          {styles.length > 0 && (
            <>
              <div className="flex flex-col gap-2 mb-4">
                {styles.map((s) => (
                  <div key={s.figma_style_id} className="flex items-center gap-3 border border-outline-variant rounded-xl px-3 py-2">
                    {s.kind === 'color' ? (
                      <span className="w-5 h-5 rounded-full border border-outline-variant shrink-0" style={{ background: s.value }} />
                    ) : (
                      <MIcon name="text_fields" size={16} className="text-secondary-foreground shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-on-surface truncate">{s.name}</p>
                      <p className="text-xs text-secondary-foreground truncate">{s.value}</p>
                    </div>
                    <select
                      value={mapping[s.figma_style_id] || ''}
                      onChange={(e) => setMapping((m) => ({ ...m, [s.figma_style_id]: e.target.value || undefined }))}
                      className="text-xs border border-outline-variant rounded-lg px-2 py-1.5"
                    >
                      <option value="">No importar</option>
                      {(s.kind === 'color' ? COLOR_FIELDS : FONT_FIELDS).map(([key, label]) => (
                        <option key={key} value={key}>{label}</option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
              <div className="flex items-center gap-3">
                <button onClick={applyToTheme} disabled={applying}
                  className="bg-primary text-white text-sm px-5 py-2 rounded-xl hover:opacity-90 disabled:opacity-50 transition-colors">
                  {applying ? 'Aplicant…' : 'Aplicar al tema'}
                </button>
                {applyMessage && <span className="text-xs text-secondary-foreground">{applyMessage}</span>}
              </div>
            </>
          )}
        </div>
      )}

      {status?.connected && (
        <div className="bg-card rounded-2xl border border-outline-variant p-6 shadow-sm mt-6">
          <h2 className="font-semibold text-on-surface mb-1">Importar un frame com a pàgina</h2>
          <p className="text-xs text-secondary-foreground mb-3">
            Només frames amb auto-layout es poden importar — la resta s&apos;omet i avisa (ver documentació).
          </p>
          <button onClick={searchFrames} disabled={searchingFrames || !fileKey.trim()}
            className="text-sm px-4 py-2 rounded-xl border border-outline-variant hover:bg-surface-container-high disabled:opacity-50 transition-colors mb-3">
            {searchingFrames ? 'Cercant…' : 'Cercar frames del fitxer de dalt'}
          </button>
          {framesError && <p className="text-red-500 text-sm mb-3">{framesError}</p>}

          {frames.length > 0 && (
            <div className="flex flex-col gap-2 mb-4">
              {frames.map((f) => (
                <label key={f.id} className={`flex items-center gap-3 border rounded-xl px-3 py-2 cursor-pointer ${selectedFrame === f.id ? 'border-primary' : 'border-outline-variant'}`}>
                  <input type="radio" name="frame" checked={selectedFrame === f.id} onChange={() => setSelectedFrame(f.id)} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-on-surface truncate">{f.name} <span className="text-secondary-foreground">— {f.page}</span></p>
                    {!f.has_auto_layout && <p className="text-[11px] text-amber-600">Sense auto-layout: no es podrà importar</p>}
                  </div>
                </label>
              ))}
            </div>
          )}

          {selectedFrame && (
            <div className="flex items-center gap-2 mb-4">
              <button onClick={startImport} disabled={importing}
                className="bg-primary text-white text-sm px-4 py-2 rounded-xl hover:opacity-90 disabled:opacity-50 transition-colors">
                {importing ? 'Important…' : 'Importar'}
              </button>
            </div>
          )}

          {job && (
            <div className="border border-outline-variant rounded-xl p-4">
              {(job.status === 'pending' || job.status === 'processing') && (
                <p className="text-sm text-secondary-foreground flex items-center gap-2">
                  <MIcon name="progress_activity" size={14} className="animate-spin" /> Important…
                </p>
              )}
              {job.status === 'error' && <p className="text-sm text-red-500">{job.error_message}</p>}
              {job.status === 'ready' && (
                <>
                  <p className="text-sm text-green-700 mb-2">Importació llesta.</p>
                  {job.warnings?.length > 0 && (
                    <ul className="text-xs text-amber-600 mb-3 list-disc pl-4">
                      {job.warnings.map((w, i) => <li key={i}>{w}</li>)}
                    </ul>
                  )}
                  {job.target_page_id ? (
                    <Link href={`/admin/editor-pagines/${pages.find((p) => p.id === job.target_page_id)?.slug || ''}`}
                      className="text-sm text-primary">
                      Obrir a l&apos;editor →
                    </Link>
                  ) : (
                    <div className="flex items-center gap-2">
                      <select value={targetPageId} onChange={(e) => setTargetPageId(e.target.value)}
                        className="text-sm border border-outline-variant rounded-lg px-2 py-1.5">
                        <option value="">Tria una pàgina…</option>
                        {pages.map((p) => <option key={p.id} value={p.id}>/{p.slug}</option>)}
                      </select>
                      <button onClick={applyJob} disabled={applyingJob || !targetPageId}
                        className="bg-primary text-white text-sm px-4 py-2 rounded-xl hover:opacity-90 disabled:opacity-50 transition-colors">
                        {applyingJob ? 'Aplicant…' : 'Aplicar a l\'esborrany'}
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
