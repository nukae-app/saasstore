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
  if (request.nextUrl.pathname.startsWith('/superadmin')) {
    const expectedHost = process.env.NEXT_PUBLIC_SUPERADMIN_HOST || 'superadmin.localhost';
    const host = request.headers.get('host')?.split(':')[0];
    if (host !== expectedHost) {
      return new NextResponse(null, { status: 404 });
    }
    return NextResponse.next();
  }
  // /nukaestore es la landing del producto (el SaaS en sí, no una tienda de
  // un tenant) — tampoco debe pasar por next-intl ni por la resolución de
  // tenant por Host que hace cada página de la tienda.
  if (request.nextUrl.pathname.startsWith('/nukaestore')) {
    return NextResponse.next();
  }
  // El dominio propio del producto (NEXT_PUBLIC_APP_HOST — "localhost" a
  // secas en dev) sirve la landing en su raíz en vez de intentar resolver
  // un tenant ahí: ningún tenant debe tener ese domain en BD. El resto de
  // rutas de este host (si las hay) siguen el flujo normal.
  const appHost = process.env.NEXT_PUBLIC_APP_HOST || 'localhost';
  const host = request.headers.get('host')?.split(':')[0];
  if (host === appHost && request.nextUrl.pathname === '/') {
    return NextResponse.rewrite(new URL('/nukaestore', request.url));
  }
  return intlMiddleware(request);
}

export const config = {
  matcher: ['/((?!admin|api|uploads|_next|.*\\..*).*)'],
};
