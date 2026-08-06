'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Link } from '../../i18n/navigation';
import { Bell, Check, Loader2 } from 'lucide-react';
import { cn } from '../lib/utils';
import { useAuth, authFetch } from './AuthProvider';

export default function RequestReleaseButton({ releaseId, className }) {
  const t = useTranslations('disc');
  const { user, loading: authLoading } = useAuth();
  const [state, setState] = useState('idle'); // idle | loading | done | error
  const [errorMsg, setErrorMsg] = useState('');

  async function handleRequest() {
    setState('loading');
    setErrorMsg('');
    try {
      const res = await authFetch('/me/peticiones', {
        method: 'POST',
        body: JSON.stringify({ release_id: releaseId }),
      });
      if (res.ok) {
        setState('done');
      } else {
        const d = await res.json().catch(() => ({}));
        setErrorMsg(d.detail || t('requestFailed'));
        setState('error');
      }
    } catch {
      setErrorMsg(t('requestFailed'));
      setState('error');
    }
  }

  if (authLoading) return null;

  if (!user) {
    return (
      <Link
        href="/login"
        className={cn(
          'inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-full text-sm font-medium transition-colors',
          'border border-zinc-300 text-zinc-700 hover:bg-zinc-50',
          className,
        )}
      >
        <Bell size={15} /> {t('loginToBeNotified')}
      </Link>
    );
  }

  if (state === 'error') {
    return <p className="text-sm text-red-600">{errorMsg}</p>;
  }

  return (
    <button
      onClick={handleRequest}
      disabled={state === 'loading' || state === 'done'}
      className={cn(
        'inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-full text-sm font-medium transition-all',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        state === 'done'
          ? 'bg-green-500 text-white cursor-default'
          : 'border border-zinc-300 text-zinc-700 hover:bg-zinc-50 disabled:opacity-60',
        className,
      )}
    >
      {state === 'loading' && <Loader2 size={15} className="animate-spin" />}
      {state === 'done' && <Check size={15} />}
      {state === 'idle' && <Bell size={15} />}
      {state === 'loading' ? t('sending') : state === 'done' ? t('willNotify') : t('notifyMe')}
    </button>
  );
}
