import createMiddleware from 'next-intl/middleware';
import { NextResponse } from 'next/server';
import { routing } from './i18n/routing';

const intlMiddleware = createMiddleware(routing);

// /superadmin no forma parte del enrutado por idioma de la tienda — nunca
// debe pasar por next-intl. El gate real vive en el backend
// (_require_superadmin_host, api/app/routers/superadmin.py): esto es solo
// UX, para que el dominio de un tenant cualquiera ni siquiera renderice el
// shell/login del panel de plataforma.
export default function middleware(request) {
  const superadminHost = process.env.NEXT_PUBLIC_SUPERADMIN_HOST || 'superadmin.localhost';
  const requestHost = request.headers.get('host')?.split(':')[0];

  if (request.nextUrl.pathname.startsWith('/superadmin')) {
    if (requestHost !== superadminHost) {
      return new NextResponse(null, { status: 404 });
    }
    return NextResponse.next();
  }
  // Cualquier otra ruta en el dominio de superadmin (empezando por "/", que
  // es justo lo que se pide al escribir el dominio a secas en el navegador)
  // NO debe caer en el flujo normal de tienda — sin esto se resolvía como
  // "dominio de tenant no encontrado" y renderizaba el shell de storefront
  // vacío en vez de llevar al panel (mismo problema que NEXT_PUBLIC_APP_HOST
  // más abajo, aquí para el dominio de superadmin).
  if (requestHost === superadminHost) {
    return NextResponse.redirect(new URL('/superadmin', request.url));
  }
  // /nukaestore es la landing del producto (el SaaS en sí, no una tienda de
  // un tenant) — tampoco debe pasar por next-intl ni por la resolución de
  // tenant por Host que hace cada página de la tienda.
  if (request.nextUrl.pathname.startsWith('/nukaestore')) {
    return NextResponse.next();
  }
  // El dominio propio del producto (NEXT_PUBLIC_APP_HOST — "localhost" a
  // secas en dev) sirve la landing para CUALQUIER ruta, no solo "/": ningún
  // tenant debe tener ese domain en BD, así que dejar caer /ca, /es/cataleg,
  // etc. en el flujo normal solo llevaba a un storefront vacío (la API
  // devuelve 404 por dominio no encontrado, pero layout.jsx/page.jsx
  // atrapan ese error y renderizan la plantilla de tienda igualmente).
  const appHost = process.env.NEXT_PUBLIC_APP_HOST || 'localhost';
  if (requestHost === appHost) {
    return NextResponse.rewrite(new URL('/nukaestore', request.url));
  }
  return intlMiddleware(request);
}

export const config = {
  matcher: ['/((?!admin|api|uploads|_next|.*\\..*).*)'],
};
