'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Download, Loader2, Trash2 } from 'lucide-react';
import { useAuth, authFetch } from '../../../../components/store/AuthProvider';

// Drets RGPD de l'usuari (accés/portabilitat i supressió) en autoservei:
// ver api/app/services/gdpr.py per al que es conserva i per què.
export default function PrivacySection() {
  const t = useTranslations('compte');
  const { user, logout } = useAuth();
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState(false);
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null); // string | { reasons: [] }

  async function handleExport() {
    setExporting(true);
    setExportError(false);
    try {
      const res = await authFetch('/me/data-export');
      if (!res.ok) throw new Error('export');
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement('a');
      a.href = url;
      a.download = 'les-meves-dades.json';
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setExportError(true);
    } finally {
      setExporting(false);
    }
  }

  async function handleDelete(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await authFetch('/me', {
        method: 'DELETE',
        body: JSON.stringify({ confirm_email: email, password: password || null }),
      });
      if (res.status === 204) {
        await logout();
        window.location.href = '/';
        return;
      }
      const data = await res.json().catch(() => ({}));
      if (res.status === 409 && data.reasons) setError({ reasons: data.reasons });
      else if (res.status === 403) setError('wrongPassword');
      else if (res.status === 422) setError('emailMismatch');
      else setError('generic');
    } catch {
      setError('generic');
    } finally {
      setBusy(false);
    }
  }

  const input = 'w-full border border-zinc-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900';

  return (
    <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] p-6 mt-6">
      <h2 className="font-medium text-zinc-900 mb-1">{t('privacy.title')}</h2>
      <p className="text-sm text-zinc-500 mb-4">{t('privacy.intro')}</p>

      <button
        type="button"
        onClick={handleExport}
        disabled={exporting}
        className="inline-flex items-center gap-2 border border-zinc-200 hover:border-zinc-400 rounded-full px-4 py-2 text-sm font-medium text-zinc-800 transition-colors disabled:opacity-60"
      >
        {exporting ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />}
        {t('privacy.download')}
      </button>
      {exportError && <p className="text-sm text-red-500 mt-2">{t('privacy.exportError')}</p>}

      <div className="border-t border-zinc-100 mt-6 pt-6">
        <h3 className="text-sm font-medium text-red-700 mb-1">{t('privacy.deleteTitle')}</h3>
        <p className="text-sm text-zinc-500 mb-3">{t('privacy.deleteWarning')}</p>
        {!open ? (
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="inline-flex items-center gap-2 text-sm font-medium text-red-700 hover:text-red-900"
          >
            <Trash2 size={15} /> {t('privacy.deleteStart')}
          </button>
        ) : (
          <form onSubmit={handleDelete} className="space-y-3">
            <div>
              <label className="block text-sm text-zinc-700 mb-1.5">{t('privacy.typeEmail', { email: user?.email || '' })}</label>
              <input type="email" required value={email} onChange={e => setEmail(e.target.value)} className={input} autoComplete="off" />
            </div>
            <div>
              <label className="block text-sm text-zinc-700 mb-1.5">{t('privacy.passwordIfAny')}</label>
              <input type="password" value={password} onChange={e => setPassword(e.target.value)} className={input} autoComplete="current-password" />
            </div>
            {error && (
              <div className="text-sm text-red-600" role="alert">
                {typeof error === 'string' ? t(`privacy.errors.${error}`) : (
                  <>
                    <p>{t('privacy.errors.blocked')}</p>
                    <ul className="list-disc pl-5 mt-1">
                      {error.reasons.map(r => <li key={r}>{t.has(`privacy.reasons.${r}`) ? t(`privacy.reasons.${r}`) : r}</li>)}
                    </ul>
                  </>
                )}
              </div>
            )}
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={busy || !email}
                className="inline-flex items-center gap-2 bg-red-700 hover:bg-red-800 text-white rounded-full px-4 py-2 text-sm font-medium disabled:opacity-60"
              >
                {busy && <Loader2 size={15} className="animate-spin" />}
                {t('privacy.deleteConfirm')}
              </button>
              <button type="button" onClick={() => { setOpen(false); setError(null); }} className="text-sm text-zinc-500 hover:text-zinc-800">
                {t('privacy.cancel')}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
