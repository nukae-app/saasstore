import { getLocale } from 'next-intl/server';
import './globals.css';
import CartProvider from '../components/store/CartProvider';
import AuthProvider from '../components/store/AuthProvider';
import FaroInit from '../components/observability/FaroInit';

export const metadata = {
  title: { default: 'Ultra-Local Records', template: '%s · Ultra-Local Records' },
  description: 'Discos nous i de segona mà a Poblenou, Barcelona. Pujades 113.',
};

export default async function RootLayout({ children }) {
  // /admin no pasa por el middleware de next-intl: getLocale() cae al
  // defaultLocale ("ca"), igual que el <html lang="ca"> fijo de antes.
  const locale = await getLocale();

  return (
    <html lang={locale}>
      <body className="flex flex-col min-h-screen">
        <FaroInit collectorUrl={process.env.NEXT_PUBLIC_FARO_COLLECTOR_URL} />
        <AuthProvider>
          <CartProvider>{children}</CartProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
