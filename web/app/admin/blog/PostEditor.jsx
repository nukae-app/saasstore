'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import MIcon from '../../../components/ui/m-icon';
import { authFetch } from '../../lib/auth';

function slugify(text) {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .slice(0, 80);
}

const EMPTY = {
  slug: '', title: '', content: '', language: 'ca', published_at: '', pagina_ids: [],
};

export default function PostEditor({ initial = null }) {
  const isEdit = !!initial;
  const router = useRouter();
  const [form, setForm] = useState(initial ? {
    slug: initial.slug,
    title: initial.title,
    content: initial.content,
    language: initial.language,
    published_at: initial.published_at
      ? new Date(initial.published_at).toISOString().slice(0, 16)
      : '',
    pagina_ids: (initial.pagines || []).map(p => p.id),
  } : EMPTY);
  const [paginesDisponibles, setPaginesDisponibles] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [preview, setPreview] = useState(false);
  const [autoSlug, setAutoSlug] = useState(!isEdit);

  useEffect(() => {
    authFetch('/api/admin/pagines').then(r => r.json()).then(ps => {
      setPaginesDisponibles(ps.filter(p => p.type === 'llista-posts'));
    }).catch(() => {});
  }, []);

  function set(k, v) { setForm(f => ({ ...f, [k]: v })); }

  function handleTitleChange(v) {
    set('title', v);
    if (autoSlug) set('slug', slugify(v));
  }

  async function handleSave(publish = false) {
    setSaving(true);
    setError('');
    try {
      const payload = { ...form, pagina_ids: form.pagina_ids };
      if (publish && !payload.published_at) {
        payload.published_at = new Date().toISOString();
      }
      if (!payload.published_at) payload.published_at = null;

      const res = await authFetch(
        isEdit ? `/admin/posts/${initial.slug}` : '/admin/posts',
        { method: isEdit ? 'PUT' : 'POST', body: JSON.stringify(payload) }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || `Error ${res.status}`);
        return;
      }
      router.push('/admin/blog');
      router.refresh();
    } finally {
      setSaving(false);
    }
  }

  const wordCount = form.content.replace(/<[^>]+>/g, ' ').split(/\s+/).filter(Boolean).length;

  return (
    <div className="space-y-5 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold">{isEdit ? 'Editar post' : 'Nou post'}</h1>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setPreview(v => !v)}
            className="flex items-center gap-1.5 text-sm border border-outline-variant text-on-surface-variant px-3 py-2 rounded-lg hover:bg-surface-container-high transition-colors"
          >
            {preview ? <MIcon name="visibility_off" size={13} /> : <MIcon name="visibility" size={13} />}
            {preview ? 'Editar' : 'Previsualitzar'}
          </button>
          {!form.published_at && (
            <button
              onClick={() => handleSave(false)}
              disabled={saving || !form.title || !form.slug}
              className="flex items-center gap-1.5 text-sm border border-outline-variant text-on-surface-variant px-4 py-2 rounded-lg hover:bg-surface-container-high transition-colors disabled:opacity-50"
            >
              {saving ? <MIcon name="progress_activity" size={13} className="animate-spin" /> : <MIcon name="save" size={13} />}
              Guardar esborrany
            </button>
          )}
          <button
            onClick={() => handleSave(true)}
            disabled={saving || !form.title || !form.slug || !form.content}
            className="flex items-center gap-1.5 text-sm bg-primary hover:opacity-90 text-white px-4 py-2 rounded-lg transition-colors disabled:opacity-50 font-medium"
          >
            {saving ? <MIcon name="progress_activity" size={13} className="animate-spin" /> : <MIcon name="save" size={13} />}
            {form.published_at ? 'Guardar canvis' : 'Publicar'}
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-4 py-3">
          <MIcon name="error" size={14} /> {error}
        </div>
      )}

      <div className="grid md:grid-cols-3 gap-5">
        {/* Main fields */}
        <div className="md:col-span-2 space-y-4">
          {/* Títol */}
          <div>
            <label className="block text-xs font-medium text-on-surface-variant mb-1.5">Títol *</label>
            <input
              type="text"
              value={form.title}
              onChange={e => handleTitleChange(e.target.value)}
              placeholder="Títol del post…"
              className="w-full border border-outline-variant rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary font-medium"
            />
          </div>

          {/* Contingut */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-medium text-on-surface-variant">Contingut HTML *</label>
              <span className="text-xs text-secondary-foreground">{wordCount} paraules</span>
            </div>
            {preview ? (
              <div
                className="blog-content min-h-[400px] bg-card border border-outline-variant rounded-xl p-5 overflow-auto"
                dangerouslySetInnerHTML={{ __html: form.content || '<p class="text-secondary-foreground">Sense contingut…</p>' }}
              />
            ) : (
              <textarea
                value={form.content}
                onChange={e => set('content', e.target.value)}
                placeholder="<p>Contingut en HTML…</p>"
                rows={20}
                className="w-full border border-outline-variant rounded-xl px-3 py-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary resize-y"
              />
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Slug */}
          <div>
            <label className="block text-xs font-medium text-on-surface-variant mb-1.5">Slug (URL) *</label>
            <input
              type="text"
              value={form.slug}
              onChange={e => { setAutoSlug(false); set('slug', e.target.value); }}
              placeholder="el-meu-post"
              className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <p className="text-xs text-secondary-foreground mt-1">/blog/{form.slug || '…'}</p>
          </div>

          {/* Idioma */}
          <div>
            <label className="block text-xs font-medium text-on-surface-variant mb-1.5">Idioma</label>
            <div className="flex gap-2">
              {[{ code: 'ca', label: 'Català' }, { code: 'es', label: 'Castellano' }].map(({ code, label }) => (
                <button
                  key={code}
                  type="button"
                  onClick={() => set('language', code)}
                  className={`flex-1 py-2 text-xs rounded-lg border transition-colors ${
                    form.language === code
                      ? 'border-primary bg-surface-container-high text-on-surface font-medium'
                      : 'border-outline-variant text-secondary-foreground hover:border-outline-variant'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Data de publicació */}
          <div>
            <label className="block text-xs font-medium text-on-surface-variant mb-1.5">
              Data de publicació
              <span className="text-secondary-foreground font-normal ml-1">(buit = esborrany)</span>
            </label>
            <input
              type="datetime-local"
              value={form.published_at}
              onChange={e => set('published_at', e.target.value)}
              className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
            {form.published_at && (
              <button
                type="button"
                onClick={() => set('published_at', '')}
                className="text-xs text-secondary-foreground hover:text-red-500 mt-1 transition-colors"
              >
                Tornar a esborrany
              </button>
            )}
          </div>

          {/* Pàgines */}
          {paginesDisponibles.length > 0 && (
            <div>
              <label className="block text-xs font-medium text-on-surface-variant mb-1.5">Apareix a</label>
              <div className="flex flex-col gap-1.5">
                {paginesDisponibles.map(p => {
                  const checked = form.pagina_ids.includes(p.id);
                  return (
                    <label key={p.id} className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-colors ${checked ? 'border-primary bg-surface-container-high text-on-surface' : 'border-outline-variant text-on-surface-variant hover:border-outline-variant'}`}>
                      <input type="checkbox" checked={checked}
                        onChange={e => {
                          setForm(f => ({
                            ...f,
                            pagina_ids: e.target.checked
                              ? [...f.pagina_ids, p.id]
                              : f.pagina_ids.filter(id => id !== p.id),
                          }));
                        }}
                        className="accent-zinc-900" />
                      <span className="text-xs font-medium">{p.name}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          {/* Status */}
          <div className={`rounded-xl px-4 py-3 text-xs ${form.published_at ? 'bg-emerald-50 border border-emerald-200 text-emerald-700' : 'bg-amber-50 border border-amber-200 text-amber-700'}`}>
            {form.published_at ? '● Publicat' : '● Esborrany — no visible al web'}
          </div>
        </div>
      </div>
    </div>
  );
}
