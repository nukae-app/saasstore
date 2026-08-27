import { getLocale } from 'next-intl/server';
import './globals.css';
import CartProvider from '../components/store/CartProvider';
import AuthProvider from '../components/store/AuthProvider';
import FaroInit from '../components/observability/FaroInit';
import { api } from './lib/api';

// Dinàmic per tenant (abans era estàtic i sempre deia "Ultra-Local
// Records", també per a la resta de tenants) — es resol per Host a cada
// request, mateix mecanisme que qualsevol altra pàgina SSR (ver lib/api.js).
export async function generateMetadata() {
  try {
    const config = await api('/config/public');
    return {
      title: { default: config.nombre, template: `%s · ${config.nombre}` },
      description: config.address ? config.address.replace(/\n/g, ', ') : undefined,
      // Favicon propio del tenant (Configuració → Botiga → Favicon), antes
      // vivía como app/icon.png estático, que Next.js aplicaba a TODO el
      // sitio (landing, superadmin, cualquier otro tenant) sin distinción
      // de dominio. Sin favicon propio, ningún <link rel="icon"> propio —
      // el navegador usa su default en vez de heredar el de otro tenant.
      icons: config.favicon_url ? { icon: config.favicon_url } : undefined,
    };
  } catch {
    return { title: 'Botiga online' };
  }
}

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
