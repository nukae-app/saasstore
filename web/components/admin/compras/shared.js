// Helpers compartits entre les pantalles de /admin/compras/* (Sol·licituds,
// Comandes, Compres particulars, Historial, Proveïdors, Resum) — extret del
// monòlit original per evitar duplicar-los a cada pantalla.

export const DESPESA_ESTAT_FALLBACK = { pendent: 'Pendent', vencut: 'Vençuda', pagat: 'Pagada' };
export const DESPESA_ESTAT_COLOR = {
  pendent: 'bg-amber-100 text-amber-700', vencut: 'bg-red-100 text-red-600', pagat: 'bg-emerald-100 text-emerald-700',
};
export function despesaEstatLabel(t, estat) {
  return t(`purchases.despesa_status.${estat}`, DESPESA_ESTAT_FALLBACK[estat] ?? estat);
}

export const GRADINGS = ['Mint (M)', 'Near Mint (NM or M-)', 'Very Good Plus (VG+)', 'Very Good (VG)', 'Good Plus (G+)', 'Good (G)', 'Fair (F)', 'Poor (P)'];

export const COMANDA_STATUS_FALLBACK = {
  esborrany: 'Esborrany', enviada: 'Enviada', rebuda_parcial: 'Rebuda parcial',
  rebuda: 'Rebuda', cancelada: 'Cancel·lada',
};
export const COMANDA_STATUS_COLOR = {
  esborrany: 'bg-zinc-100 text-zinc-600', enviada: 'bg-blue-100 text-blue-700',
  rebuda_parcial: 'bg-amber-100 text-amber-700', rebuda: 'bg-emerald-100 text-emerald-700',
  cancelada: 'bg-red-100 text-red-600',
};
export function comandaStatusLabel(t, status) {
  return t(`purchases.comanda_status.${status}`, COMANDA_STATUS_FALLBACK[status] ?? status);
}

export const SOLICITUD_STATUS_FALLBACK = { oberta: 'Oberta', resolta: 'Resolta', cancelada: 'Cancel·lada' };
export const SOLICITUD_STATUS_COLOR = {
  oberta: 'bg-blue-100 text-blue-700', resolta: 'bg-emerald-100 text-emerald-700',
  cancelada: 'bg-red-100 text-red-600',
};
export function solicitudStatusLabel(t, estado) {
  return t(`purchases.solicitud_status.${estado}`, SOLICITUD_STATUS_FALLBACK[estado] ?? estado);
}

// Estat d'una línia dins del pool de sol·licituds (independent del lot al
// qual pertany, veure GET /admin/solicitudes-compra/pool): "pendent" si
// encara no s'ha resolt, "resolta" si ja té comanda_linea_id/item_resuelto_id,
// "cancelada" si el lot sencer es va cancel·lar.
export const POOL_LINEA_ESTAT_COLOR = {
  pendent: 'bg-zinc-100 text-zinc-500', resolta: 'bg-emerald-100 text-emerald-700', cancelada: 'bg-red-100 text-red-600',
};
export function poolLineaEstat(linea) {
  if (linea.solicitud_estado === 'cancelada') return 'cancelada';
  if (linea.resuelta) return 'resolta';
  return 'pendent';
}
export function poolLineaEstatLabel(t, linea) {
  const estat = poolLineaEstat(linea);
  if (estat === 'pendent') return t('purchases.pending', 'Pendent');
  return solicitudStatusLabel(t, estat);
}

export const ORIGEN_SOLICITUD_FALLBACK = { manual: 'Manual', refill_stock: 'Reposició', peticion_cliente: 'Petició client' };
export const ORIGEN_SOLICITUD_COLOR = {
  manual: 'bg-zinc-100 text-zinc-600', refill_stock: 'bg-blue-100 text-blue-700', peticion_cliente: 'bg-violet-100 text-violet-700',
};
export function origenSolicitudLabel(t, origen) {
  return t(`purchases.origin.${origen}`, ORIGEN_SOLICITUD_FALLBACK[origen] ?? origen);
}

export function fmtEur(n) {
  return `${parseFloat(n).toLocaleString('ca-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

export function costCompra(c) {
  return (c.items ?? []).reduce((acc, it) => acc + parseFloat(it.acquisition_cost || 0), 0);
}

export function pendentQty(c) {
  return (c.lineas ?? []).reduce((acc, l) => acc + Math.max(0, l.quantity - l.received_quantity), 0);
}
