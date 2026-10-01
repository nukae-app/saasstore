// Tipos que reflejan la forma real de la respuesta de la API (ver
// api/app/schemas/auth.py y api/app/routers/admin/orders.py) — no se
// inventa vocabulario nuevo, se copian los nombres de campo tal cual.

export interface MobileTokenOut {
  access_token: string;
  refresh_token: string;
  token_type: string;
  // Solo lo rellena /auth/mobile/magic-link/verify — es la única llamada
  // donde el cliente todavía no sabe de qué tenant es.
  tenant_slug?: string | null;
}

export interface MobileTenantOption {
  slug: string;
  name: string;
}

export interface MobileLoginOut {
  status: "signed_in" | "choose_tenant";
  access_token: string | null;
  refresh_token: string | null;
  token_type: string;
  tenant_slug: string | null;
  tenants: MobileTenantOption[] | null;
}

export interface OrderSummary {
  id: string;
  email: string;
  status: string;
  total: string;
  coste_envio: string;
  metodo_envio: string | null;
  metodo_pago: string | null;
  numero_seguiment: string | null;
  created_at: string;
  origen: string;
  discogs_order_id: string | null;
  pendent_arribada: boolean;
  avisada_recollida_at: string | null;
}

export interface OrderPayment {
  id: string;
  proveedor: string;
  ds_order: string | null;
  estado: string;
  importe: string;
  ds_response_code: string | null;
  ds_authorisation_code: string | null;
  created_at: string;
}

export interface OrderItemDetail {
  order_item_id: string;
  item_id: string | null;
  artista: string | null;
  titulo: string | null;
  precio: string;
  condicion: string | null;
  estado_disco: string | null;
  item_status: string | null;
  pendent_arribada: boolean;
  devuelto: boolean;
}

export interface OrderDetail {
  id: string;
  email: string;
  status: string;
  total: string;
  coste_envio: string;
  metodo_envio: string | null;
  metodo_pago: string | null;
  direccion_envio: Record<string, unknown> | null;
  notas: string | null;
  numero_seguiment: string | null;
  transportista: string | null;
  created_at: string;
  origen: string;
  discogs_order_id: string | null;
  discogs_buyer: string | null;
  avisada_recollida_at: string | null;
  albara_id: string | null;
  payments: OrderPayment[];
  items: OrderItemDetail[];
}

// --- Catálogo (búsqueda para TPV — ver api/app/schemas/catalog.py) ---

export interface CatalogItem {
  id: string;
  price: string;
  list_price: string | null;
  condition: string;
  estado_disco: string | null;
  estado_funda: string | null;
  status: string;
  quantity: number;
  reserved_quantity: number;
}

export interface CatalogRelease {
  id: string;
  artista: string | null;
  title: string;
  sello: string | null;
  ean: string | null;
  formato: string | null;
  image_url: string | null;
  items: CatalogItem[];
}

export interface CatalogPage {
  total: number;
  page: number;
  page_size: number;
  results: CatalogRelease[];
}

// --- TPV (ver api/app/routers/erp/ventas_externas.py) ---

export interface TipusIva {
  id: number;
  name: string;
  percentage: string;
  is_rebu: boolean;
  active: boolean;
}

export interface VentaExternaLoteLinea {
  item_id?: string;
  description?: string;
  tipus_iva_id?: number;
  sale_price: string;
  quantity: number;
}

export type PaymentMethod = "efectivo" | "tarjeta" | "bizum" | "bono_cultural";

export interface VentaExternaOut {
  id: string;
  ticket_id: string;
  item_id: string | null;
  description: string | null;
  channel: string;
  payment_method: string;
  sale_price: string;
  date: string;
}

// --- Compras / Comandes (ver api/app/schemas/erp_comandas.py) ---

export interface Proveedor {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  active: boolean;
}

export interface ComandaLinea {
  id: string;
  release_id: string;
  artista: string;
  titulo: string;
  ean: string | null;
  quantity: number;
  estimated_unit_price: string | null;
  received_quantity: number;
  notes: string | null;
}

export interface Comanda {
  id: string;
  proveedor_id: string;
  proveedor_nombre: string;
  date: string;
  status: string;
  order_number: string | null;
  notes: string | null;
  sent_at: string | null;
  created_at: string;
  lineas: ComandaLinea[];
}

export interface ComandaLineaInPayload {
  release_id: string;
  quantity: number;
  estimated_unit_price?: string;
  notes?: string;
}

export interface RecepcionItemPayload {
  comanda_linea_id: string;
  price: string;
  condition: "nou" | "segona_ma";
  acquisition_cost?: string;
  estado_disco?: string;
  estado_funda?: string;
  quantity?: number;
}

export interface ReleaseRef {
  id: string;
  artista: string | null;
  title: string;
}

// --- Discogs (ver api/app/services/discogs.py / routers/admin/releases.py) ---
// Igual vocabulario que devuelve la API — "titulo"/"imagen_url" en
// castellano, no se traduce, es el propio contrato del backend.

export interface DiscogsSearchResult {
  discogs_release_id: number;
  artista: string | null;
  titulo: string;
  anio: number | null;
  sello: string | null;
  referencia: string | null;
  formato: string | null;
  genero: string | null;
  imagen_url: string | null;
}

export interface DiscogsReleaseDetail {
  tracklist?: unknown;
  credits?: unknown;
  pais?: string | null;
  estilos?: string | null;
  [key: string]: unknown;
}

// --- Sol·licituds de compra (ver api/app/schemas/erp_solicitudes.py) ---

export interface SolicitudCompraLinea {
  id: string;
  origen: "manual" | "refill_stock" | "peticion_cliente";
  release_id: string | null;
  artist: string | null;
  title: string | null;
  label: string | null;
  format: string | null;
  quantity: number;
  proveedor_sugerido_id: string | null;
  proveedor_sugerido_nombre: string | null;
  comanda_linea_id: string | null;
  item_resuelto_id: string | null;
  resuelta: boolean;
  notes: string | null;
}

export interface SolicitudCompra {
  id: string;
  numero: string;
  estado: "oberta" | "resolta" | "cancelada";
  origenes: string[];
  user_id: string | null;
  user_nom: string | null;
  notes: string | null;
  created_at: string;
  lineas: SolicitudCompraLinea[];
}

export interface SolicitudPoolPage {
  total: number;
  page: number;
  page_size: number;
  results: SolicitudCompraLinea[];
}

export interface SolicitudCompraListPage {
  total: number;
  page: number;
  page_size: number;
  results: SolicitudCompra[];
}

export interface RefillSugerencia {
  release_id: string;
  artista: string;
  titulo: string;
  formato: string | null;
  stock_actual: number;
  vendes_periode: number;
  tendencia: "accelerant" | "frenant" | "estable";
  dies_estoc: number;
  cantidad_sugerida: number;
  proveedor_sugerido_id: string | null;
  proveedor_sugerido_nombre: string | null;
}

export interface PoolLineaInPayload {
  release_id?: string;
  artist?: string;
  title?: string;
  label?: string;
  format?: string;
  quantity?: number;
  proveedor_sugerido_id?: string;
}

// --- Historial de compres (ver api/app/schemas/erp_historial.py) ---
// Gateado a vertical `records` en el propio backend (devuelve [] para
// cualquier otro vertical, nunca error) — ver ConfigPublic.vertical.

export interface HistorialResumProveedor {
  proveedor_id: string;
  proveedor_nombre: string;
  count: number;
  ultima_compra: string;
}

export interface HistorialCompraLinea {
  id: string;
  proveedor_id: string;
  proveedor_nombre: string;
  date: string;
  artist: string | null;
  title: string | null;
  label: string | null;
  format: string | null;
  quantity: number;
  cost_price: string | null;
  notes: string | null;
  release_id: string | null;
  ean: string | null;
}

// --- Peticions de client (ver api/app/schemas/erp_peticiones.py) ---

export type EstadoPeticion =
  | "pendent"
  | "pendent_acceptacio"
  | "acceptada"
  | "rebutjada"
  | "en_tramit"
  | "reservada"
  | "recollida"
  | "caducada"
  | "cancelada";

export interface PeticionCliente {
  id: string;
  user_id: string;
  user_nombre: string | null;
  user_email: string;
  channel: string;
  release_id: string | null;
  artista: string | null;
  titulo: string | null;
  status: EstadoPeticion;
  estimated_price: string | null;
  chosen_delivery_method: string | null;
  client_notes: string | null;
}

export interface UserSearchResult {
  id: string;
  name: string | null;
  email: string;
  phone: string | null;
}
