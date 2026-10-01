import { resolveLocale } from '../locale';

// `<img>` plana, no `next/image`: este nodo no garantiza un contenedor con
// tamaño fijo (es de layout libre, a diferencia de ReleaseCard/HomeHero,
// que sí lo tienen) — usar `next/image` con `fill` exigiría forzar esa
// restricción aquí. Optimización de imagen queda para cuando haga falta,
// sin romper el esquema del árbol.
export default function ImageNode({ node, locale }) {
  const { id, props = {}, style = {} } = node;
  if (!props.src) return null;
  return (
    <img
      data-node-id={id}
      src={props.src}
      alt={resolveLocale(props.alt, locale)}
      style={{ maxWidth: '100%', height: 'auto', ...style }}
    />
  );
}
