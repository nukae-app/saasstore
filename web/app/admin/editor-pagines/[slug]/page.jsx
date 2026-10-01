'use client';

// Editor visual real (Fase 2, ver docs/ARQUITECTURA_DISENY_FIGMA.md) sobre
// una `Page` concreta. Carga `draft_tree`, lo hidrata en Craft.js
// (`treeToCraftState` + `<Frame data=...>`, de-riesgado en un checkpoint
// aparte antes de escribir esta pantalla), y guarda/publica contra la API
// real (`craftStateToTree` en sentido inverso al guardar).
import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { Editor, Frame, useEditor } from '@craftjs/core';
import { authFetch, getToken } from '../../../lib/auth';
import MIcon from '../../../../components/ui/m-icon';
import { NODE_RESOLVER } from '../../../../components/admin/pageEditor/resolver';
import { treeToCraftState, craftStateToTree, normalizeDraftTree } from '../../../../components/admin/pageEditor/craftTransform';
import { BreakpointProvider, useBreakpoint, BREAKPOINTS } from '../../../../components/admin/pageEditor/BreakpointContext';
import Toolbox from '../../../../components/admin/pageEditor/Toolbox';
import SettingsPanel from '../../../../components/admin/pageEditor/SettingsPanel';
import HistoryBar from '../../../../components/admin/pageEditor/HistoryBar';

export default function PageEditorScreen() {
  const { slug } = useParams();
  const [page, setPage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    authFetch(`/admin/pages/${slug}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setPage)
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [slug]);

  // `<Frame data=...>` solo hidrata en el montaje inicial de Craft.js —
  // calcularlo una vez por `page` cargada es suficiente, no hace falta que
  // sea estable entre renders posteriores.
  const initialCraftData = useMemo(() => {
    if (!page) return null;
    return JSON.stringify(treeToCraftState(normalizeDraftTree(page.draft_tree)));
  }, [page]);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <MIcon name="progress_activity" size={20} className="animate-spin text-secondary-foreground" />
      </div>
    );
  }
  if (notFound || !page) {
    return (
      <div className="p-6">
        <p className="text-sm text-secondary-foreground mb-2">Pàgina no trobada.</p>
        <Link href="/admin/editor-pagines" className="text-sm text-primary">Tornar al llistat</Link>
      </div>
    );
  }

  return (
    <BreakpointProvider>
      <Editor resolver={NODE_RESOLVER}>
        <EditorScreen slug={slug} page={page} initialCraftData={initialCraftData} />
      </Editor>
    </BreakpointProvider>
  );
}

const LOCALES = ['ca', 'es', 'en'];

function EditorScreen({ slug, page, initialCraftData }) {
  const { query } = useEditor();
  const { breakpoint } = useBreakpoint();
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [message, setMessage] = useState(null);
  const [published, setPublished] = useState(Boolean(page.published_tree));
  const [seoOpen, setSeoOpen] = useState(false);
  const [seoTitle, setSeoTitle] = useState(page.seo_title || {});
  const [seoDescription, setSeoDescription] = useState(page.seo_description || {});
  const [savingSeo, setSavingSeo] = useState(false);

  function currentTree() {
    const serialized = query.serialize();
    const parsed = typeof serialized === 'string' ? JSON.parse(serialized) : serialized;
    return craftStateToTree(parsed);
  }

  async function saveDraft() {
    setSaving(true); setMessage(null);
    try {
      const tree = currentTree();
      const r = await authFetch(`/admin/pages/${slug}`, { method: 'PATCH', body: JSON.stringify({ draft_tree: tree }) });
      if (!r.ok) { const b = await r.json(); setMessage({ type: 'error', text: b.detail || 'Error en desar' }); return; }
      setMessage({ type: 'success', text: 'Esborrany desat' });
    } finally { setSaving(false); }
  }

  async function publish() {
    setPublishing(true); setMessage(null);
    try {
      const tree = currentTree();
      const saveRes = await authFetch(`/admin/pages/${slug}`, { method: 'PATCH', body: JSON.stringify({ draft_tree: tree }) });
      if (!saveRes.ok) { const b = await saveRes.json(); setMessage({ type: 'error', text: b.detail || 'Error en desar' }); return; }
      const pubRes = await authFetch(`/admin/pages/${slug}/publish`, { method: 'POST' });
      const body = await pubRes.json();
      if (!pubRes.ok) { setMessage({ type: 'error', text: body.detail || 'Error en publicar' }); return; }
      setPublished(true);
      setMessage({ type: 'success', text: 'Pàgina publicada' });
    } finally { setPublishing(false); }
  }

  async function saveSeo() {
    setSavingSeo(true);
    try {
      const r = await authFetch(`/admin/pages/${slug}`, {
        method: 'PATCH',
        body: JSON.stringify({ seo_title: seoTitle, seo_description: seoDescription }),
      });
      if (!r.ok) { const b = await r.json(); setMessage({ type: 'error', text: b.detail || 'Error en desar el SEO' }); return; }
      setSeoOpen(false);
      setMessage({ type: 'success', text: 'SEO desat' });
    } finally { setSavingSeo(false); }
  }

  const viewportWidth = BREAKPOINTS.find((b) => b.key === breakpoint)?.width;

  return (
    <div className="flex flex-col h-screen">
      <div className="flex items-center justify-between px-4 py-3 border-b border-outline-variant bg-card shrink-0">
        <div className="flex items-center gap-3">
          <Link href="/admin/editor-pagines" className="text-secondary-foreground hover:text-on-surface">
            <MIcon name="arrow_back" size={18} />
          </Link>
          <span className="font-medium text-on-surface text-sm">/{slug}</span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${published ? 'bg-green-100 text-green-700' : 'bg-surface-container-high text-secondary-foreground'}`}>
            {published ? 'Publicada' : 'Esborrany'}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <HistoryBar />
          <button onClick={async () => { await saveDraft(); window.open(`/ca/preview-pagina/${slug}?token=${getToken()}`, '_blank'); }}
            className="text-sm px-3 py-2 rounded-xl border border-outline-variant hover:bg-surface-container-high transition-colors">
            Previsualitzar
          </button>
          <button onClick={() => setSeoOpen(true)}
            className="text-sm px-3 py-2 rounded-xl border border-outline-variant hover:bg-surface-container-high transition-colors">
            SEO
          </button>
          {message && (
            <span className={`text-xs ${message.type === 'error' ? 'text-red-500' : 'text-green-600'}`}>{message.text}</span>
          )}
          <button onClick={saveDraft} disabled={saving}
            className="text-sm px-4 py-2 rounded-xl border border-outline-variant hover:bg-surface-container-high disabled:opacity-50 transition-colors">
            {saving ? 'Desant…' : 'Desar esborrany'}
          </button>
          <button onClick={publish} disabled={publishing}
            className="bg-primary text-white text-sm px-4 py-2 rounded-xl hover:opacity-90 disabled:opacity-50 transition-colors">
            {publishing ? 'Publicant…' : 'Publicar'}
          </button>
        </div>
      </div>

      <div className="flex flex-1 min-h-0">
        <div className="w-56 border-r border-outline-variant p-4 overflow-y-auto shrink-0">
          <Toolbox />
        </div>

        <div className="flex-1 overflow-auto bg-surface-container-high p-8 flex justify-center">
          <div style={{ width: viewportWidth ? `${viewportWidth}px` : '100%', maxWidth: '100%' }}>
            <div className="bg-white shadow-sm min-h-[200px]">
              <Frame data={initialCraftData} />
            </div>
          </div>
        </div>

        <div className="w-64 border-l border-outline-variant p-4 overflow-y-auto shrink-0">
          <SettingsPanel />
        </div>
      </div>

      {seoOpen && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => setSeoOpen(false)}>
          <div className="bg-card rounded-2xl border border-outline-variant p-6 w-full max-w-md shadow-lg" onClick={(e) => e.stopPropagation()}>
            <h2 className="font-semibold text-on-surface mb-4">SEO de la pàgina</h2>
            {LOCALES.map((loc) => (
              <div key={loc} className="mb-3">
                <label className="block text-xs font-medium text-on-surface-variant mb-1">Títol ({loc})</label>
                <input
                  value={seoTitle[loc] || ''}
                  onChange={(e) => setSeoTitle((v) => ({ ...v, [loc]: e.target.value }))}
                  className="w-full border border-outline-variant rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
            ))}
            {LOCALES.map((loc) => (
              <div key={loc} className="mb-3">
                <label className="block text-xs font-medium text-on-surface-variant mb-1">Descripció ({loc})</label>
                <textarea
                  rows={2}
                  value={seoDescription[loc] || ''}
                  onChange={(e) => setSeoDescription((v) => ({ ...v, [loc]: e.target.value }))}
                  className="w-full border border-outline-variant rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
            ))}
            <div className="flex gap-2 mt-4">
              <button onClick={saveSeo} disabled={savingSeo}
                className="bg-primary text-white text-sm px-5 py-2 rounded-xl hover:opacity-90 disabled:opacity-50 transition-colors">
                {savingSeo ? 'Desant…' : 'Desar SEO'}
              </button>
              <button onClick={() => setSeoOpen(false)}
                className="text-sm px-4 py-2 rounded-xl border border-outline-variant hover:bg-surface-container-high transition-colors">
                Tancar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
