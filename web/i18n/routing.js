import { defineRouting } from 'next-intl/routing';

export const routing = defineRouting({
  locales: ['ca', 'es', 'en'],
  defaultLocale: 'ca',
  localePrefix: 'always',
});
