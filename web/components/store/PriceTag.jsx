// Precio final + precio de tarifa tachado cuando una oferta está activa
// (`Item.list_price`, ver models/pricing.py en la API). `list_price` es
// `null`/`undefined` mientras no haya oferta — en ese caso solo se muestra
// el precio normal, sin tachado ni color de oferta.
export default function PriceTag({ price, listPrice, size = 'text-lg' }) {
  const p = parseFloat(price);
  const lp = listPrice != null ? parseFloat(listPrice) : null;
  const hasOffer = lp != null && lp > p;

  return (
    <span className="inline-flex items-baseline gap-1.5">
      {hasOffer && (
        <span className="text-xs text-zinc-400 line-through">{lp.toFixed(2)} €</span>
      )}
      <span className={`${size} font-semibold ${hasOffer ? 'text-red-600' : 'text-zinc-900'}`}>
        {p.toFixed(2)} €
      </span>
    </span>
  );
}
