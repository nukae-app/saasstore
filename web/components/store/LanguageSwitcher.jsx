'use client';

import { useLocale } from 'next-intl';
import { useParams } from 'next/navigation';
import { usePathname, useRouter } from '../../i18n/navigation';

const LANGUAGES = [
  { code: 'ca', label: 'CA' },
  { code: 'es', label: 'ES' },
  { code: 'en', label: 'EN' },
];

// `dark` només el fa servir StorefrontNav.jsx (únic consumidor) quan la
// barra és negra — sense això l'idioma actiu (text-zinc-900) era gairebé
// invisible sobre fons negre.
export default function LanguageSwitcher({ className = '', dark = false }) {
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
            dark
              ? (locale === code ? 'text-white' : 'text-white/40 hover:text-white/70')
              : (locale === code ? 'text-zinc-900' : 'text-zinc-400 hover:text-zinc-600')
          }`}
          aria-current={locale === code}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
