import { Fragment } from 'react';
import { api } from '../../../app/lib/api';
import { collectEtiquetaSlugs, treeHasHomeBlockNode } from './collectLiveData';
import { NODE_REGISTRY } from './registry';

// Idéntico a fetchAllByEtiqueta en app/[locale]/page.jsx — se duplica aquí
// a propósito en vez de importarlo: ese fichero es del home viejo
// (HomeBlock), que se retira en la Fase 5 (ver ARQUITECTURA_DISENY_FIGMA.md
// §5); esta copia es la que queda cuando eso pase.
async function fetchAllByEtiqueta(slug) {
  const results = [];
  let page = 1;
  for (;;) {
    const data = await api(`/catalog?etiqueta=${slug}&page=${page}&page_size=100`);
    results.push(...data.results);
    if (results.length >= data.total || data.results.length === 0) break;
    page += 1;
  }
  return results;
}

function renderNode(node, ctx) {
  if (!node) return null;
  const Component = NODE_REGISTRY[node.type];
  if (!Component) return null; // tipo desconocido: no tira la página entera, solo omite el nodo

  if (node.type === 'ProductGrid') {
    const releases = node.props?.etiqueta_slug ? ctx.releasesByEtiqueta[node.props.etiqueta_slug] || [] : [];
    return <Component key={node.id} node={node} releases={releases} />;
  }

  // Nodo "vivo" sin children (mismo criterio que ProductGrid) — necesita el
  // searchParams/basePath de la página real que lo incrusta (ver
  // [locale]/[slug]/page.jsx y [locale]/page.jsx), nunca datos de catálogo
  // resueltos por adelantado (regla de oro §2).
  if (node.type === 'CatalogBrowse') {
    return <Component key={node.id} node={node} locale={ctx.locale} searchParams={ctx.searchParams} basePath={ctx.basePath} />;
  }

  if (node.type === 'HomeBlockNode') {
    return <Component key={node.id} node={node} liveHomeData={ctx.liveHomeData} />;
  }

  const children = (node.children ?? []).map((child) => (
    <Fragment key={child.id}>{renderNode(child, ctx)}</Fragment>
  ));
  return (
    <Component key={node.id} node={node} locale={ctx.locale}>
      {children}
    </Component>
  );
}

// Server Component async: hace el pre-fetch de datos en vivo (una sola vez,
// por etiqueta distinta usada en todo el árbol, no por nodo) y luego
// renderiza de forma síncrona — mismo orden de trabajo que HomePage en
// app/[locale]/page.jsx, aplicado a un árbol en vez de una lista plana de
// bloques. Nunca importa @craftjs/core (verificado en el spike de Fase 0):
// esto es exactamente lo que permite que el storefront público no cargue
// el runtime del editor.
export default async function TreeRenderer({ tree, locale = 'ca', searchParams, basePath }) {
  if (!tree) return null;

  // `searchParams` llega como Promise en el App Router (mismo patrón que
  // `cataleg/page.jsx`) — se resuelve aquí una vez, no en cada nodo que lo
  // necesite (hoy solo `CatalogBrowse`).
  const resolvedSearchParams = searchParams ? await searchParams : {};

  const etiquetaSlugs = [...collectEtiquetaSlugs(tree)];
  const releasesByEtiqueta = {};
  for (const slug of etiquetaSlugs) {
    try {
      releasesByEtiqueta[slug] = await fetchAllByEtiqueta(slug);
    } catch {
      releasesByEtiqueta[slug] = [];
    }
  }

  // Solo si el árbol usa algún bloque legado (`HomeBlockNode`) — el resto de
  // páginas no paga este coste. Mismas tres llamadas que hace HomePage hoy
  // (app/[locale]/page.jsx) para lo mismo.
  let liveHomeData;
  if (treeHasHomeBlockNode(tree)) {
    let config = null, recomanats = [], sonant = [];
    try { config = await api('/config/public'); } catch {}
    try { recomanats = await fetchAllByEtiqueta('recomanat'); } catch {}
    try { sonant = (await api('/catalog?esta_sonant=true&page_size=1')).results; } catch {}
    const featured = sonant[0] || recomanats[0] || null;
    liveHomeData = {
      config, recomanats, featured, releasesByEtiqueta,
      recordstore: config?.theme?.preset === 'recordstore',
    };
  }

  return renderNode(tree, { locale, releasesByEtiqueta, searchParams: resolvedSearchParams, basePath, liveHomeData });
}
