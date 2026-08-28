'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { authFetch } from '../../lib/auth';
import { useT } from '../../lib/i18n';
import { Plus, Pencil, Trash2, GripVertical, RefreshCw, ExternalLink } from 'lucide-react';
import { Button } from '../../../components/ui/button';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../../../components/ui/dialog';
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetFooter,
} from '../../../components/ui/sheet';
import { BLOCK_META, BLOCK_TYPES } from '../../../components/store/blocks/meta';
import HeroPropsForm from '../../../components/store/blocks/HeroPropsForm';
import CarouselPropsForm from '../../../components/store/blocks/CarouselPropsForm';

const PROPS_FORMS = { hero: HeroPropsForm, carousel: CarouselPropsForm };

// Mateixos valors per defecte que web/app/globals.css, perquè un tenant que
// no ha tocat res vegi els pickers ja carregats amb el look actual.
const THEME_FIELDS = [
  { key: 'background', label: 'Fons', default: '#faf9f6' },
  { key: 'foreground', label: 'Text', default: '#1a1a1a' },
  { key: 'primary', label: 'Principal', default: '#171717' },
  { key: 'primary_foreground', label: 'Text sobre principal', default: '#ffffff' },
  { key: 'secondary', label: 'Secundari', default: '#f5f5f5' },
  { key: 'secondary_foreground', label: 'Text sobre secundari', default: '#1a1a1a' },
  { key: 'accent', label: 'Accent', default: '#f2f2f2' },
  { key: 'accent_foreground', label: 'Text sobre accent', default: '#262626' },
  { key: 'muted', label: 'Apagat', default: '#f2f2f2' },
  { key: 'muted_foreground', label: 'Text apagat', default: '#757575' },
  { key: 'border', label: 'Vores', default: '#cccccc' },
];

export default function DissenyWebPage() {
  const t = useT();
  const [tab, setTab] = useState('blocs'); // blocs | disseny | css
  const [config, setConfig] = useState(null);
  const iframeRef = useRef(null);
  const [previewReady, setPreviewReady] = useState(false);

  const loadConfig = useCallback(async () => {
    const r = await authFetch('/admin/configuracio');
    setConfig(await r.json());
  }, []);
  useEffect(() => { loadConfig(); }, [loadConfig]);

  // El pont de missatges viu a web/components/store/PreviewBridge.jsx, muntat
  // dins de l'iframe només quan detecta ?admin_preview=1. Aquí només escoltem
  // el seu "ja estic llest" per no enviar cap missatge a un iframe que encara
  // no ha carregat.
  useEffect(() => {
    function onMessage(e) {
      if (e.origin !== window.location.origin) return;
      if (e.data?.type === 'preview-ready') setPreviewReady(true);
    }
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, []);

  const sendPreview = useCallback((msg) => {
    if (!previewReady) return;
    iframeRef.current?.contentWindow?.postMessage(msg, window.location.origin);
  }, [previewReady]);

  function reloadPreview() {
    setPreviewReady(false);
    const el = iframeRef.current;
    if (el) el.src = el.src;
  }

  return (
    <div className="max-w-[1700px] mx-auto">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
        <div>
          <h1 className="text-xl font-semibold text-zinc-900">{t('design.title', 'Disseny web')}</h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            {t('design.hint', 'Blocs, colors, tipografia i CSS de la teva botiga — amb previsualització en directe.')}
          </p>
        </div>
        <div className="flex gap-1 bg-zinc-100 p-1 rounded-xl w-fit">
          {[
            ['blocs', t('design.tab.blocks', 'Blocs')],
            ['disseny', t('design.tab.design', 'Colors i tipografia')],
            ['css', t('design.tab.css', 'CSS')],
          ].map(([k, l]) => (
            <button key={k} onClick={() => setTab(k)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${tab === k ? 'bg-white shadow-sm text-zinc-900' : 'text-zinc-600 hover:text-zinc-900'}`}>
              {l}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 items-start">
        <div className="min-w-0">
          {tab === 'blocs' && <BlocksPanel sendPreview={sendPreview} />}
          {tab === 'disseny' && (config ? <DissenyPanel config={config} onSaved={loadConfig} sendPreview={sendPreview} /> : <Loading t={t} />)}
          {tab === 'css' && (config ? <CustomCssPanel config={config} onSaved={loadConfig} sendPreview={sendPreview} /> : <Loading t={t} />)}
        </div>

        <div className="xl:sticky xl:top-6">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-medium text-zinc-500 uppercase tracking-wide">
              {t('design.preview', 'Previsualització en directe')}
            </p>
            <div className="flex items-center gap-3">
              <a href="/ca" target="_blank" rel="noopener" className="text-zinc-400 hover:text-zinc-700 transition-colors" title={t('design.open_new_tab', 'Obrir en una pestanya nova')}>
                <ExternalLink size={14} />
              </a>
              <button onClick={reloadPreview} className="text-zinc-400 hover:text-zinc-700 transition-colors" title={t('design.reload', 'Recarregar')}>
                <RefreshCw size={14} />
              </button>
            </div>
          </div>
          <div className="rounded-2xl border border-zinc-200 overflow-hidden bg-white shadow-sm h-[calc(100vh-190px)] min-h-[420px]">
            <iframe
              ref={iframeRef}
              src="/ca?admin_preview=1"
              className="w-full h-full border-0"
              title={t('design.preview', 'Previsualització en directe')}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function Loading({ t }) {
  return <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading')}</div>;
}

function blockSummary(block) {
  const meta = BLOCK_META[block.block_type];
  if (block.block_type === 'hero') return block.props?.title || '(sense títol)';
  if (block.block_type === 'carousel') return `${block.props?.heading || '(sense títol)'} · #${block.props?.etiqueta_slug || '—'}`;
  return meta?.description || '';
}

function BlocksPanel({ sendPreview }) {
  const [blocks, setBlocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [adding, setAdding] = useState(false);
  const [editingBlock, setEditingBlock] = useState(null);
  const [editingProps, setEditingProps] = useState({});
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [err, setErr] = useState('');
  const dragIdRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await authFetch('/admin/home-blocks');
      setBlocks(await r.json());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function addBlock(type) {
    setAdding(true);
    setErr('');
    try {
      const r = await authFetch('/admin/home-blocks', {
        method: 'POST',
        body: JSON.stringify({ block_type: type, props: {} }),
      });
      if (!r.ok) { const b = await r.json(); setErr(typeof b.detail === 'string' ? b.detail : 'Error en afegir el bloc'); return; }
      const created = await r.json();
      await load();
      setAddOpen(false);
      sendPreview({ type: 'reload' });
      if (BLOCK_META[type]?.editable) {
        setEditingBlock(created);
        setEditingProps(created.props || {});
      }
    } finally {
      setAdding(false);
    }
  }

  function openEdit(block) {
    setEditingBlock(block);
    setEditingProps(block.props || {});
    setErr('');
  }

  // Si l'usuari edita en directe i després cancel·la, el DOM de l'iframe ha
  // quedat mutat amb valors provisionals que mai s'han desat — l'única
  // manera fiable de tornar-lo a l'estat real és recarregar-lo.
  function cancelEdit() {
    setEditingBlock(null);
    sendPreview({ type: 'reload' });
  }

  async function saveEdit() {
    if (!editingBlock) return;
    setSaving(true);
    setErr('');
    try {
      const r = await authFetch(`/admin/home-blocks/${editingBlock.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ props: editingProps }),
      });
      if (!r.ok) { const b = await r.json(); setErr(typeof b.detail === 'string' ? b.detail : 'Error en guardar'); return; }
      await load();
      setEditingBlock(null);
    } finally {
      setSaving(false);
    }
  }

  async function toggleEnabled(block) {
    sendPreview({ type: 'block-toggle', blockId: block.id, enabled: !block.enabled });
    await authFetch(`/admin/home-blocks/${block.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled: !block.enabled }),
    });
    await load();
  }

  async function deleteBlock(block) {
    if (!confirm(`Eliminar el bloc "${BLOCK_META[block.block_type]?.label || block.block_type}"?`)) return;
    setDeletingId(block.id);
    try {
      await authFetch(`/admin/home-blocks/${block.id}`, { method: 'DELETE' });
      await load();
      sendPreview({ type: 'reload' });
    } finally {
      setDeletingId(null);
    }
  }

  function onDragStart(id) { dragIdRef.current = id; }
  function onDragOver(e) { e.preventDefault(); }

  async function persistReorder(list) {
    await authFetch('/admin/home-blocks/reorder', {
      method: 'PATCH',
      body: JSON.stringify({ order: list.map((b, i) => ({ id: b.id, position: i + 1 })) }),
    });
  }

  function onDrop(targetId) {
    const dragId = dragIdRef.current;
    dragIdRef.current = null;
    if (dragId == null || dragId === targetId) return;
    setBlocks((prev) => {
      const list = [...prev];
      const fromIdx = list.findIndex((b) => b.id === dragId);
      const toIdx = list.findIndex((b) => b.id === targetId);
      if (fromIdx === -1 || toIdx === -1) return prev;
      const [moved] = list.splice(fromIdx, 1);
      list.splice(toIdx, 0, moved);
      sendPreview({ type: 'block-reorder', order: list.map((b) => b.id) });
      persistReorder(list);
      return list;
    });
  }

  const availableToAdd = BLOCK_TYPES.filter((type) => type === 'carousel' || !blocks.some((b) => b.block_type === type));
  const EditForm = editingBlock ? PROPS_FORMS[editingBlock.block_type] : null;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-zinc-500">Arrossega per reordenar els blocs del home.</p>
        <button
          onClick={() => { setErr(''); setAddOpen(true); }}
          className="flex items-center gap-1.5 bg-zinc-900 text-white text-sm px-4 py-2 rounded-xl hover:bg-zinc-700 transition-colors"
        >
          <Plus size={15} /> Afegir bloc
        </button>
      </div>

      {loading ? (
        <p className="text-zinc-400 text-sm">Carregant…</p>
      ) : (
        <div className="flex flex-col gap-2">
          {blocks.map((block) => {
            const meta = BLOCK_META[block.block_type];
            return (
              <div
                key={block.id}
                draggable
                onDragStart={() => onDragStart(block.id)}
                onDragOver={onDragOver}
                onDrop={() => onDrop(block.id)}
                className={`flex items-center gap-3 bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] px-4 py-3 cursor-grab active:cursor-grabbing transition-opacity ${block.enabled ? '' : 'opacity-50'}`}
              >
                <GripVertical size={16} className="text-zinc-300 shrink-0" />

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-zinc-900 text-sm">{meta?.label || block.block_type}</span>
                    <span className="text-[10px] bg-zinc-100 text-zinc-500 px-1.5 py-0.5 rounded-full">{block.block_type}</span>
                  </div>
                  <p className="text-xs text-zinc-400 mt-0.5 truncate">{blockSummary(block)}</p>
                </div>

                <div className="flex items-center gap-1 shrink-0">
                  <button
                    type="button"
                    onClick={() => toggleEnabled(block)}
                    title={block.enabled ? 'Actiu' : 'Inactiu'}
                    className={`w-10 h-5 rounded-full transition-colors relative shrink-0 ${block.enabled ? 'bg-green-500' : 'bg-zinc-300'}`}
                  >
                    <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${block.enabled ? 'left-5' : 'left-0.5'}`} />
                  </button>
                  {meta?.editable && (
                    <button onClick={() => openEdit(block)} className="p-1.5 text-zinc-400 hover:text-zinc-700 rounded-lg hover:bg-zinc-50 transition-colors">
                      <Pencil size={14} />
                    </button>
                  )}
                  <button
                    onClick={() => deleteBlock(block)}
                    disabled={deletingId === block.id}
                    className="p-1.5 text-zinc-300 hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            );
          })}
          {blocks.length === 0 && (
            <p className="text-zinc-400 text-sm py-8 text-center">Cap bloc configurat. La pàgina d&apos;inici es mostrarà buida — afegeix-ne un!</p>
          )}
        </div>
      )}

      {/* Afegir bloc */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Afegir bloc</DialogTitle>
            <DialogDescription>Tria un tipus de bloc per afegir-lo al final del home.</DialogDescription>
          </DialogHeader>
          {err && <p className="text-red-500 text-xs">{err}</p>}
          <div className="grid grid-cols-1 gap-2">
            {availableToAdd.map((type) => {
              const meta = BLOCK_META[type];
              return (
                <button
                  key={type}
                  onClick={() => addBlock(type)}
                  disabled={adding}
                  className="flex flex-col items-start gap-0.5 p-3 rounded-xl border border-zinc-200 hover:border-zinc-900 text-left transition-colors disabled:opacity-50"
                >
                  <span className="text-sm font-semibold text-zinc-900">{meta.label}</span>
                  <span className="text-xs text-zinc-400">{meta.description}</span>
                </button>
              );
            })}
            {availableToAdd.length === 0 && (
              <p className="text-sm text-zinc-400 text-center py-4">Ja tens tots els blocs disponibles configurats.</p>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Editar props */}
      <Sheet open={!!editingBlock} onOpenChange={(open) => { if (!open) cancelEdit(); }}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>{editingBlock ? BLOCK_META[editingBlock.block_type]?.label : ''}</SheetTitle>
          </SheetHeader>
          <div className="mt-4">
            {EditForm && editingBlock && (
              <EditForm
                props={editingProps}
                onChange={setEditingProps}
                onFieldChange={(field, value) => sendPreview({ type: 'block-field', blockId: editingBlock.id, field, value })}
              />
            )}
          </div>
          {err && <p className="text-red-500 text-xs mt-3">{err}</p>}
          <SheetFooter className="mt-6">
            <button
              onClick={cancelEdit}
              className="text-sm px-4 py-2 rounded-xl border border-zinc-200 hover:bg-zinc-50 transition-colors"
            >
              Cancel·lar
            </button>
            <button
              onClick={saveEdit}
              disabled={saving}
              className="bg-zinc-900 text-white text-sm px-5 py-2 rounded-xl hover:bg-zinc-700 disabled:opacity-50 transition-colors"
            >
              {saving ? 'Guardant…' : 'Guardar canvis'}
            </button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </div>
  );
}

function DissenyPanel({ config, onSaved, sendPreview }) {
  const t = useT();
  const [values, setValues] = useState(() => {
    const v = {};
    for (const f of THEME_FIELDS) v[f.key] = config.theme?.[f.key] || f.default;
    return v;
  });
  const [fontHeadline, setFontHeadline] = useState(config.theme?.font_headline || '');
  const [fontBody, setFontBody] = useState(config.theme?.font_body || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  function setColor(key, value) {
    setValues((v) => {
      const next = { ...v, [key]: value };
      sendPreview({ type: 'theme-vars', vars: { ...next, font_headline: fontHeadline, font_body: fontBody } });
      return next;
    });
  }

  function setFont(which, value) {
    if (which === 'headline') setFontHeadline(value); else setFontBody(value);
    sendPreview({
      type: 'theme-vars',
      vars: { ...values, font_headline: which === 'headline' ? value : fontHeadline, font_body: which === 'body' ? value : fontBody },
    });
  }

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    setSaved(false);
    const r = await authFetch('/admin/configuracio/theme', {
      method: 'PATCH',
      body: JSON.stringify({
        ...values,
        font_headline: fontHeadline || null,
        font_body: fontBody || null,
      }),
    });
    setSaving(false);
    if (r.ok) {
      setSaved(true);
      onSaved();
    } else {
      setError((await r.json()).detail || t('config.save_error', 'Error desant'));
    }
  }

  function resetDefaults() {
    const v = {};
    for (const f of THEME_FIELDS) v[f.key] = f.default;
    setValues(v);
    setFontHeadline('');
    setFontBody('');
    sendPreview({ type: 'theme-vars', vars: { ...v, font_headline: '', font_body: '' } });
  }

  return (
    <form onSubmit={save} className="space-y-5">
      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6 space-y-4">
        <p className="text-sm text-zinc-500">
          {t('config.design.hint', "Colors i tipografia propis de la teva botiga. Si has encarregat un disseny, pots copiar aquí els valors exactes (hex, nom de la font) que et doni el/la dissenyador/a.")}
        </p>

        <div className="flex h-10 rounded-lg overflow-hidden border border-zinc-200">
          {THEME_FIELDS.map((f) => (
            <div key={f.key} className="flex-1" style={{ backgroundColor: values[f.key] }} title={f.label} />
          ))}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {THEME_FIELDS.map((f) => (
            <div key={f.key} className="flex items-center gap-2">
              <input
                type="color"
                value={values[f.key]}
                onChange={(e) => setColor(f.key, e.target.value)}
                className="w-9 h-9 rounded border border-zinc-300 shrink-0 cursor-pointer"
              />
              <div className="min-w-0 flex-1">
                <label className="block text-xs font-medium text-zinc-700">{f.label}</label>
                <input
                  value={values[f.key]}
                  onChange={(e) => setColor(f.key, e.target.value)}
                  className="w-full border border-zinc-300 rounded-lg px-2 py-1 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-zinc-900"
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6 space-y-4">
        <p className="text-sm text-zinc-500">
          {t('config.design.font_hint', 'Nom de família tipogràfica de Google Fonts. Si el nom no existeix, es fa servir la tipografia per defecte sense trencar la pàgina.')}
        </p>
        <div>
          <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.design.font_headline', 'Tipografia de títols')}</label>
          <input value={fontHeadline} onChange={(e) => setFont('headline', e.target.value)}
            placeholder="Bodoni Moda, Georgia, serif"
            className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
        </div>
        <div>
          <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.design.font_body', 'Tipografia de text')}</label>
          <input value={fontBody} onChange={(e) => setFont('body', e.target.value)}
            placeholder="Hanken Grotesk, system-ui, sans-serif"
            className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={saving}>{saving ? t('common.saving') : t('config.save_changes', 'Desar canvis')}</Button>
        <button type="button" onClick={resetDefaults} className="text-xs text-zinc-500 hover:text-zinc-700">
          {t('config.design.reset', 'Restaurar valors per defecte')}
        </button>
        {saved && !saving && <span className="text-xs text-green-600">{t('subscriptions.config.saved', 'Desat')}</span>}
      </div>
    </form>
  );
}

function CustomCssPanel({ config, onSaved, sendPreview }) {
  const t = useT();
  const [css, setCss] = useState(config.custom_css || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  function onChangeCss(value) {
    setCss(value);
    sendPreview({ type: 'custom-css', css: value });
  }

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    setSaved(false);
    const r = await authFetch('/admin/configuracio/custom-css', {
      method: 'PATCH',
      body: JSON.stringify({ custom_css: css || null }),
    });
    setSaving(false);
    if (r.ok) {
      setSaved(true);
      onSaved();
    } else {
      setError((await r.json()).detail || t('config.save_error', 'Error desant'));
    }
  }

  return (
    <form onSubmit={save} className="space-y-5">
      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6 space-y-3">
        <p className="text-sm text-zinc-500">
          {t('config.css.hint', "Per a retocs que els colors/tipografia de \"Colors i tipografia\" no cobreixin. Pensat per a qui sap CSS o per al/la dissenyador/a que hagis contractat — no s'accepten @import ni @media en aquesta primera versió.")}
        </p>
        <textarea
          value={css}
          onChange={(e) => onChangeCss(e.target.value)}
          rows={16}
          placeholder=".hero { letter-spacing: 0.02em; }"
          spellCheck={false}
          className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-zinc-900"
        />
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={saving}>{saving ? t('common.saving') : t('config.save_changes', 'Desar canvis')}</Button>
        {saved && !saving && <span className="text-xs text-green-600">{t('subscriptions.config.saved', 'Desat')}</span>}
      </div>
    </form>
  );
}
