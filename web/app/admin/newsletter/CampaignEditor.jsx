'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Save, Code, PenLine, Loader2, AlertCircle, Send, Mail } from 'lucide-react';
import { authFetch } from '../../lib/auth';
import RichTextEditor from './RichTextEditor';

const EMPTY = { assumpte: '', contingut_html: '', idioma: 'ca' };

export default function CampaignEditor({ initial = null }) {
  const isEdit = !!initial;
  const isDraft = !initial || initial.estat === 'esborrany';
  const router = useRouter();
  const [campaign, setCampaign] = useState(initial);
  const [form, setForm] = useState(initial ? {
    assumpte: initial.assumpte,
    contingut_html: initial.contingut_html,
    idioma: initial.idioma,
  } : EMPTY);
  const [recipients, setRecipients] = useState(null);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [testEmail, setTestEmail] = useState('');
  const [sendingTest, setSendingTest] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [showHtml, setShowHtml] = useState(false);

  useEffect(() => {
    authFetch('/admin/newsletter/recipients/count').then(r => r.json()).then(d => setRecipients(d.total)).catch(() => {});
  }, []);

  // Mentre s'està enviant, fem poll de l'estat per veure el progrés
  useEffect(() => {
    if (!campaign || campaign.estat !== 'enviant') return;
    const id = setInterval(async () => {
      const res = await authFetch(`/admin/newsletter/${campaign.id}`);
      if (res.ok) setCampaign(await res.json());
    }, 3000);
    return () => clearInterval(id);
  }, [campaign]);

  function set(k, v) { setForm(f => ({ ...f, [k]: v })); }

  async function handleSave() {
    setSaving(true);
    setError('');
    try {
      const res = await authFetch(
        isEdit ? `/admin/newsletter/${campaign.id}` : '/admin/newsletter',
        { method: isEdit ? 'PATCH' : 'POST', body: JSON.stringify(form) }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || `Error ${res.status}`);
        return;
      }
      const saved = await res.json();
      if (!isEdit) {
        router.push(`/admin/newsletter/${saved.id}`);
        return;
      }
      setCampaign(saved);
      setNotice('Desat.');
      setTimeout(() => setNotice(''), 2000);
    } finally {
      setSaving(false);
    }
  }

  async function handleSendTest() {
    if (!testEmail) return;
    setSendingTest(true);
    setError('');
    try {
      const res = await authFetch(`/admin/newsletter/${campaign.id}/send-test`, {
        method: 'POST',
        body: JSON.stringify({ email: testEmail }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || `Error ${res.status}`);
        return;
      }
      setNotice(`Correu de prova enviat a ${testEmail}.`);
      setTimeout(() => setNotice(''), 3000);
    } finally {
      setSendingTest(false);
    }
  }

  async function handleSendAll() {
    if (!confirm(`Enviar aquesta campanya a ${recipients ?? '?'} subscriptors? Aquesta acció no es pot desfer.`)) return;
    setSending(true);
    setError('');
    try {
      const res = await authFetch(`/admin/newsletter/${campaign.id}/send`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || `Error ${res.status}`);
        return;
      }
      const detail = await authFetch(`/admin/newsletter/${campaign.id}`);
      if (detail.ok) setCampaign(await detail.json());
    } finally {
      setSending(false);
    }
  }

  const wordCount = form.contingut_html.replace(/<[^>]+>/g, ' ').split(/\s+/).filter(Boolean).length;
  const counts = campaign?.counts;
  const total = counts ? counts.pendent + counts.enviat + counts.error : 0;

  return (
    <div className="space-y-5 max-w-4xl mx-auto">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold">{isEdit ? 'Campanya de newsletter' : 'Nova campanya'}</h1>
        {isDraft && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowHtml(v => !v)}
              className="flex items-center gap-1.5 text-sm border border-zinc-200 text-zinc-600 px-3 py-2 rounded-lg hover:bg-zinc-50 transition-colors"
            >
              {showHtml ? <PenLine size={13} /> : <Code size={13} />}
              {showHtml ? 'Editor visual' : 'Veure HTML'}
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !form.assumpte || !form.contingut_html}
              className="flex items-center gap-1.5 text-sm bg-primary hover:bg-zinc-800 text-white px-4 py-2 rounded-lg transition-colors disabled:opacity-50 font-medium"
            >
              {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
              {isEdit ? 'Desar canvis' : 'Crear esborrany'}
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-4 py-3">
          <AlertCircle size={14} /> {error}
        </div>
      )}
      {notice && (
        <div className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3">
          {notice}
        </div>
      )}

      <div className="grid md:grid-cols-3 gap-5">
        <div className="md:col-span-2 space-y-4">
          <div>
            <label className="block text-xs font-medium text-zinc-600 mb-1.5">Assumpte *</label>
            <input
              type="text"
              value={form.assumpte}
              onChange={e => set('assumpte', e.target.value)}
              disabled={!isDraft}
              placeholder="Novetats de la setmana…"
              className="w-full border border-zinc-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 font-medium disabled:bg-zinc-50 disabled:text-zinc-500"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-medium text-zinc-600">Contingut *</label>
              <span className="text-xs text-zinc-400">{wordCount} paraules</span>
            </div>
            {!isDraft ? (
              <div
                className="blog-content min-h-[400px] bg-white border border-zinc-200 rounded-xl p-5 overflow-auto"
                dangerouslySetInnerHTML={{ __html: form.contingut_html || '<p class="text-zinc-300">Sense contingut…</p>' }}
              />
            ) : showHtml ? (
              <textarea
                value={form.contingut_html}
                onChange={e => set('contingut_html', e.target.value)}
                placeholder="<p>Contingut en HTML…</p>"
                rows={20}
                className="w-full border border-zinc-200 rounded-xl px-3 py-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-zinc-900 resize-y"
              />
            ) : (
              <RichTextEditor value={form.contingut_html} onChange={v => set('contingut_html', v)} />
            )}
          </div>
        </div>

        <div className="space-y-4">
          {isDraft && (
            <div>
              <label className="block text-xs font-medium text-zinc-600 mb-1.5">Idioma</label>
              <div className="flex gap-2">
                {[{ code: 'ca', label: 'Català' }, { code: 'es', label: 'Castellano' }].map(({ code, label }) => (
                  <button
                    key={code}
                    type="button"
                    onClick={() => set('idioma', code)}
                    className={`flex-1 py-2 text-xs rounded-lg border transition-colors ${
                      form.idioma === code
                        ? 'border-zinc-900 bg-zinc-100 text-zinc-900 font-medium'
                        : 'border-zinc-200 text-zinc-500 hover:border-zinc-300'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className={`rounded-xl px-4 py-3 text-xs ${
            campaign?.estat === 'enviada' ? 'bg-emerald-50 border border-emerald-200 text-emerald-700'
            : campaign?.estat === 'enviant' ? 'bg-blue-50 border border-blue-200 text-blue-700'
            : 'bg-amber-50 border border-amber-200 text-amber-700'
          }`}>
            {campaign?.estat === 'enviada' ? '● Enviada'
              : campaign?.estat === 'enviant' ? '● Enviant…'
              : '● Esborrany — no s\'ha enviat'}
          </div>

          {campaign && total > 0 && (
            <div className="border border-zinc-200 rounded-xl p-4 space-y-2">
              <p className="text-xs font-medium text-zinc-600">Progrés</p>
              <div className="h-2 bg-zinc-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-500 transition-all"
                  style={{ width: `${((counts.enviat + counts.error) / total) * 100}%` }}
                />
              </div>
              <p className="text-xs text-zinc-500">
                {counts.enviat} enviats · {counts.pendent} pendents{counts.error > 0 ? ` · ${counts.error} errors` : ''}
              </p>
              {campaign.errors?.length > 0 && (
                <details className="text-xs text-red-600">
                  <summary className="cursor-pointer">Veure errors</summary>
                  <ul className="mt-1 space-y-0.5">
                    {campaign.errors.map((e, i) => (
                      <li key={i} className="truncate">{e.email}: {e.error_msg}</li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          )}

          {isDraft && isEdit && (
            <div className="border border-zinc-200 rounded-xl p-4 space-y-3">
              <p className="text-xs font-medium text-zinc-600 flex items-center gap-1.5">
                <Mail size={13} /> {recipients === null ? '…' : recipients} subscriptors actius
              </p>

              <div className="space-y-1.5">
                <label className="block text-xs font-medium text-zinc-600">Enviar prova a</label>
                <div className="flex gap-1.5">
                  <input
                    type="email"
                    value={testEmail}
                    onChange={e => setTestEmail(e.target.value)}
                    placeholder="tu@exemple.com"
                    className="flex-1 min-w-0 border border-zinc-200 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-zinc-900"
                  />
                  <button
                    onClick={handleSendTest}
                    disabled={sendingTest || !testEmail}
                    className="px-3 py-1.5 text-xs border border-zinc-200 rounded-lg hover:bg-zinc-50 disabled:opacity-50 transition-colors"
                  >
                    {sendingTest ? <Loader2 size={12} className="animate-spin" /> : 'Provar'}
                  </button>
                </div>
              </div>

              <button
                onClick={handleSendAll}
                disabled={sending || !form.assumpte || !form.contingut_html}
                className="w-full flex items-center justify-center gap-1.5 text-sm bg-primary hover:bg-zinc-800 text-white px-4 py-2 rounded-lg transition-colors disabled:opacity-50 font-medium"
              >
                {sending ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
                Enviar a tothom
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
