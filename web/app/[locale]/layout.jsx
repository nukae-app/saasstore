import { hasLocale, NextIntlClientProvider } from 'next-intl';
import { notFound } from 'next/navigation';
import { setRequestLocale } from 'next-intl/server';
import { routing } from '../../i18n/routing';
import { api } from '../lib/api';

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export default async function LocaleLayout({ children, params }) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();

  // Dominio sin tenant (uno viejo reasignado, un typo, lo que sea): antes
  // cada página tragaba el 404 de la API y renderizaba igual el layout de
  // tienda vacío ("Botiga online" genérico) — ahora sí se ve como lo que
  // es, un 404 real. Solo se distingue el 404 de "sin tenant" de otros
  // fallos (red, backend caído): esos no deben tapar la tienda entera.
  try {
    await api('/config/public');
  } catch (err) {
    if (err.status === 404) notFound();
  }

  setRequestLocale(locale);

  return <NextIntlClientProvider>{children}</NextIntlClientProvider>;
}
