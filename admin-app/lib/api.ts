import { API_URL } from "./config";
import type {
  CatalogPage,
  CatalogRelease,
  Comanda,
  ComandaLineaInPayload,
  DiscogsReleaseDetail,
  DiscogsSearchResult,
  HistorialCompraLinea,
  HistorialResumProveedor,
  MobileLoginOut,
  MobileTokenOut,
  OrderDetail,
  OrderSummary,
  PaymentMethod,
  PeticionCliente,
  PoolLineaInPayload,
  Proveedor,
  RecepcionItemPayload,
  RefillSugerencia,
  ReleaseRef,
  SolicitudCompra,
  SolicitudCompraListPage,
  SolicitudCompraLinea,
  SolicitudPoolPage,
  TipusIva,
  UserSearchResult,
  VentaExternaLoteLinea,
  VentaExternaOut,
} from "./types";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

interface ApiFetchOptions extends RequestInit {
  tenantSlug?: string;
  accessToken?: string;
}

async function apiFetch<T>(path: string, { tenantSlug, accessToken, headers, ...options }: ApiFetchOptions = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(tenantSlug ? { "X-Tenant-Slug": tenantSlug } : {}),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...headers,
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body || `API ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// --- Auth (ver api/app/routers/auth_mobile.py) ---
// Pedir/verificar el enlace NO necesitan X-Tenant-Slug: la API resuelve el
// tenant por el email (busca en qué tienda(s) es admin) o por el propio
// token (token_hash es único a nivel global) — el usuario no tiene que
// saber ni escribir el slug de su tienda para entrar.

export function requestMagicLink(email: string) {
  return apiFetch<{ detail: string }>("/auth/mobile/magic-link", {
    method: "POST",
    body: JSON.stringify({ email, language: "ca" }),
  });
}

export function verifyMagicLink(token: string) {
  return apiFetch<MobileTokenOut>(`/auth/mobile/magic-link/verify?token=${encodeURIComponent(token)}`, {
    method: "POST",
  });
}

export function loginWithPassword(email: string, password: string, tenantSlug?: string) {
  return apiFetch<MobileLoginOut>("/auth/mobile/login", {
    method: "POST",
    body: JSON.stringify({ email, password, ...(tenantSlug ? { tenant_slug: tenantSlug } : {}) }),
  });
}

export function refreshSession(tenantSlug: string, refreshToken: string) {
  return apiFetch<MobileTokenOut>("/auth/mobile/refresh", {
    method: "POST",
    tenantSlug,
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export function logoutSession(tenantSlug: string, refreshToken: string) {
  return apiFetch<undefined>("/auth/mobile/logout", {
    method: "POST",
    tenantSlug,
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

// --- Pedidos (ver api/app/routers/admin/orders.py) ---

export function fetchOrders(tenantSlug: string, accessToken: string) {
  return apiFetch<OrderSummary[]>("/admin/orders", { tenantSlug, accessToken });
}

export function fetchOrderDetail(tenantSlug: string, accessToken: string, orderId: string) {
  return apiFetch<OrderDetail>(`/admin/orders/${orderId}`, { tenantSlug, accessToken });
}

export interface OrderStatusUpdatePayload {
  status?: string;
  tracking_number?: string;
  carrier?: string;
}

export function updateOrderStatus(
  tenantSlug: string,
  accessToken: string,
  orderId: string,
  payload: OrderStatusUpdatePayload,
) {
  return apiFetch<{ status: string; numero_seguiment: string | null; transportista: string | null }>(
    `/admin/orders/${orderId}/status`,
    { method: "PATCH", tenantSlug, accessToken, body: JSON.stringify(payload) },
  );
}

export function avisarRecollida(tenantSlug: string, accessToken: string, orderId: string) {
  return apiFetch<{ avisada_recollida_at: string }>(`/admin/orders/${orderId}/avisar-recollida`, {
    method: "POST",
    tenantSlug,
    accessToken,
  });
}

export function marcarPagadoTienda(
  tenantSlug: string,
  accessToken: string,
  orderId: string,
  paymentMethod: "efectivo" | "tarjeta",
) {
  return apiFetch<{ status: string }>(`/admin/orders/${orderId}/marcar-pagado-tienda`, {
    method: "POST",
    tenantSlug,
    accessToken,
    body: JSON.stringify({ payment_method: paymentMethod }),
  });
}

// --- Catálogo / TPV (ver api/app/routers/catalog.py y erp/ventas_externas.py) ---

export function searchCatalog(tenantSlug: string, accessToken: string, q: string) {
  const params = new URLSearchParams({ q, page_size: "20" });
  return apiFetch<CatalogPage>(`/catalog?${params}`, { tenantSlug, accessToken });
}

export function fetchTiposIva(tenantSlug: string, accessToken: string) {
  return apiFetch<TipusIva[]>("/admin/tipus-iva?nomes_actius=true", { tenantSlug, accessToken });
}

export interface VentaExternaLotePayload {
  lineas: VentaExternaLoteLinea[];
  channel: "mostrador";
  payment_method: PaymentMethod;
  date: string;
  client_name?: string;
}

export function createVentaExternaLote(tenantSlug: string, accessToken: string, payload: VentaExternaLotePayload) {
  return apiFetch<VentaExternaOut[]>("/admin/ventas-externas/lote", {
    method: "POST",
    tenantSlug,
    accessToken,
    body: JSON.stringify(payload),
  });
}

// --- Catálogo — crear release manual (ver api/app/schemas/catalog.py::ReleaseIn) ---
// Solo `title` es obligatorio — el alta debe permitir siempre meter datos
// a mano, sin depender de Discogs (CLAUDE.md).

export interface CreateReleasePayload {
  title: string;
  artista?: string | null;
  sello?: string | null;
  ean?: string | null;
  formato?: string | null;
  anio?: number | null;
  genero?: string | null;
  estilos?: string | null;
  pais?: string | null;
  image_url?: string | null;
  tracklist?: unknown;
  credits?: unknown;
  discogs_release_id?: number | null;
}

export function createRelease(tenantSlug: string, accessToken: string, payload: CreateReleasePayload) {
  return apiFetch<ReleaseRef & { sello: string | null; ean: string | null }>("/admin/releases", {
    method: "POST",
    tenantSlug,
    accessToken,
    body: JSON.stringify(payload),
  });
}

// --- Config pública (ver api/app/routers/configuracio.py::get_configuracio_publica) ---

export function fetchConfigPublic(tenantSlug: string, accessToken: string) {
  return apiFetch<{ discogs_habilitat: boolean; vertical: string }>("/config/public", { tenantSlug, accessToken });
}

// --- Discogs (ver api/app/routers/admin/releases.py, services/discogs.py) ---
// El rate limit (~60/min) lo respeta el backend (throttle server-side,
// CLAUDE.md) — la app nunca pega directo a Discogs, así que no es una
// preocupación nueva aquí.

export function searchDiscogs(tenantSlug: string, accessToken: string, q: string) {
  return apiFetch<DiscogsSearchResult[]>(`/admin/discogs/search?q=${encodeURIComponent(q)}`, {
    tenantSlug,
    accessToken,
  });
}

function enrichDiscogsResult(
  tenantSlug: string,
  accessToken: string,
  result: DiscogsSearchResult,
): Promise<DiscogsSearchResult & DiscogsReleaseDetail> {
  return apiFetch<DiscogsReleaseDetail>(`/admin/discogs/release/${result.discogs_release_id}`, {
    tenantSlug,
    accessToken,
  })
    .then((detail) => ({ ...result, ...detail }))
    .catch(() => result as DiscogsSearchResult & DiscogsReleaseDetail);
}

function checkDuplicateRelease(
  tenantSlug: string,
  accessToken: string,
  params: { discogs_release_id?: number; artista?: string; titulo?: string },
) {
  const query = new URLSearchParams();
  if (params.discogs_release_id) query.set("discogs_release_id", String(params.discogs_release_id));
  if (params.artista) query.set("artista", params.artista);
  if (params.titulo) query.set("titulo", params.titulo);
  return apiFetch<{ id: string; artista: string | null; titulo: string; sello: string | null }[]>(
    `/admin/releases/check-duplicate?${query}`,
    { tenantSlug, accessToken },
  );
}

/** Mismo flujo que `web/app/lib/discogs.js::resolveOrCreateRelease`: busca
 * un local ya existente (por discogs_release_id o artista+título) antes de
 * crear uno nuevo, para no duplicar el catálogo. Trae la ficha completa
 * (tracklist/credits/país/estilos) antes de crear — el resultado de
 * búsqueda es "ligero". */
export async function resolveOrCreateDiscogsRelease(
  tenantSlug: string,
  accessToken: string,
  result: DiscogsSearchResult,
): Promise<ReleaseRef> {
  const full = await enrichDiscogsResult(tenantSlug, accessToken, result);
  const matches = await checkDuplicateRelease(tenantSlug, accessToken, {
    discogs_release_id: full.discogs_release_id,
  });
  if (matches.length > 0) {
    return { id: matches[0].id, artista: matches[0].artista, title: matches[0].titulo };
  }
  const created = await createRelease(tenantSlug, accessToken, {
    title: full.titulo,
    artista: full.artista,
    sello: full.sello,
    formato: full.formato ? full.formato.split(",")[0].trim() : null,
    anio: full.anio,
    genero: full.genero,
    estilos: (full as DiscogsReleaseDetail).estilos ?? null,
    pais: (full as DiscogsReleaseDetail).pais ?? null,
    image_url: full.imagen_url,
    tracklist: (full as DiscogsReleaseDetail).tracklist ?? null,
    credits: (full as DiscogsReleaseDetail).credits ?? null,
    discogs_release_id: full.discogs_release_id,
  });
  return { id: created.id, artista: created.artista, title: created.title };
}

// --- Compras / Comandes (ver api/app/routers/erp/comandas.py) ---

export function fetchProveedores(tenantSlug: string, accessToken: string) {
  return apiFetch<Proveedor[]>("/admin/proveedores", { tenantSlug, accessToken });
}

export function fetchComandas(tenantSlug: string, accessToken: string, status?: string) {
  const params = status ? `?status=${status}` : "";
  return apiFetch<Comanda[]>(`/admin/comandas${params}`, { tenantSlug, accessToken });
}

export function fetchComandaDetail(tenantSlug: string, accessToken: string, id: string) {
  return apiFetch<Comanda>(`/admin/comandas/${id}`, { tenantSlug, accessToken });
}

export interface CreateComandaPayload {
  proveedor_id: string;
  date: string;
  notes?: string;
  lineas: ComandaLineaInPayload[];
}

export function createComanda(tenantSlug: string, accessToken: string, payload: CreateComandaPayload) {
  return apiFetch<Comanda>("/admin/comandas", {
    method: "POST",
    tenantSlug,
    accessToken,
    body: JSON.stringify(payload),
  });
}

export function marcarComandaEnviada(tenantSlug: string, accessToken: string, id: string) {
  return apiFetch<Comanda>(`/admin/comandas/${id}/marcar-enviada`, { method: "PATCH", tenantSlug, accessToken });
}

export function cancelarComanda(tenantSlug: string, accessToken: string, id: string) {
  return apiFetch<Comanda>(`/admin/comandas/${id}/cancelar`, { method: "PATCH", tenantSlug, accessToken });
}

export interface RecepcionPayload {
  date: string;
  delivery_note_number?: string;
  notes?: string;
  items: RecepcionItemPayload[];
}

export function recibirComanda(tenantSlug: string, accessToken: string, id: string, payload: RecepcionPayload) {
  return apiFetch<unknown>(`/admin/comandas/${id}/recepcio`, {
    method: "POST",
    tenantSlug,
    accessToken,
    body: JSON.stringify(payload),
  });
}

// --- Catálogo — ficha de un release (para elegir ejemplar al resoldre
// des d'estoc, ver api/app/routers/catalog.py::GET /releases/{id}) ---

export function fetchReleaseDetail(tenantSlug: string, accessToken: string, releaseId: string) {
  return apiFetch<CatalogRelease>(`/catalog/releases/${releaseId}`, { tenantSlug, accessToken });
}

// --- Sol·licituds de compra (ver api/app/routers/erp/solicitudes_compra.py) ---

export function fetchRefillSugerencias(tenantSlug: string, accessToken: string) {
  return apiFetch<RefillSugerencia[]>("/admin/solicitudes-compra/refill-sugerencias", { tenantSlug, accessToken });
}

export function fetchPool(tenantSlug: string, accessToken: string, estado: "pendent" | "resolta" | "totes" = "pendent") {
  return apiFetch<SolicitudPoolPage>(`/admin/solicitudes-compra/pool?estado=${estado}&page_size=200`, {
    tenantSlug,
    accessToken,
  });
}

export function addToPool(
  tenantSlug: string,
  accessToken: string,
  origen: "manual" | "refill_stock",
  lineas: PoolLineaInPayload[],
) {
  return apiFetch<SolicitudCompraLinea[]>("/admin/solicitudes-compra/pool", {
    method: "POST",
    tenantSlug,
    accessToken,
    body: JSON.stringify({ origen, lineas }),
  });
}

export function deletePoolLinea(tenantSlug: string, accessToken: string, lineaId: string) {
  return apiFetch<undefined>(`/admin/solicitudes-compra/pool/lineas/${lineaId}`, {
    method: "DELETE",
    tenantSlug,
    accessToken,
  });
}

export function generarSolicitud(tenantSlug: string, accessToken: string, lineaIds: string[], notes?: string) {
  return apiFetch<SolicitudCompra>("/admin/solicitudes-compra/generar", {
    method: "POST",
    tenantSlug,
    accessToken,
    body: JSON.stringify({ linea_ids: lineaIds, notes }),
  });
}

export function fetchSolicitudes(tenantSlug: string, accessToken: string, estado?: string) {
  const params = estado ? `?estado=${estado}` : "";
  return apiFetch<SolicitudCompraListPage>(`/admin/solicitudes-compra${params}`, { tenantSlug, accessToken });
}

export function fetchSolicitudDetail(tenantSlug: string, accessToken: string, id: string) {
  return apiFetch<SolicitudCompra>(`/admin/solicitudes-compra/${id}`, { tenantSlug, accessToken });
}

export function cancelarSolicitud(tenantSlug: string, accessToken: string, id: string) {
  return apiFetch<SolicitudCompra>(`/admin/solicitudes-compra/${id}/cancelar`, {
    method: "PATCH",
    tenantSlug,
    accessToken,
  });
}

export interface ResolverSolicitudLinea {
  solicitud_linea_id: string;
  quantity?: number;
  estimated_unit_price?: string;
  release_id?: string;
}

export function resolverSolicitud(
  tenantSlug: string,
  accessToken: string,
  payload: { proveedor_id: string; date: string; notes?: string; lineas: ResolverSolicitudLinea[] },
) {
  return apiFetch<Comanda>("/admin/solicitudes-compra/resolver", {
    method: "POST",
    tenantSlug,
    accessToken,
    body: JSON.stringify(payload),
  });
}

export function resolverLineaDesdeEstoc(tenantSlug: string, accessToken: string, lineaId: string, itemId: string) {
  return apiFetch<SolicitudCompraLinea>(`/admin/solicitudes-compra/lineas/${lineaId}/resoldre-estoc`, {
    method: "POST",
    tenantSlug,
    accessToken,
    body: JSON.stringify({ item_id: itemId }),
  });
}

// --- Historial de compres (ver api/app/routers/erp/historial_compres.py) ---
// Gateado a vertical `records` en el propio backend — devuelve [] para
// cualquier otro vertical, nunca error, así que no hace falta manejar 403.

export function fetchHistorialResum(tenantSlug: string, accessToken: string, q?: string) {
  const params = q ? `?q=${encodeURIComponent(q)}` : "";
  return apiFetch<HistorialResumProveedor[]>(`/admin/historial-compres/resum${params}`, { tenantSlug, accessToken });
}

export function fetchHistorialLineas(
  tenantSlug: string,
  accessToken: string,
  params: { proveedor_id?: string; q?: string },
) {
  const query = new URLSearchParams();
  if (params.proveedor_id) query.set("proveedor_id", params.proveedor_id);
  if (params.q) query.set("q", params.q);
  return apiFetch<HistorialCompraLinea[]>(`/admin/historial-compres?${query}`, { tenantSlug, accessToken });
}

// --- Usuaris (para buscar/crear el cliente de una petición) ---

export function searchUsers(tenantSlug: string, accessToken: string, q: string) {
  return apiFetch<UserSearchResult[]>(`/admin/users/search?q=${encodeURIComponent(q)}`, { tenantSlug, accessToken });
}

export function createUser(tenantSlug: string, accessToken: string, payload: { email: string; name?: string; phone?: string }) {
  return apiFetch<UserSearchResult>("/admin/users", {
    method: "POST",
    tenantSlug,
    accessToken,
    body: JSON.stringify(payload),
  });
}

// --- Peticions de client (ver api/app/routers/erp/peticiones.py) ---

export function fetchPeticiones(tenantSlug: string, accessToken: string, estado?: string) {
  const params = estado ? `?estado=${estado}` : "";
  return apiFetch<PeticionCliente[]>(`/admin/peticiones${params}`, { tenantSlug, accessToken });
}

export function fetchPeticionDetail(tenantSlug: string, accessToken: string, id: string) {
  return apiFetch<PeticionCliente>(`/admin/peticiones/${id}`, { tenantSlug, accessToken }).catch(async () => {
    // No hay GET /peticiones/{id} dedicado — se busca en la lista completa.
    const all = await fetchPeticiones(tenantSlug, accessToken);
    const found = all.find((p) => p.id === id);
    if (!found) throw new ApiError(404, "Petició no trobada");
    return found;
  });
}

export interface CrearPeticionTiendaPayload {
  user_id: string;
  release_id?: string;
  free_artist?: string;
  free_title?: string;
  client_notes?: string;
}

export function crearPeticionTienda(tenantSlug: string, accessToken: string, payload: CrearPeticionTiendaPayload) {
  return apiFetch<PeticionCliente>("/admin/peticiones/tienda", {
    method: "POST",
    tenantSlug,
    accessToken,
    body: JSON.stringify(payload),
  });
}

export function catalogarPeticion(tenantSlug: string, accessToken: string, id: string, releaseId: string) {
  return apiFetch<PeticionCliente>(`/admin/peticiones/${id}/catalogar`, {
    method: "PATCH",
    tenantSlug,
    accessToken,
    body: JSON.stringify({ release_id: releaseId }),
  });
}

export function fijarPrecioPeticion(tenantSlug: string, accessToken: string, id: string, estimatedPrice: string) {
  return apiFetch<PeticionCliente>(`/admin/peticiones/${id}/precio`, {
    method: "PATCH",
    tenantSlug,
    accessToken,
    body: JSON.stringify({ estimated_price: estimatedPrice }),
  });
}

export function vincularPeticionASolicitud(
  tenantSlug: string,
  accessToken: string,
  id: string,
  cantidad: number,
  proveedorSugeridoId?: string,
) {
  return apiFetch<SolicitudCompraLinea>(`/admin/peticiones/${id}/vincular-solicitud`, {
    method: "POST",
    tenantSlug,
    accessToken,
    body: JSON.stringify({ cantidad, proveedor_sugerido_id: proveedorSugeridoId }),
  });
}

export function cancelarPeticion(tenantSlug: string, accessToken: string, id: string) {
  return apiFetch<PeticionCliente>(`/admin/peticiones/${id}/cancelar`, {
    method: "PATCH",
    tenantSlug,
    accessToken,
  });
}
