'use client';

// Llista/alta de `Page` (árbol constructible, ver
// docs/ARQUITECTURA_DISENY_FIGMA.md) — mismo patrón que admin/pagines/page.jsx
// (que gestiona el sistema legado `Pagina`), pero contra /admin/pages. Los
// dos sistemas conviven hasta la Fase 5 (retirada), ver §3e del documento.
import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { authFetch } from '../../lib/auth';
import MIcon from '../../../components/ui/m-icon';

function slugify(nom) {
  return nom.toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

// Pàgines del sistema: sempre visibles, es "creen soles" en obrir-les per
// primer cop (mateix criteri que una plantilla de tema, no un contingut
// lliure) — a diferència de les pàgines pròpies, que l'admin dona d'alta a
// mà. El slug exacte és el que [locale]/page.jsx i
// [locale]/cataleg/page.jsx comproven per substituir la implementació de
// sempre (coexistència, ver docs/ARQUITECTURA_DISENY_FIGMA.md). "Fitxa de
// producte" encara no hi és: és una plantilla per item (dades en viu per
// disc), no una pàgina única — mecanisme pendent, ver bitácora "fuera de
// fases".
const SYSTEM_PAGES = [
  { slug: 'home', label: 'Home', description: 'La portada de la botiga (/)', icon: 'home' },
  { slug: 'cataleg', label: 'Catàleg', description: 'El catàleg amb filtres (/cataleg)', icon: 'grid_view' },
];

export default function EditorPaginesPage() {
  const router = useRouter();
  const [pages, setPages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newSlug, setNewSlug] = useState('');
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  const [deleting, setDeleting] = useState(null);
  const [creatingSystemSlug, setCreatingSystemSlug] = useState(null);
  const [systemErr, setSystemErr] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await authFetch('/admin/pages');
      setPages(await r.json());
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function createPage() {
    if (!newSlug.trim()) { setErr('El slug és obligatori'); return; }
    setSaving(true); setErr('');
    try {
      const r = await authFetch('/admin/pages', {
        method: 'POST',
        body: JSON.stringify({ slug: slugify(newSlug) }),
      });
      const body = await r.json();
      if (!r.ok) { setErr(body.detail || 'Error en crear la pàgina'); return; }
      setNewSlug('');
      setCreating(false);
      await load();
    } finally { setSaving(false); }
  }

  // El home, a diferència del catàleg, sí que té un equivalent directe al
  // sistema vell (la llista de HomeBlock del tenant) — es porta tal qual
  // com a `HomeBlockNode` (ver pageEditor/nodes/HomeBlockNode.jsx) perquè
  // en obrir "Home" per primer cop es vegi exactament el que ja hi ha
  // publicat avui, no un llenç buit. El catàleg no en té (no és una llista
  // de blocs), es queda buit com fins ara.
  //
  // Llança en cas d'error en lloc de tornar `null` en silenci (com feia
  // abans): un fallo silenciós aquí acaba creant una `Page` buida sense
  // cap avís — exactament el bug real trobat en viu (la sessió de l'admin
  // no tenia accés a /admin/home-blocks en aquell moment i ningú se'n va
  // assabentar fins revisar la BD a mà).
  async function buildHomeDraftTreeFromLegacyBlocks() {
    const r = await authFetch('/admin/home-blocks');
    if (!r.ok) throw new Error(`GET /admin/home-blocks -> ${r.status}`);
    const blocks = await r.json();
    const enabled = blocks.filter((b) => b.enabled).sort((a, b) => a.position - b.position);
    if (enabled.length === 0) return null; // no hi ha res a portar — vàlid crear-la buida
    return {
      id: 'ROOT', type: 'Stack',
      props: { direction: { base: 'column' }, gap: { base: 0 } },
      style: {},
      children: enabled.map((b) => ({
        id: `legacy${b.id}`,
        type: 'HomeBlockNode',
        props: { block_type: b.block_type, block_props: b.props || {} },
        style: {},
        children: [],
      })),
    };
  }

  async function createSystemPage(slug) {
    setCreatingSystemSlug(slug);
    setSystemErr('');
    try {
      let draftTree = null;
      if (slug === 'home') {
        try {
          draftTree = await buildHomeDraftTreeFromLegacyBlocks();
        } catch (e) {
          setSystemErr(`No s'ha pogut llegir el home actual (${e.message}) — torna-ho a provar.`);
          return;
        }
      }
      const r = await authFetch('/admin/pages', { method: 'POST', body: JSON.stringify({ slug }) });
      if (!r.ok && r.status !== 409) { // 409 = ja existia (carrera improbable), s'obre igualment
        setSystemErr(`No s'ha pogut crear la pàgina (${r.status})`);
        return;
      }
      if (draftTree) {
        const pr = await authFetch(`/admin/pages/${slug}`, { method: 'PATCH', body: JSON.stringify({ draft_tree: draftTree }) });
        if (!pr.ok) {
          setSystemErr("La pàgina s'ha creat però no s'ha pogut omplir amb el contingut actual — entra-hi i revisa-ho.");
        }
      }
      router.push(`/admin/editor-pagines/${slug}`);
    } finally { setCreatingSystemSlug(null); }
  }

  // Recuperació manual si el "Dissenyar" inicial va fallar en silenci (el
  // bug real trobat en viu, ver comentari de buildHomeDraftTreeFromLegacyBlocks
  // més amunt) i la `Page` "home" ha quedat creada però buida — sense
  // haver de tocar la BD a mà cada cop.
  async function reseedHomePage() {
    setCreatingSystemSlug('home');
    setSystemErr('');
    try {
      const draftTree = await buildHomeDraftTreeFromLegacyBlocks();
      if (!draftTree) { setSystemErr('No hi ha cap bloc actiu al home actual per portar.'); return; }
      const r = await authFetch('/admin/pages/home', { method: 'PATCH', body: JSON.stringify({ draft_tree: draftTree }) });
      if (!r.ok) { setSystemErr(`No s'ha pogut omplir la pàgina (${r.status})`); return; }
      await load();
    } catch (e) {
      setSystemErr(`No s'ha pogut llegir el home actual (${e.message})`);
    } finally { setCreatingSystemSlug(null); }
  }

  async function deletePage(slug) {
    if (!confirm(`Eliminar la pàgina "${slug}"? Aquesta acció no es pot desfer.`)) return;
    setDeleting(slug);
    try {
      await authFetch(`/admin/pages/${slug}`, { method: 'DELETE' });
      await load();
    } finally { setDeleting(null); }
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-on-surface">Editor visual (beta)</h1>
          <p className="text-sm text-secondary-foreground mt-0.5">
            Dissenya les pàgines del sistema (home, catàleg...) o crea pàgines pròpies noves.
          </p>
        </div>
        <button
          onClick={() => setCreating((v) => !v)}
          className="flex items-center gap-1.5 bg-primary text-white text-sm px-4 py-2 rounded-xl hover:opacity-90 transition-colors"
        >
          <MIcon name="add" size={15} /> Nova pàgina
        </button>
      </div>

      {creating && (
        <div className="bg-card rounded-2xl border border-outline-variant p-6 mb-6 shadow-sm">
          <label className="block text-xs font-medium text-on-surface-variant mb-1">Slug (URL)</label>
          <div className="flex items-center border border-outline-variant rounded-xl overflow-hidden focus-within:ring-2 focus-within:ring-primary mb-3">
            <span className="px-2 text-secondary-foreground text-xs border-r border-outline-variant bg-surface-container-high py-2">/</span>
            <input
              value={newSlug}
              onChange={(e) => setNewSlug(e.target.value)}
              className="flex-1 px-3 py-2 text-sm focus:outline-none"
              placeholder="sobre-nosaltres"
            />
          </div>
          {err && <p className="text-red-500 text-sm mb-3">{err}</p>}
          <div className="flex gap-2">
            <button onClick={createPage} disabled={saving}
              className="bg-primary text-white text-sm px-5 py-2 rounded-xl hover:opacity-90 disabled:opacity-50 transition-colors">
              {saving ? 'Creant…' : 'Crear pàgina'}
            </button>
            <button onClick={() => { setCreating(false); setErr(''); }}
              className="text-sm px-4 py-2 rounded-xl border border-outline-variant hover:bg-surface-container-high transition-colors">
              Cancel·lar
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <p className="text-secondary-foreground text-sm">Carregant…</p>
      ) : (
        <>
          <h2 className="text-xs font-semibold uppercase tracking-wide text-secondary-foreground mb-2">Pàgines del sistema</h2>
          {systemErr && <p className="text-red-500 text-sm mb-2">{systemErr}</p>}
          <div className="flex flex-col gap-2 mb-8">
            {SYSTEM_PAGES.map((sys) => {
              const existing = pages.find((p) => p.slug === sys.slug);
              if (existing) {
                const isEmptyHome = sys.slug === 'home' && Object.keys(existing.draft_tree || {}).length === 0;
                return (
                  <PageRow key={sys.slug} p={existing} icon={sys.icon} onDelete={deletePage} deleting={deleting}
                    extraAction={isEmptyHome ? (
                      <button onClick={reseedHomePage} disabled={creatingSystemSlug === 'home'}
                        className="text-xs px-2.5 py-1.5 rounded-lg border border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100 disabled:opacity-50 transition-colors shrink-0">
                        {creatingSystemSlug === 'home' ? 'Omplint…' : 'Buida — reomplir amb el contingut actual'}
                      </button>
                    ) : null}
                  />
                );
              }
              return (
                <div key={sys.slug} className="flex items-center gap-3 bg-card rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] px-4 py-3 border border-dashed border-outline-variant">
                  <MIcon name={sys.icon} size={16} className="text-secondary-foreground shrink-0" />
                  <div className="flex-1 min-w-0">
                    <span className="font-medium text-on-surface text-sm">{sys.label}</span>
                    <span className="ml-2 text-xs text-secondary-foreground">{sys.description}</span>
                    <span className="ml-2 text-[10px] bg-surface-container-high text-secondary-foreground px-1.5 py-0.5 rounded-full">
                      Encara amb el disseny de sempre
                    </span>
                  </div>
                  <button onClick={() => createSystemPage(sys.slug)} disabled={creatingSystemSlug === sys.slug}
                    className="text-sm px-3 py-1.5 rounded-xl border border-outline-variant hover:bg-surface-container-high disabled:opacity-50 transition-colors shrink-0">
                    {creatingSystemSlug === sys.slug ? 'Creant…' : 'Dissenyar'}
                  </button>
                </div>
              );
            })}
          </div>

          <h2 className="text-xs font-semibold uppercase tracking-wide text-secondary-foreground mb-2">Pàgines pròpies</h2>
          <div className="flex flex-col gap-2">
            {pages.filter((p) => !SYSTEM_PAGES.some((sys) => sys.slug === p.slug)).map((p) => (
              <PageRow key={p.id} p={p} onDelete={deletePage} deleting={deleting} />
            ))}
            {pages.filter((p) => !SYSTEM_PAGES.some((sys) => sys.slug === p.slug)).length === 0 && (
              <p className="text-secondary-foreground text-sm py-8 text-center">Cap pàgina pròpia creada. Afegeix-ne una!</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function PageRow({ p, icon, onDelete, deleting, extraAction }) {
  return (
    <div className="flex items-center gap-3 bg-card rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] px-4 py-3">
      {icon && <MIcon name={icon} size={16} className="text-secondary-foreground shrink-0" />}
      <div className="flex-1 min-w-0">
        <span className="font-medium text-on-surface text-sm">/{p.slug}</span>
        <span className={`ml-2 text-[10px] px-1.5 py-0.5 rounded-full ${p.published_tree ? 'bg-green-100 text-green-700' : 'bg-surface-container-high text-secondary-foreground'}`}>
          {p.published_tree ? 'Publicada' : 'Esborrany'}
        </span>
        {p.requires_nodes?.length > 0 && (
          <span className="ml-2 text-[10px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded-full">
            requereix: {p.requires_nodes.join(', ')}
          </span>
        )}
      </div>
      {extraAction}
      <div className="flex items-center gap-1 shrink-0">
        <Link href={`/admin/editor-pagines/${p.slug}`}
          className="p-1.5 text-secondary-foreground hover:text-on-surface-variant rounded-lg hover:bg-surface-container-high transition-colors">
          <MIcon name="edit" size={14} />
        </Link>
        <button onClick={() => onDelete(p.slug)} disabled={deleting === p.slug}
          className="p-1.5 text-secondary-foreground hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors">
          <MIcon name="delete" size={14} />
        </button>
      </div>
    </div>
  );
}
