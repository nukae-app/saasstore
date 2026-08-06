'use client';

import { useLocale } from 'next-intl';
import { useParams } from 'next/navigation';
import { usePathname, useRouter } from '../../i18n/navigation';

const LANGUAGES = [
  { code: 'ca', label: 'CA' },
  { code: 'es', label: 'ES' },
  { code: 'en', label: 'EN' },
];

export default function LanguageSwitcher({ className = '' }) {
  const locale = useLocale();
  const pathname = usePathname();
  const params = useParams();
  const router = useRouter();

  function switchTo(code) {
    router.replace({ pathname, params }, { locale: code });
  }

  return (
    <div className={`flex items-center gap-0.5 text-xs font-medium ${className}`}>
      {LANGUAGES.map(({ code, label }) => (
        <button
          key={code}
          onClick={() => switchTo(code)}
          className={`px-1.5 py-1 rounded transition-colors ${
            locale === code ? 'text-zinc-900' : 'text-zinc-400 hover:text-zinc-600'
          }`}
          aria-current={locale === code}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
