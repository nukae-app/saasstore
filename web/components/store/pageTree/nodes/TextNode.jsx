import { resolveLocale } from '../locale';

export default function TextNode({ node, locale }) {
  const { id, props = {}, style = {} } = node;
  const text = resolveLocale(props.text, locale);
  if (!text) return null;
  return (
    <p data-node-id={id} style={style}>
      {text}
    </p>
  );
}
