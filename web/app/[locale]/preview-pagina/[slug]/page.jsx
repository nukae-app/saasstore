// Previsualització REAL de `draft_tree` (no publicada) — feedback directo
// del usuario: el placeholder del canvas del editor ("Bloc: Hero") no se
// parece a la web de verdad y no basta. Esta ruta renderiza con el MISMO
// TreeRenderer que usa el sitio público (mismos componentes reales, misma
// resolución de datos en vivo), solo que leyendo `draft_tree` en vez de
// `published_tree`.
//
// Vive FUERA de `web/app/admin/` a propósito: `admin/layout.jsx` envuelve
// todo lo de ahí con su propio chrome (sidebar) y guarda de sesión basada
// en localStorage, que no aplica aquí — esta ruta se autentica con un
// token pasado por query string (ver más abajo), no con esa sesión.
//
// `GET /admin/pages/:slug` exige el JWT de admin (localStorage, solo
// accesible en el navegador) — esta ruta es un Server Component y no puede
// leer localStorage, así que el editor
// (`admin/editor-pagines/[slug]/page.jsx`) pasa el access token vigente
// como query param al abrir esta pestaña. Es un token de acceso normal
// (~15 min, el mismo que ya viaja en cada llamada admin), no uno nuevo —
// pragmático: sin token válido esta ruta no muestra nada, y el token
// expira solo en minutos.
import { notFound } from 'next/navigation';
import { api } from '../../../lib/api';
import StorefrontNav from '../../../../components/store/StorefrontNav';
import StorefrontFooter from '../../../../components/store/StorefrontFooter';
import TreeRenderer from '../../../../components/store/pageTree/TreeRenderer';

export default async function PagePreview({ params, searchParams }) {
  const { slug, locale } = await params;
  const { token } = await searchParams;
  if (!token) notFound();

  let page;
  try {
    page = await api(`/admin/pages/${slug}`, { headers: { Authorization: `Bearer ${token}` } });
  } catch {
    return (
      <div className="p-10 text-center text-sm text-zinc-500">
        No s&apos;ha pogut carregar la previsualització (sessió caducada?) — torna-la a obrir des de l&apos;editor.
      </div>
    );
  }

  const basePath = slug === 'home' ? '/' : `/${slug}`;

  return (
    <>
      <div className="bg-amber-100 text-amber-800 text-xs text-center py-1.5 sticky top-0 z-50">
        Previsualització de l&apos;esborrany — encara no publicat
      </div>
      <StorefrontNav />
      <main className="flex-1">
        <TreeRenderer tree={page.draft_tree} locale={locale} basePath={basePath} />
      </main>
      <StorefrontFooter />
    </>
  );
}
