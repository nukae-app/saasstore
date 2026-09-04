"""Esquemas Pydantic de entrada/salida de la API (no exponen los modelos tal cual).

Cada bloque de esquemas vive en su módulo de dominio; este paquete solo los
reexporta bajo `app.schemas`, igual que antes, para que ningún
`from ..schemas import X` existente necesite cambiar."""


from .catalog import (
    ItemOut,
    EtiquetaOut,
    EtiquetaIn,
    GeneroFacetOut,
    SeccioOut,
    SeccioIn,
    ReleaseImageOut,
    ReleaseOut,
    CatalogPage,
    ReleaseIn,
    ItemIn,
    ItemUpdate,
    CatalogAgingBucketOut,
    CatalogAgingItemOut,
    CatalogAgingItemsOut,
    CatalogAgingOut,
    StockAlertItemOut,
    StockAlertsOut,
)

from .auth import (
    MagicLinkRequest,
    PasswordLoginRequest,
    RegisterRequest,
    SetPasswordRequest,
    TokenOut,
    MeOut,
)

from .cart import (
    CartAdd,
    CartItemOut,
    CartOut,
)

from .checkout import (
    AddressIn,
    CheckoutConfirm,
    OrderOut,
    OrderStatusUpdate,
    OrderPendentTiendaItemOut,
    OrderPendentTiendaOut,
    OrderMarcarPagadoTiendaIn,
)

from .erp_proveedores import (
    TIPUS_PROVEIDOR,
    METODES_PAGAMENT_PROV,
    ProveedorIn,
    ProveedorOut,
)

from .erp_compras import (
    CompraParticularItemIn,
    CompraParticularIn,
    CompraItemOut,
    CompraOut,
    ComprasStatsProveedorOut,
    ComprasStatsMesOut,
    ComprasStatsOut,
)

from .erp_comandas import (
    ComandaLineaIn,
    ComandaIn,
    ComandaLineaOut,
    ComandaOut,
    RecepcionItemIn,
    RecepcionIn,
)

from .erp_historial import (
    HistorialCompraOut,
    HistorialResumProveedorOut,
)

from .erp_solicitudes import (
    SolicitudCompraLineaIn,
    PoolLineasIn,
    SolicitudGenerarIn,
    SolicitudCompraLineaOut,
    SolicitudCompraOut,
    SolicitudResolverLineaIn,
    SolicitudResolverIn,
    ResoldreEstocIn,
    RefillSugerenciaOut,
    SolicitudPoolPage,
    SolicitudCompraListPage,
)

from .erp_peticiones import (
    PeticionClienteAdminOut,
    PeticionCatalogarIn,
    PeticionPrecioIn,
    PeticionVincularIn,
    PeticionVincularItemIn,
    PeticionTiendaIn,
    ReservaRecollidaOut,
)

from .erp_ventas_externas import (
    VentaExternaIn,
    VentaExternaLoteLineaIn,
    VentaExternaLoteIn,
    VincularUsuariTicketIn,
    VentaExternaOut,
)

from .erp_caja import (
    CajaSessionIn,
    CajaCierreIn,
    CajaSessionOut,
    CajaMovimientoIn,
    CajaMovimientoOut,
)

from .erp_devolucions import (
    DevolucionVentaIn,
    DevolucionVentaOut,
    DevolucionCompraIn,
    DevolucionCompraOut,
)

from .cms import (
    PostOut,
    EventOut,
)

from .comptabilitat import (
    TipusIvaIn,
    TipusIvaUpdate,
    TipusIvaOut,
    CATEGORIES_DESPESA,
    ESTATS_PAGAMENT,
    METODES_PAGAMENT_DESPESA,
    DespesaIn,
    DespesaUpdate,
    DespesaOut,
    DespesaDesDeComprasIn,
    CompteBancariIn,
    CompteBancariOut,
    MovimentBancariOut,
    ConciliarMovimentIn,
    ReglaConciliacioIn,
    ReglaConciliacioOut,
    DespesaSuggerimentOut,
    AccountingAccountOut,
    ApuntManualIn,
    AssentamentManualIn,
    ResultatLiniaDespesa,
    ResultatMensualOut,
    IVALiniaOut,
    IVATrimestralOut,
    PeriodeComptableOut,
    CAIXA_DIARIA_CAMPS,
    CaixaDiariaLiniaIn,
    CaixaDiariaLiniaOut,
    CaixaDiariaMesOut,
    VendesRealsLiniaOut,
    ApuntLlibreOut,
    AssentamentLlibreOut,
    LlibreDiariOut,
    LlibreMajorLiniaOut,
    LlibreMajorOut,
    BalancLiniaOut,
    BalancSituacioOut,
    ComptePyGLiniaOut,
    ComptePyGOut,
)

from .configuracio import (
    MargeConfigIn,
    MargeConfigUpdate,
    MargeConfigOut,
    TramEnviamentIn,
    TramEnviamentUpdate,
    TramEnviamentOut,
    PesFormatIn,
    PesFormatUpdate,
    PesFormatOut,
    ConfiguracioBotigaOut,
    ConfiguracioBotigaUpdate,
    ConfiguracioBotigaPublic,
    ThemeTokens,
    HEX_COLOR_RE,
    THEME_COLOR_FIELDS,
    CustomCssUpdateIn,
    FontSearchOut,
    FontSelectIn,
    TenantSecretsStatusOut,
    TenantSecretsUpdateIn,
)

from .subscripcions import (
    ConfiguracioSubscripcioOut,
    ConfiguracioSubscripcioUpdate,
    SubscripcioAltaIn,
    SubscripcioReleaseRebutOut,
    SubscripcioMeOut,
    SubscripcioMePatch,
    SubscripcioCatalogItemOut,
    InformeSubscripcioMensualOut,
)

from .actius import (
    CATEGORIES_ACTIU,
    FixedAssetIn,
    FixedAssetOut,
    AssetDepreciationEntryOut,
    GenerarAmortitzacionsOut,
)

from .aeat import (
    Model303TipusOut,
    Model303Out,
)

from .holded import (
    HoldedExportIn,
    HoldedExportLiniaOut,
    HoldedExportOut,
)

from .storefront import (
    HomeBlockOut,
    HomeBlockPublicOut,
    HomeBlockCreateIn,
    HomeBlockUpdateIn,
    HomeBlockReorderIn,
    UploadedVideoOut,
)

from .documents import (
    PressupostLiniaIn,
    PressupostIn,
    PressupostStatusIn,
    PressupostLiniaOut,
    PressupostOut,
    AlbaraIn,
    AlbaraOut,
)

from .pricing import (
    OfferCriteria,
    OfferItemIn,
    OfferItemOut,
    OfferIn,
    OfferOut,
    OfferPreviewItem,
    OfferPreviewOut,
    OfferOverlapOut,
    OfferApplyResultOut,
    CouponIn,
    CouponOut,
    CouponRedemptionOut,
    CouponApplyResultOut,
)
