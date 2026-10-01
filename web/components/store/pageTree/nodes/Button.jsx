import { resolveLocale } from '../locale';

const DEFAULT_STYLE = {
  display: 'inline-block',
  padding: '10px 20px',
  borderRadius: '8px',
  background: '#18181b',
  color: '#ffffff',
  textDecoration: 'none',
  fontSize: '14px',
  fontWeight: 600,
};

export default function Button({ node, locale }) {
  const { id, props = {}, style = {} } = node;
  const text = resolveLocale(props.text, locale);
  if (!text) return null;
  return (
    <a data-node-id={id} href={props.href || '#'} style={{ ...DEFAULT_STYLE, ...style }}>
      {text}
    </a>
  );
}
