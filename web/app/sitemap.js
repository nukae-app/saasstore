import { routing } from '../i18n/routing';
import { api } from './lib/api';

const SITE = 'https://labotigaaquesta.com';

// Rutas estáticas públicas (las privadas — login, checkout, compte, carret —
// se excluyen aquí y además llevan noindex, ver robots.js y sus layouts).
const STATIC_PATHS = ['', '/cataleg', '/blog', '/agenda', '/termes', '/privacitat'];

export default async function sitemap() {
  const entries = [];

  for (const locale of routing.locales) {
    for (const path of STATIC_PATHS) {
      entries.push({ url: `${SITE}/${locale}${path}` });
    }
  }

  try {
    const posts = await api('/posts?page_size=200');
    for (const post of posts) {
      for (const locale of routing.locales) {
        entries.push({
          url: `${SITE}/${locale}/blog/${post.slug}`,
          lastModified: post.published_at || undefined,
        });
      }
    }
  } catch {
    // Si la API no responde en el momento de generar el sitemap, se sirve
    // solo con las rutas estáticas — mejor un sitemap parcial que ninguno.
  }

  try {
    const paginas = await api('/pagines');
    // Las traducciones de páginas legales (`privacitat-es`...) se sirven bajo el
    // slug base según el idioma (ver [pagina]/page.jsx): listarlas aparte
    // duplicaría URLs.
    const esVarianteLegal = (slug) => /^(avis-legal|privacitat|termes|cookies|condicions-venda)-(es|en)$/.test(slug);
    for (const pagina of paginas) {
      if (esVarianteLegal(pagina.slug)) continue;
      for (const locale of routing.locales) {
        entries.push({ url: `${SITE}/${locale}/${pagina.slug}` });
      }
    }
  } catch {}

  return entries;
}
