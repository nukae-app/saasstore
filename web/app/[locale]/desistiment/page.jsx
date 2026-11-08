'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Loader2, CheckCircle2 } from 'lucide-react';
import { Link } from '../../../i18n/navigation';
import StorefrontNav from '../../../components/store/StorefrontNav';
import StorefrontFooter from '../../../components/store/StorefrontFooter';

// Función de desistimiento (Directiva 2011/83/UE art. 11 bis). Pública y sin
// login: un invitado también compra, así que el consumidor solo necesita la
// referencia del pedido y el email de compra. El servidor responde siempre
// igual (no revela qué pedidos existen), por eso el mensaje de éxito es neutro.
export default function DesistimentPage() {
  const t = useTranslations('withdrawal');
  const [form, setForm] = useState({ order_ref: '', email: '', name: '' });
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function onSubmit(e) {
    e.preventDefault();
    setSending(true);
    setError('');
    try {
      const res = await fetch('/api/orders/withdrawal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          order_ref: form.order_ref.trim(),
          email: form.email.trim(),
          name: form.name.trim() || null,
        }),
      });
      if (!res.ok) throw new Error('bad status');
      setDone(true);
    } catch {
      setError(t('error'));
    } finally {
      setSending(false);
    }
  }

  const input = 'w-full border border-zinc-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900';

  return (
    <>
      <StorefrontNav />
      <main className="container max-w-xl py-12">
        <h1 className="text-2xl font-semibold mb-3">{t('title')}</h1>

        {done ? (
          <div className="bg-green-50 border border-green-200 rounded-xl p-5 text-sm text-green-900" role="status">
            <div className="flex items-center gap-2 font-medium mb-1">
              <CheckCircle2 size={18} /> {t('doneTitle')}
            </div>
            <p>{t('done')}</p>
          </div>
        ) : (
          <>
            <p className="text-sm text-zinc-600 mb-6">{t('intro')}</p>
            <form onSubmit={onSubmit} className="space-y-4">
              <div>
                <label htmlFor="wd-ref" className="block text-sm font-medium text-zinc-700 mb-1.5">{t('orderRef')}</label>
                <input id="wd-ref" required minLength={6} maxLength={36} value={form.order_ref}
                  onChange={set('order_ref')} className={input} autoComplete="off" />
                <p className="text-xs text-zinc-500 mt-1">{t('orderRefHelp')}</p>
              </div>
              <div>
                <label htmlFor="wd-email" className="block text-sm font-medium text-zinc-700 mb-1.5">{t('email')}</label>
                <input id="wd-email" type="email" required value={form.email}
                  onChange={set('email')} className={input} autoComplete="email" />
              </div>
              <div>
                <label htmlFor="wd-name" className="block text-sm font-medium text-zinc-700 mb-1.5">{t('name')}</label>
                <input id="wd-name" maxLength={120} value={form.name}
                  onChange={set('name')} className={input} autoComplete="name" />
              </div>
              {error && <p className="text-red-600 text-sm" role="alert">{error}</p>}
              <button type="submit" disabled={sending}
                className="w-full flex items-center justify-center gap-2 bg-zinc-900 hover:bg-zinc-800 text-white px-6 py-3 rounded-full font-medium text-sm transition-colors disabled:opacity-60">
                {sending && <Loader2 size={16} className="animate-spin" />}
                {sending ? t('sending') : t('submit')}
              </button>
            </form>
            <p className="text-xs text-zinc-500 mt-6">
              {t('exceptions')}{' '}
              <Link href="/condicions-venda" className="underline">{t('terms')}</Link>.
            </p>
          </>
        )}
      </main>
      <StorefrontFooter />
    </>
  );
}
