'use client';

import { useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { useRouter } from '../../../../i18n/navigation';
import { useTranslations } from 'next-intl';
import { Loader2 } from 'lucide-react';
import { useAuth } from '../../../../components/store/AuthProvider';
import { Suspense } from 'react';

function GoogleCallback() {
  const t = useTranslations('authPages');
  const router = useRouter();
  const params = useSearchParams();
  const { login } = useAuth();

  useEffect(() => {
    // El token ve com a query param ?access_token= o bé en el cookie
    // El backend fa redirect a /auth/ok, l'access_token s'ha de recollir
    const token = params.get('access_token');
    if (token) {
      login(token);
    } else {
      // Intentar refresh per si el backend ha posat el cookie
      fetch('/api/auth/refresh', { method: 'POST', credentials: 'include' })
        .then(r => r.ok ? r.json() : null)
        .then(data => { if (data?.access_token) login(data.access_token); });
    }
    setTimeout(() => router.replace('/compte'), 1000);
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <Loader2 size={36} className="text-zinc-900 animate-spin mx-auto mb-3" />
        <p className="text-zinc-500 text-sm">{t('loggingIn')}</p>
      </div>
    </div>
  );
}

export default function AuthOkPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 size={32} className="text-zinc-900 animate-spin" /></div>}>
      <GoogleCallback />
    </Suspense>
  );
}
