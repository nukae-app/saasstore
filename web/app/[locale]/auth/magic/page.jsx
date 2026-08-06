'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useRouter, Link } from '../../../../i18n/navigation';
import { useTranslations } from 'next-intl';
import { Loader2, CheckCircle, XCircle } from 'lucide-react';
import { useAuth } from '../../../../components/store/AuthProvider';
import { Suspense } from 'react';

function MagicVerify() {
  const t = useTranslations('authPages');
  const router = useRouter();
  const params = useSearchParams();
  const { login } = useAuth();
  const [status, setStatus] = useState('loading'); // loading | ok | error

  useEffect(() => {
    const token = params.get('token');
    if (!token) { setStatus('error'); return; }

    fetch(`/api/auth/magic-link/verify?token=${token}`, {
      method: 'POST',
      credentials: 'include',
    })
      .then(async res => {
        if (!res.ok) { setStatus('error'); return; }
        const { access_token } = await res.json();
        login(access_token);
        setStatus('ok');
        const next = params.get('next') || '/compte';
        setTimeout(() => router.replace(next), 1200);
      })
      .catch(() => setStatus('error'));
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="text-center max-w-sm">
        {status === 'loading' && (
          <>
            <Loader2 size={40} className="text-zinc-900 animate-spin mx-auto mb-4" />
            <p className="text-zinc-600">{t('verifyingLink')}</p>
          </>
        )}
        {status === 'ok' && (
          <>
            <CheckCircle size={40} className="text-green-500 mx-auto mb-4" />
            <h1 className="font-serif italic text-2xl mb-2">{t('welcome')}</h1>
            <p className="text-zinc-500 text-sm">{t('redirectingToAccount')}</p>
          </>
        )}
        {status === 'error' && (
          <>
            <XCircle size={40} className="text-red-500 mx-auto mb-4" />
            <h1 className="font-serif italic text-2xl mb-2">{t('invalidLink')}</h1>
            <p className="text-zinc-500 text-sm mb-6">
              {t('linkExpiredOrUsed')}
            </p>
            <Link
              href="/login"
              className="inline-flex items-center gap-2 bg-primary hover:bg-zinc-800 text-white px-5 py-2.5 rounded-full text-sm font-medium transition-colors"
            >
              {t('backToLogin')}
            </Link>
          </>
        )}
      </div>
    </div>
  );
}

export default function MagicPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 size={32} className="text-zinc-900 animate-spin" />
      </div>
    }>
      <MagicVerify />
    </Suspense>
  );
}
