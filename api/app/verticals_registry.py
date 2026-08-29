"""Fuente única de qué providers de catálogo externo y qué arquetipos de
producto están REALMENTE implementados en código — evita que desde
superadmin se pueda asignar a un vertical una combinación sin tabla/servicio
real detrás (docs/ARQUITECTURA_CORE_VERTICAL.md §18, §20)."""

# Proveedor de búsqueda de referencias externas en compras (§19.1). Hoy solo
# discos tiene uno implementado (services/discogs.py, envuelto por
# require_discogs_enabled); añadir uno nuevo (ISBN/OpenLibrary para libros,
# etc.) es trabajo de desarrollo, no de configuración.
CATALOG_PROVIDERS: list[str] = ["discogs"]

# Arquetipo de extensión de Product/StockItem (§18) al que pertenece un
# vertical. "record" y "floristry" ya tienen tabla de extensión real
# (RecordProduct/RecordStockDetail, ReleaseFloristeria) — el resto son
# arquetipos planificados (agrupan qué verticales compartirán forma el día
# que se construya su tabla), sin tabla propia todavía.
PRODUCT_ARCHETYPES_IMPLEMENTED: list[str] = ["record", "floristry"]
PRODUCT_ARCHETYPES_PLANNED: list[str] = [
    "media_catalog", "consumable", "botanical", "retail_simple", "apparel_variant",
]
PRODUCT_ARCHETYPES: list[str] = PRODUCT_ARCHETYPES_IMPLEMENTED + PRODUCT_ARCHETYPES_PLANNED

# Claves de `tenant_features` (Fase 7, TenantFeature) que el código realmente
# consulta hoy — ver los `_set_feature("...")` en models/configuracio.py
# (ConfiguracioBotiga) y `require_discogs_enabled`. Spotify NO es una de
# estas: es un kill switch global (Settings.spotify_enabled + vertical,
# ver routers/spotify.py), no un feature por tenant.
TENANT_FEATURE_KEYS: list[str] = [
    "discogs_sync", "subscriptions", "catalog_browse_mode", "catalog_format_filter", "catalog_genre_filter",
]
