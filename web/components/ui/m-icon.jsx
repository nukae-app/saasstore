// Icona de Material Symbols Outlined (ligadura = contingut de l'span).
// Requereix la fulla d'estils carregada per AdminHead (web/app/admin/layout.jsx) —
// només s'usa dins l'admin, el storefront segueix amb lucide-react.
export default function MIcon({ name, size = 20, className = '', style }) {
  return (
    <span
      className={`material-symbols-outlined leading-none select-none ${className}`}
      style={{ fontSize: size, width: size, height: size, ...style }}
    >
      {name}
    </span>
  );
}
