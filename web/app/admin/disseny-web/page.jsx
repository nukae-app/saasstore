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
import CuratorSelectionPropsForm from '../../../components/store/blocks/CuratorSelectionPropsForm';
import TextPropsForm from '../../../components/store/blocks/TextPropsForm';
import TestimonialsPropsForm from '../../../components/store/blocks/TestimonialsPropsForm';
import GalleryPropsForm from '../../../components/store/blocks/GalleryPropsForm';
import FaqPropsForm from '../../../components/store/blocks/FaqPropsForm';
import BannerPropsForm from '../../../components/store/blocks/BannerPropsForm';
import BrandStripPropsForm from '../../../components/store/blocks/BrandStripPropsForm';
import FeatureGridPropsForm from '../../../components/store/blocks/FeatureGridPropsForm';
import VideoPropsForm from '../../../components/store/blocks/VideoPropsForm';
import FontPickerDialog from '../../../components/store/blocks/FontPickerDialog';

const PROPS_FORMS = {
  hero: HeroPropsForm,
  carousel: CarouselPropsForm,
  curator_selection: CuratorSelectionPropsForm,
  text: TextPropsForm,
  testimonials: TestimonialsPropsForm,
  gallery: GalleryPropsForm,
  faq: FaqPropsForm,
  banner: BannerPropsForm,
  brand_strip: BrandStripPropsForm,
  feature_grid: FeatureGridPropsForm,
  video: VideoPropsForm,
};

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

// Preajustos d'aparença — valors CSS ja resolts (ver api/app/schemas/configuracio.py::
// ThemeTokens): cada component del storefront declara el seu propi fallback,
// així que mentre l'admin no en triï cap, l'aspecte no canvia.
const RADIUS_CARD_OPTIONS = [
  { label: 'Cap', value: '4px' },
  { label: 'Suau', value: '12px' },
  { label: 'Rodó', value: '24px' },
  { label: 'Molt rodó', value: '40px' },
];
const RADIUS_BUTTON_OPTIONS = [
  { label: 'Rectangular', value: '4px' },
  { label: 'Arrodonit', value: '16px' },
  { label: 'Píndola', value: '9999px' },
];
const SHADOW_OPTIONS = [
  { label: 'Cap', value: 'none' },
  { label: 'Suau', value: '0 2px 24px -6px rgba(15,23,42,0.08)' },
  { label: 'Marcada', value: '0 20px 40px -8px rgba(15,23,42,0.25)' },
];
const CONTENT_WIDTH_OPTIONS = [
  { label: 'Estreta', value: '960px' },
  { label: 'Normal', value: '1280px' },
  { label: 'Completa', value: '1600px' },
];
const BORDER_CARD_ON = '1px solid var(--border)';
const IMAGE_TREATMENT_OPTIONS = [
  { label: 'Color', value: 'none' },
  { label: 'Blanc i negre', value: 'grayscale(100%)' },
];
const EYEBROW_STYLE_OPTIONS = [
  { label: 'MAJÚSCULES', value: 'uppercase' },
  { label: 'Normal', value: 'none' },
];
const SPACING_DENSITY_OPTIONS = [
  { label: 'Compacte', value: '48px' },
  { label: 'Normal', value: '96px' },
  { label: 'Espaiós', value: '128px' },
];
const SECTION_DIVIDER_OPTIONS = [
  { label: 'Cap', value: 'none' },
  { label: 'Línia', value: '1px solid var(--border)' },
];

function PresetField({ label, options, value, onChange }) {
  return (
    <div>
      <label className="block text-sm font-medium text-zinc-700 mb-2">{label}</label>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={`text-xs font-medium px-3 py-1.5 rounded-lg border transition-colors ${
              value === opt.value ? 'border-zinc-900 bg-zinc-900 text-white' : 'border-zinc-200 text-zinc-600 hover:border-zinc-300'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}

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
  if (block.block_type === 'text') return block.props?.heading || block.props?.body || '(buit)';
  if (block.block_type === 'testimonials') return `${block.props?.items?.length || 0} testimoni(s)`;
  if (block.block_type === 'curator_selection') return `#${block.props?.etiqueta_slug || '—'}`;
  if (block.block_type === 'gallery') return `${block.props?.items?.length || 0} imatge(s)`;
  if (block.block_type === 'faq') return `${block.props?.items?.length || 0} pregunta(es)`;
  if (block.block_type === 'banner') return block.props?.text || '(buit)';
  if (block.block_type === 'brand_strip') return `${block.props?.items?.length || 0} logo(s)`;
  if (block.block_type === 'feature_grid') return `${block.props?.items?.length || 0} element(s)`;
  if (block.block_type === 'video') return block.props?.heading || block.props?.video_url || '(sense enllaç)';
  return meta?.description || '';
}

// Bloc afegit al esborrany però encara no creat al servidor: se li assigna
// un id temporal (string) perquè React el pugui fer servir de key i perquè
// el sheet d'edició el pugui referenciar, però mai es manda a cap PATCH —
// només es POSTeja de veritat des de saveAll().
function tempBlockId() {
  return `nou-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function BlocksPanel({ sendPreview }) {
  // `saved` és l'última fotografia coneguda del servidor (per calcular què
  // ha canviat en desar); `draft` és la còpia editable — cap acció d'aquest
  // panell (afegir, esborrar, arrossegar, activar/desactivar, editar props)
  // toca el servidor fins que es prem "Guardar canvis". Això evita dependre
  // de la previsualització en directe per a res crític: un bloc nou o buit
  // encara no existeix al DOM de l'iframe (el seu propi component retorna
  // null sense contingut), així que no hi ha res a "pedaçar" en directe —
  // l'única manera fiable de veure'l és desar de veritat i recarregar.
  const [saved, setSaved] = useState([]);
  const [draft, setDraft] = useState([]);
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editingProps, setEditingProps] = useState({});
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  const dragIdRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await authFetch('/admin/home-blocks');
      const data = await r.json();
      setSaved(data);
      setDraft(data.map((b) => ({ ...b })));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const dirty = JSON.stringify(draft) !== JSON.stringify(saved);

  function addBlock(type) {
    const block = { id: tempBlockId(), block_type: type, enabled: true, props: {}, _new: true };
    setDraft((prev) => [...prev, block]);
    setAddOpen(false);
    if (BLOCK_META[type]?.editable) {
      setEditingId(block.id);
      setEditingProps({});
      setErr('');
    }
  }

  function openEdit(block) {
    setEditingId(block.id);
    setEditingProps(block.props || {});
    setErr('');
  }

  function applyEdit() {
    setDraft((prev) => prev.map((b) => (b.id === editingId ? { ...b, props: editingProps } : b)));
    setEditingId(null);
  }

  function toggleEnabled(block) {
    setDraft((prev) => prev.map((b) => (b.id === block.id ? { ...b, enabled: !b.enabled } : b)));
  }

  function deleteBlock(block) {
    setDraft((prev) => prev.filter((b) => b.id !== block.id));
  }

  function discardChanges() {
    setDraft(saved.map((b) => ({ ...b })));
    setEditingId(null);
    setErr('');
  }

  function onDragStart(id) { dragIdRef.current = id; }
  function onDragOver(e) { e.preventDefault(); }

  function onDrop(targetId) {
    const dragId = dragIdRef.current;
    dragIdRef.current = null;
    if (dragId == null || dragId === targetId) return;
    setDraft((prev) => {
      const list = [...prev];
      const fromIdx = list.findIndex((b) => b.id === dragId);
      const toIdx = list.findIndex((b) => b.id === targetId);
      if (fromIdx === -1 || toIdx === -1) return prev;
      const [moved] = list.splice(fromIdx, 1);
      list.splice(toIdx, 0, moved);
      return list;
    });
  }

  // Persisteix tot l'esborrany d'un cop: esborra el que s'ha tret,
  // crea el que és nou, actualitza props/enabled del que ha canviat i
  // finalment envia l'ordre complet — en aquest ordre perquè el reorder
  // final ja pugui fer servir els ids reals dels blocs acabats de crear.
  async function saveAll() {
    setSaving(true);
    setErr('');
    try {
      const draftIds = new Set(draft.map((b) => b.id));
      for (const b of saved) {
        if (!draftIds.has(b.id)) {
          await authFetch(`/admin/home-blocks/${b.id}`, { method: 'DELETE' });
        }
      }

      const idMap = {};
      for (const b of draft) {
        if (!b._new) continue;
        const r = await authFetch('/admin/home-blocks', {
          method: 'POST',
          body: JSON.stringify({ block_type: b.block_type, props: b.props || {} }),
        });
        if (!r.ok) { const body = await r.json(); throw new Error(typeof body.detail === 'string' ? body.detail : 'Error en crear un bloc'); }
        const created = await r.json();
        idMap[b.id] = created.id;
      }

      const savedById = Object.fromEntries(saved.map((b) => [b.id, b]));
      for (const b of draft) {
        if (b._new) continue;
        const before = savedById[b.id];
        if (!before) continue;
        const propsChanged = JSON.stringify(before.props) !== JSON.stringify(b.props);
        const enabledChanged = before.enabled !== b.enabled;
        if (!propsChanged && !enabledChanged) continue;
        const body = {};
        if (propsChanged) body.props = b.props;
        if (enabledChanged) body.enabled = b.enabled;
        const r = await authFetch(`/admin/home-blocks/${b.id}`, { method: 'PATCH', body: JSON.stringify(body) });
        if (!r.ok) { const respBody = await r.json(); throw new Error(typeof respBody.detail === 'string' ? respBody.detail : 'Error en desar un bloc'); }
      }

      const order = draft.map((b, i) => ({ id: idMap[b.id] || b.id, position: i + 1 }));
      await authFetch('/admin/home-blocks/reorder', { method: 'PATCH', body: JSON.stringify({ order }) });

      await load();
      sendPreview({ type: 'reload' });
    } catch (e) {
      setErr(e.message || 'Error desant els canvis');
    } finally {
      setSaving(false);
    }
  }

  const availableToAdd = BLOCK_TYPES.filter((type) => type === 'carousel' || !draft.some((b) => b.block_type === type));
  const editingBlock = draft.find((b) => b.id === editingId) || null;
  const EditForm = editingBlock ? PROPS_FORMS[editingBlock.block_type] : null;

  return (
    <div>
      <div className="flex items-center justify-between mb-4 gap-3">
        <p className="text-sm text-zinc-500">Arrossega per reordenar els blocs del home. La previsualització s&apos;actualitza en prémer &quot;Guardar canvis&quot;.</p>
        <button
          onClick={() => { setErr(''); setAddOpen(true); }}
          className="flex items-center gap-1.5 bg-white border border-zinc-200 text-zinc-700 text-sm px-4 py-2 rounded-xl hover:bg-zinc-50 transition-colors shrink-0"
        >
          <Plus size={15} /> Afegir bloc
        </button>
      </div>

      {loading ? (
        <p className="text-zinc-400 text-sm">Carregant…</p>
      ) : (
        <div className="flex flex-col gap-2">
          {draft.map((block) => {
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
                    {block._new && <span className="text-[10px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded-full">nou</span>}
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
                    className="p-1.5 text-zinc-300 hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            );
          })}
          {draft.length === 0 && (
            <p className="text-zinc-400 text-sm py-8 text-center">Cap bloc configurat. La pàgina d&apos;inici es mostrarà buida — afegeix-ne un!</p>
          )}
        </div>
      )}

      {err && <p className="text-red-500 text-xs mt-3">{err}</p>}

      <div className="flex items-center gap-3 mt-5 pt-5 border-t border-zinc-200">
        <button
          onClick={saveAll}
          disabled={!dirty || saving}
          className="bg-zinc-900 text-white text-sm px-5 py-2 rounded-xl hover:bg-zinc-700 disabled:opacity-40 disabled:hover:bg-zinc-900 transition-colors"
        >
          {saving ? 'Desant…' : 'Guardar canvis'}
        </button>
        {dirty && !saving && (
          <>
            <span className="text-xs text-amber-600">Tens canvis sense desar</span>
            <button onClick={discardChanges} className="text-xs text-zinc-400 hover:text-zinc-700">
              Descartar
            </button>
          </>
        )}
      </div>

      {/* Afegir bloc */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Afegir bloc</DialogTitle>
            <DialogDescription>Tria un tipus de bloc per afegir-lo al final del home. No es desa fins que premis &quot;Guardar canvis&quot;.</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-1 gap-2">
            {availableToAdd.map((type) => {
              const meta = BLOCK_META[type];
              return (
                <button
                  key={type}
                  onClick={() => addBlock(type)}
                  className="flex flex-col items-start gap-0.5 p-3 rounded-xl border border-zinc-200 hover:border-zinc-900 text-left transition-colors"
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

      {/* Editar props (encara dins l'esborrany, no desa al servidor) */}
      <Sheet open={!!editingBlock} onOpenChange={(open) => { if (!open) setEditingId(null); }}>
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
          <SheetFooter className="mt-6">
            <button
              onClick={() => setEditingId(null)}
              className="text-sm px-4 py-2 rounded-xl border border-zinc-200 hover:bg-zinc-50 transition-colors"
            >
              Cancel·lar
            </button>
            <button
              onClick={applyEdit}
              className="bg-zinc-900 text-white text-sm px-5 py-2 rounded-xl hover:bg-zinc-700 transition-colors"
            >
              Aplicar
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
  const [extra, setExtra] = useState(() => ({
    radius_card: config.theme?.radius_card || '',
    radius_button: config.theme?.radius_button || '',
    shadow_card: config.theme?.shadow_card || '',
    border_card: config.theme?.border_card || '',
    content_width: config.theme?.content_width || '',
    image_treatment: config.theme?.image_treatment || '',
    eyebrow_style: config.theme?.eyebrow_style || '',
    spacing_density: config.theme?.spacing_density || '',
    section_divider: config.theme?.section_divider || '',
  }));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [pickerRole, setPickerRole] = useState(null); // null | 'headline' | 'body'

  function onFontDownloaded(newConfig) {
    setFontHeadline(newConfig.theme?.font_headline || '');
    setFontBody(newConfig.theme?.font_body || '');
    onSaved();
    // La tipografia autoallotjada és una regla @font-face nova que l'iframe
    // encara no té — un simple canvi de --font-headline no n'hi ha prou,
    // cal recarregar perquè web/app/layout.jsx la torni a injectar.
    sendPreview({ type: 'reload' });
  }

  function setColor(key, value) {
    setValues((v) => {
      const next = { ...v, [key]: value };
      sendPreview({ type: 'theme-vars', vars: { ...next, font_headline: fontHeadline, font_body: fontBody, ...extra } });
      return next;
    });
  }

  function setFont(which, value) {
    if (which === 'headline') setFontHeadline(value); else setFontBody(value);
    sendPreview({
      type: 'theme-vars',
      vars: { ...values, font_headline: which === 'headline' ? value : fontHeadline, font_body: which === 'body' ? value : fontBody, ...extra },
    });
  }

  function setExtraField(key, value) {
    setExtra((v) => {
      const next = { ...v, [key]: value };
      sendPreview({ type: 'theme-vars', vars: { ...values, font_headline: fontHeadline, font_body: fontBody, ...next } });
      return next;
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
        radius_card: extra.radius_card || null,
        radius_button: extra.radius_button || null,
        shadow_card: extra.shadow_card || null,
        border_card: extra.border_card || null,
        content_width: extra.content_width || null,
        image_treatment: extra.image_treatment || null,
        eyebrow_style: extra.eyebrow_style || null,
        spacing_density: extra.spacing_density || null,
        section_divider: extra.section_divider || null,
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
    const emptyExtra = {
      radius_card: '', radius_button: '', shadow_card: '', border_card: '', content_width: '',
      image_treatment: '', eyebrow_style: '', spacing_density: '', section_divider: '',
    };
    setValues(v);
    setFontHeadline('');
    setFontBody('');
    setExtra(emptyExtra);
    sendPreview({ type: 'theme-vars', vars: { ...v, font_headline: '', font_body: '', ...emptyExtra } });
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
          {t('config.design.font_hint', "Cerca i tria una tipografia gratuïta (es descarrega i queda allotjada al teu servidor), o escriu-la a mà si ja saps que existeix (p. ex. una del sistema).")}
        </p>
        <div>
          <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.design.font_headline', 'Tipografia de títols')}</label>
          <div className="flex gap-2">
            <input value={fontHeadline} onChange={(e) => setFont('headline', e.target.value)}
              placeholder="Bodoni Moda, Georgia, serif"
              className="flex-1 border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            <button type="button" onClick={() => setPickerRole('headline')}
              className="shrink-0 text-sm font-medium text-zinc-700 border border-zinc-300 rounded-lg px-3 py-2 hover:bg-zinc-50 transition-colors">
              Cercar…
            </button>
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.design.font_body', 'Tipografia de text')}</label>
          <div className="flex gap-2">
            <input value={fontBody} onChange={(e) => setFont('body', e.target.value)}
              placeholder="Hanken Grotesk, system-ui, sans-serif"
              className="flex-1 border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            <button type="button" onClick={() => setPickerRole('body')}
              className="shrink-0 text-sm font-medium text-zinc-700 border border-zinc-300 rounded-lg px-3 py-2 hover:bg-zinc-50 transition-colors">
              Cercar…
            </button>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6 space-y-5">
        <p className="text-sm text-zinc-500">
          Forma i textura dels blocs: targetes, botons i amplada del contingut. Si no tries res, es manté l&apos;aspecte actual.
        </p>
        <PresetField label="Radi de les targetes i imatges" options={RADIUS_CARD_OPTIONS} value={extra.radius_card} onChange={(v) => setExtraField('radius_card', v)} />
        <PresetField label="Radi dels botons" options={RADIUS_BUTTON_OPTIONS} value={extra.radius_button} onChange={(v) => setExtraField('radius_button', v)} />
        <PresetField label="Ombra de les targetes" options={SHADOW_OPTIONS} value={extra.shadow_card} onChange={(v) => setExtraField('shadow_card', v)} />
        <PresetField label="Amplada del contingut" options={CONTENT_WIDTH_OPTIONS} value={extra.content_width} onChange={(v) => setExtraField('content_width', v)} />
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-zinc-700">Vores a les targetes</p>
            <p className="text-xs text-zinc-400 mt-1 max-w-sm">Afegeix una vora fina (color &quot;Vores&quot; de la paleta) a les targetes que avui no en tenen.</p>
          </div>
          <button
            type="button"
            onClick={() => setExtraField('border_card', extra.border_card === BORDER_CARD_ON ? 'none' : BORDER_CARD_ON)}
            className={`w-10 h-5 rounded-full transition-colors relative shrink-0 ${extra.border_card === BORDER_CARD_ON ? 'bg-green-500' : 'bg-zinc-300'}`}
          >
            <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${extra.border_card === BORDER_CARD_ON ? 'left-5' : 'left-0.5'}`} />
          </button>
        </div>
        <PresetField label="Tractament de les fotos" options={IMAGE_TREATMENT_OPTIONS} value={extra.image_treatment} onChange={(v) => setExtraField('image_treatment', v)} />
        <PresetField label="Estil de les etiquetes petites" options={EYEBROW_STYLE_OPTIONS} value={extra.eyebrow_style} onChange={(v) => setExtraField('eyebrow_style', v)} />
        <PresetField label="Densitat de l'espaiat entre seccions" options={SPACING_DENSITY_OPTIONS} value={extra.spacing_density} onChange={(v) => setExtraField('spacing_density', v)} />
        <PresetField label="Separador entre seccions" options={SECTION_DIVIDER_OPTIONS} value={extra.section_divider} onChange={(v) => setExtraField('section_divider', v)} />
      </div>

      <FontPickerDialog
        open={!!pickerRole}
        onOpenChange={(open) => { if (!open) setPickerRole(null); }}
        role={pickerRole || 'headline'}
        onSelected={onFontDownloaded}
      />

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
