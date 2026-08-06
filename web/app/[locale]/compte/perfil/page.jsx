'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Check, Loader2 } from 'lucide-react';
import { useAuth, authFetch } from '../../../../components/store/AuthProvider';

export default function PerfilPage() {
  const t = useTranslations('compte');
  const { user, refresh } = useAuth();
  const [form, setForm] = useState({
    nombre: user?.nombre || '',
    telefon: user?.telefon || '',
    idioma: user?.idioma || 'ca',
    consent_newsletter: user?.consent_newsletter ?? false,
  });
  const [status, setStatus] = useState('idle'); // idle | saving | saved | error

  function set(key, val) { setForm(f => ({ ...f, [key]: val })); }

  async function handleSave(e) {
    e.preventDefault();
    setStatus('saving');
    try {
      const res = await authFetch('/me/profile', {
        method: 'PATCH',
        body: JSON.stringify(form),
      });
      if (res.ok) {
        setStatus('saved');
        await refresh();
        setTimeout(() => setStatus('idle'), 2500);
      } else {
        setStatus('error');
      }
    } catch {
      setStatus('error');
    }
  }

  return (
    <div className="max-w-lg">
      <h1 className="font-serif italic text-2xl md:text-3xl mb-6">{t('myProfile')}</h1>

      <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] p-6">
        <div className="mb-5 pb-5 border-b border-zinc-50">
          <p className="text-sm font-medium text-zinc-500 mb-1">Email</p>
          <p className="text-zinc-800">{user?.email}</p>
          <p className="text-xs text-zinc-400 mt-1">{t('emailCannotBeChanged')}</p>
        </div>

        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1.5">{t('name')}</label>
            <input
              type="text"
              value={form.nombre}
              onChange={e => set('nombre', e.target.value)}
              placeholder={t('yourName')}
              className="w-full border border-zinc-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1.5">{t('phone')}</label>
            <input
              type="tel"
              value={form.telefon}
              onChange={e => set('telefon', e.target.value)}
              placeholder="+34 600 000 000"
              className="w-full border border-zinc-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1.5">{t('preferredLanguage')}</label>
            <div className="flex gap-3">
              {[{ code: 'ca', label: 'Català' }, { code: 'es', label: 'Castellano' }, { code: 'en', label: 'English' }].map(({ code, label }) => (
                <button
                  key={code}
                  type="button"
                  onClick={() => set('idioma', code)}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-colors ${
                    form.idioma === code
                      ? 'border-zinc-900 bg-zinc-100 text-zinc-900'
                      : 'border-zinc-200 text-zinc-600 hover:border-zinc-300'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <label className="flex items-start gap-3 cursor-pointer py-3 px-4 rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] hover:bg-zinc-50 transition-colors">
            <input
              type="checkbox"
              checked={form.consent_newsletter}
              onChange={e => set('consent_newsletter', e.target.checked)}
              className="mt-0.5 accent-zinc-900"
            />
            <div>
              <p className="text-sm font-medium text-zinc-700">{t('newsletterSubscription')}</p>
              <p className="text-xs text-zinc-400 mt-0.5">
                {t('newsletterDescription')}
              </p>
            </div>
          </label>

          {status === 'error' && (
            <p className="text-sm text-red-500">{t('saveError')}</p>
          )}

          <button
            type="submit"
            disabled={status === 'saving' || status === 'saved'}
            className="w-full flex items-center justify-center gap-2 bg-primary hover:bg-zinc-800 text-white py-3 rounded-full font-medium text-sm transition-colors disabled:opacity-70"
          >
            {status === 'saving' && <Loader2 size={15} className="animate-spin" />}
            {status === 'saved' && <Check size={15} />}
            {status === 'saving' ? t('saving') : status === 'saved' ? t('saved') : t('saveChanges')}
          </button>
        </form>
      </div>
    </div>
  );
}
