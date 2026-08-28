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

  // Fetch propio de generateMetadata() de arriba — Next.js no permite
  // compartir su resultado con el componente, y api.js fuerza `no-store`,
  // así que ya había esta duplicación de /config/public antes de este
  // cambio (generateMetadata + page.jsx). No se arregla aquí a propósito,
  // es una refactorización aparte.
  let config = null;
  try {
    config = await api('/config/public');
  } catch {}

  // `custom_fonts` és estructurat (family + faces), no un valor CSS — es
  // filtra abans de convertir la resta de `theme` en variables --clau: valor.
  const themeVars = config?.theme
    ? Object.entries(config.theme)
        .filter(([key, value]) => key !== 'custom_fonts' && value)
        .map(([key, value]) => `--${key.replace(/_/g, '-')}: ${value};`)
        .join('')
    : '';

  // Tipografies autoallotjades triades des de Colors i tipografia → Cercar
  // a Fontsource (ver services/fontsource.py) — els fitxers reals ja viuen
  // a /uploads, aquí només es declara la regla @font-face.
  const customFontFaces = config?.theme?.custom_fonts
    ? Object.values(config.theme.custom_fonts)
        .map(({ family, faces }) =>
          (faces || [])
            .map(({ weight, url }) => `@font-face{font-family:'${family}';src:url('${url}') format('woff2');font-weight:${weight};font-style:normal;font-display:swap;}`)
            .join('')
        )
        .join('')
    : '';

  return (
    <html lang={locale}>
      <head>
        {/* Tokens de tema del tenant, sobreescriben las variables de
            globals.css — luego custom_css, para que pueda sobreescribir
            los tokens si hace falta. dangerouslySetInnerHTML es lo correcto
            aquí para un <style>; la defensa real es el saneado al guardar
            (ver services/sanitize.py::sanitize_custom_css), no esta línea. */}
        {customFontFaces && <style dangerouslySetInnerHTML={{ __html: customFontFaces }} />}
        {themeVars && <style dangerouslySetInnerHTML={{ __html: `:root{${themeVars}}` }} />}
        {config?.custom_css && <style dangerouslySetInnerHTML={{ __html: config.custom_css }} />}
      </head>
      <body className="flex flex-col min-h-screen">
        <FaroInit collectorUrl={process.env.NEXT_PUBLIC_FARO_COLLECTOR_URL} />
        <AuthProvider>
          <CartProvider>{children}</CartProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
