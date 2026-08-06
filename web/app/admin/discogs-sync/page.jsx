'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function DiscogsSyncRedirect() {
  const router = useRouter();
  useEffect(() => { router.replace('/admin/catalogo'); }, [router]);
  return null;
}
