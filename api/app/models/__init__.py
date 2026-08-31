"""Modelos de datos, agrupados por dominio de negocio.

Cada tabla vive en su módulo de dominio (uno por bloque de tablas
relacionadas); este paquete solo las reexporta bajo `app.models`,
igual que antes, para que ningún `from .models import X` existente
necesite cambiar. Alembic (`alembic/env.py`) importa este paquete
entero para poblar `Base.metadata` antes de autogenerar."""

from ._base import TenantScoped

from .platform import (
    Tenant,
    Vertical,
    AccountingJurisdiction,
    PlatformAdmin,
    PlatformAdminRole,
    PlatformAdminAuditLog,
    TenantFeature,
    BillingPeriod,
    PlatformPlan,
    TenantBillingStatus,
    TenantBilling,
    PlatformInvoiceStatus,
    PlatformInvoice,
)

from .catalog import (
    Etiqueta,
    Seccio,
    ReleaseEtiqueta,
    Release,
    ReleaseFloristeria,
    RecordProduct,
    ReleaseImage,
)

from .stock import (
    ItemStatus,
    CondicionItem,
    Item,
    RecordStockDetail,
    StockHold,
)

from .users import (
    User,
    Identity,
    RefreshToken,
    AuthToken,
    Address,
)

from .orders import (
    Cart,
    CartItem,
    OrderStatus,
    OrderOrigen,
    Order,
    PaymentStatus,
    Payment,
    OrderItem,
)

from .compras import (
    Proveedor,
    TipoCompra,
    Compra,
    EstadoComanda,
    Comanda,
    ComandaLinea,
    HistorialCompra,
    EstadoSolicitud,
    OrigenSolicitud,
    SolicitudCompra,
    SolicitudCompraLinea,
)

from .actius import (
    AssetCategory,
    DepreciationMethod,
    FixedAsset,
    AssetDepreciationEntry,
)

from .peticiones import (
    EstadoPeticionCliente,
    PeticionCliente,
)

from .ventas_externas import (
    CanalVenta,
    MetodoPago,
    VentaExterna,
    CajaSession,
    TipoMovimiento,
    CajaMovimiento,
    DevolucionVenta,
    DevolucionCompra,
)

from .comptabilitat import (
    AccountType,
    AccountingAccount,
    CategoriaDespesa,
    EstatPagamentDespesa,
    EstatConciliacio,
    TipusIva,
    Despesa,
    CompteBancari,
    MovimentBancari,
    PeriodeComptable,
    CaixaDiaria,
    JournalSourceType,
    JournalEntryCounter,
    JournalEntry,
    JournalLine,
)

from .configuracio import (
    MargeConfig,
    TramEnviament,
    PesFormat,
    ConfiguracioBotiga,
)

from .cms import (
    Translation,
    Pagina,
    Post,
    PostPagina,
    Event,
)

from .spotify import (
    SpotifyConnection,
)

from .newsletter import (
    NewsletterCampaignStatus,
    NewsletterSendStatus,
    NewsletterCampaign,
    NewsletterSend,
)

from .subscripcions import (
    EstatSubscripcio,
    ConfiguracioSubscripcio,
    Subscripcio,
    EstatCobrament,
    CobramentSubscripcio,
    EstatAssignacio,
    Assignacio,
)

from .storefront import (
    HomeBlock,
    UploadedVideo,
)
