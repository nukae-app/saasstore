"""Modelos de datos de Ultra-Local Records.

Decisiones de diseño (ver discusión de arquitectura):
- `Release` = el álbum (metadatos); `Item` = cada copia física única con su
  precio, grading y estado. Un mismo release puede tener varias copias a
  precios distintos.
- `OrderItem` guarda el precio en el momento de la compra (snapshot), y
  `Order` guarda la dirección de envío como JSON (snapshot). Los pedidos
  históricos nunca cambian aunque cambie el catálogo o la libreta de
  direcciones.
- Sin contraseñas: login con Google (tabla `Identity`) o magic link por
  email (tabla `AuthToken`). La sesión es nuestra: `RefreshToken`.
- `Order.user_id` es nullable: se permite comprar sin cuenta (guest
  checkout) y la FK usa SET NULL para poder anonimizar cuentas (RGPD)
  sin tocar los pedidos, que hay obligación legal de conservar.
"""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------

class Etiqueta(Base):
    """Etiqueta configurable per destacar releases al catàleg (Novetat, Recomanat, etc.)."""

    __tablename__ = "etiquetes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    nom_ca: Mapped[str] = mapped_column(String(100))
    nom_es: Mapped[str | None] = mapped_column(String(100))
    color: Mapped[str | None] = mapped_column(String(20))  # hex o classe Tailwind
    activa: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    posicio: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    releases: Mapped[list["Release"]] = relationship(
        secondary="release_etiquetes", back_populates="etiquetes"
    )


class Seccio(Base):
    """Cubeta física de la botiga (Nacional, Internacional, Alternatiu...).

    A diferència d'Etiqueta (M2M, distintius promocionals), un release viu
    en una sola cubeta: relació 1-a-molts.
    """

    __tablename__ = "seccions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    nom_ca: Mapped[str] = mapped_column(String(100))
    nom_es: Mapped[str | None] = mapped_column(String(100))
    color: Mapped[str | None] = mapped_column(String(20))  # hex o classe Tailwind
    activa: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    posicio: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    releases: Mapped[list["Release"]] = relationship(back_populates="seccio")


class ReleaseEtiqueta(Base):
    """M2M: un release pot tenir múltiples etiquetes."""

    __tablename__ = "release_etiquetes"

    release_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("releases.id", ondelete="CASCADE"), primary_key=True
    )
    etiqueta_id: Mapped[int] = mapped_column(
        ForeignKey("etiquetes.id", ondelete="CASCADE"), primary_key=True
    )


class Release(Base):
    """Un álbum/edición: los metadatos compartidos por todas sus copias."""

    __tablename__ = "releases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    artista: Mapped[str] = mapped_column(String(300), index=True)
    titulo: Mapped[str] = mapped_column(String(300), index=True)
    sello: Mapped[str | None] = mapped_column(String(500))
    referencia: Mapped[str | None] = mapped_column(String(200))
    ean: Mapped[str | None] = mapped_column(String(20), index=True)
    formato: Mapped[str | None] = mapped_column(String(120), index=True)
    anio: Mapped[int | None] = mapped_column(Integer)
    genero: Mapped[str | None] = mapped_column(String(200), index=True)
    descripcion: Mapped[str | None] = mapped_column(Text)
    imagen_url: Mapped[str | None] = mapped_column(String(800))
    pais: Mapped[str | None] = mapped_column(String(100))
    estilos: Mapped[str | None] = mapped_column(String(300))
    # Pes en grams: depèn del format (LP, 2xLP, 7"...), no de la còpia
    # concreta. S'usa per calcular el cost d'enviament (veure services/enviament.py).
    pes_g: Mapped[int | None] = mapped_column(Integer)
    tracklist: Mapped[list | None] = mapped_column(JSON)
    credits: Mapped[list | None] = mapped_column(JSON)
    discogs_release_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    spotify_album_id: Mapped[str | None] = mapped_column(String(50))
    properament: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    data_disponibilitat: Mapped[date | None] = mapped_column(Date)
    esta_sonant: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    seccio_id: Mapped[int | None] = mapped_column(
        ForeignKey("seccions.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["Item"]] = relationship(back_populates="release")
    etiquetes: Mapped[list["Etiqueta"]] = relationship(
        secondary="release_etiquetes", back_populates="releases"
    )
    seccio: Mapped["Seccio | None"] = relationship(back_populates="releases")
    images: Mapped[list["ReleaseImage"]] = relationship(
        back_populates="release", order_by="ReleaseImage.posicio", cascade="all, delete-orphan"
    )


class ReleaseImage(Base):
    """Imatge de la galeria d'un release (portada, posterior, etiqueta, vinil...)."""

    __tablename__ = "release_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    release_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("releases.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(String(800))
    posicio: Mapped[int] = mapped_column(Integer, default=0)
    # portada | posterior | etiqueta | vinil | altre
    tipus: Mapped[str | None] = mapped_column(String(40))
    # discogs | upload
    font: Mapped[str] = mapped_column(String(20), default="upload")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    release: Mapped["Release"] = relationship(back_populates="images")


class ItemStatus(str, enum.Enum):
    disponible = "disponible"
    reservado = "reservado"
    vendido = "vendido"
    retirado = "retirado"  # p. ej. vendido en tienda física o en Discogs


class CondicionItem(str, enum.Enum):
    nou = "nou"
    segona_ma = "segona_ma"


class Item(Base):
    """Para `segona_ma`: una copia física concreta, cada fila se vende como
    mucho una vez (ver `status`/`reserved_*` más abajo).

    Para `nou`: una línea de stock agregado — `cantidad` son las unidades
    físicas que hay en esta línea (todas idénticas: mismo precio, sin
    grading), y `status`/`reserved_*` NO se usan para regular la venta
    (solo `retirado` tiene sentido, para descatalogar la línea a mano).
    Las reservas y ventas parciales de una línea `nou` se gestionan con
    `cantidad_reservada` y la tabla `StockHold` (ver services/reservations.py),
    porque a diferencia de una copia única, una línea agregada puede tener
    varias reservas simultáneas de orígenes distintos (varios carritos, una
    petición de cliente, una asignación de club...)."""

    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint("cantidad >= 0", name="ck_items_cantidad_no_negativa"),
        CheckConstraint(
            "cantidad_reservada >= 0 AND cantidad_reservada <= cantidad",
            name="ck_items_cantidad_reservada_valida",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    release_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("releases.id", ondelete="RESTRICT"), index=True)
    codi_discogs: Mapped[int | None] = mapped_column(BigInteger, unique=True)  # listing id (columna CODI del Excel)
    precio: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    condicion: Mapped[CondicionItem] = mapped_column(
        Enum(CondicionItem, name="condicion_item"), default=CondicionItem.segona_ma, index=True
    )
    # Unidades físicas en esta línea. Para segona_ma siempre 1 (una copia = una
    # fila, como siempre); para nou puede ser N (ver docstring de la clase).
    cantidad: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    # Unidades de `cantidad` retenidas por reservas activas (StockHold). Solo
    # relevante para nou: segona_ma sigue usando status='reservado'/'vendido'.
    cantidad_reservada: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    estado_disco: Mapped[str | None] = mapped_column(String(60))   # grading Discogs: "Near Mint (NM or M-)"...
    estado_funda: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[ItemStatus] = mapped_column(
        Enum(ItemStatus, name="item_status"), default=ItemStatus.disponible, index=True
    )
    reserved_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reserved_by_cart_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("carts.id", ondelete="SET NULL"))
    # Reserva llarga (72h) per a una PeticionCliente que recull i paga a botiga
    # (sense passarel·la, per tant sense Order). Comparteix `reserved_until` i
    # el mateix alliberament mandrós que el carret; mai els dos FK alhora.
    reserved_for_peticion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "peticiones_cliente.id", ondelete="SET NULL",
            use_alter=True, name="fk_items_reserved_for_peticion_id",
        )
    )
    # Reserva mentre l'admin revisa una proposta d'assignació de subscripció
    # (veure services/subscripcions.py): mateix patró que reserved_for_peticion_id,
    # sense caducitat perquè el ritme el marca l'admin, no un client esperant.
    reserved_for_assignacio_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "subscripcio_assignacions.id", ondelete="SET NULL",
            use_alter=True, name="fk_items_reserved_for_assignacio_id",
        )
    )
    fecha_entrada: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # L'admin marca a mà quins exemplars concrets són elegibles per al club
    # del disc (veure routers/admin_subscripcions.py, pantalla "Catàleg"): és
    # la safata d'on tria l'algorisme d'assignació, mai tot el catàleg
    # disponible directament.
    subscripcio_pool: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", index=True)

    coste_adquisicion: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    compra_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("compras.id", ondelete="SET NULL"), index=True
    )
    rebu: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    release: Mapped[Release] = relationship(back_populates="items")
    compra: Mapped["Compra | None"] = relationship(back_populates="items")


# ---------------------------------------------------------------------------
# Usuarios y autenticación (sin contraseñas)
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    nombre: Mapped[str | None] = mapped_column(String(200))
    telefon: Mapped[str | None] = mapped_column(String(30))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    rol: Mapped[str] = mapped_column(String(20), default="cliente")  # cliente | admin
    activo: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    # Provada per magic link/Google en el moment del login; l'alta amb contrasenya
    # comença en False i cal confirmar-la clicant l'enllaç del mail (ver auth.py).
    email_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    consent_newsletter: Mapped[bool] = mapped_column(Boolean, default=False)
    idioma: Mapped[str] = mapped_column(String(5), default="ca")  # ca | es | en
    notas_internes: Mapped[str | None] = mapped_column(Text)  # notes visibles solo per admin
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    identities: Mapped[list["Identity"]] = relationship(back_populates="user")
    addresses: Mapped[list["Address"]] = relationship(back_populates="user")
    vendes: Mapped[list["VentaExterna"]] = relationship(back_populates="client", foreign_keys="VentaExterna.user_id")
    compres_client: Mapped[list["Compra"]] = relationship(back_populates="client", foreign_keys="Compra.user_id")
    peticiones: Mapped[list["PeticionCliente"]] = relationship(back_populates="user")


class Identity(Base):
    """Vínculo con un proveedor externo de identidad (Google hoy; otros mañana)."""

    __tablename__ = "identities"
    __table_args__ = (UniqueConstraint("provider", "provider_user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(40))         # "google"
    provider_user_id: Mapped[str] = mapped_column(String(255))  # el `sub` del id_token
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="identities")


class RefreshToken(Base):
    """Sesiones propias. Guardamos solo el hash del token, nunca el token."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthToken(Base):
    """Tokens de un solo uso para magic links y verificación de email tras el registro.

    Lleva `email` (no user_id) porque para el magic link el usuario puede no
    existir aún: se crea/recupera al canjear el enlace. `purpose` distingue
    ambos usos para que un token de un flujo no sirva para canjear el otro.
    """

    __tablename__ = "auth_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    purpose: Mapped[str] = mapped_column(String(20), default="magic_link")  # magic_link | verify_email
    # Idioma del visitante en el momento de PEDIR el enlace (no al canjearlo: el
    # magic link se abre a menudo desde el correu, en un altre dispositiu/navegador).
    idioma: Mapped[str | None] = mapped_column(String(5))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Address(Base):
    """Libreta de direcciones (para autorellenar). El pedido guarda su propia copia."""

    __tablename__ = "addresses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    nombre_destinatario: Mapped[str] = mapped_column(String(200))
    linea1: Mapped[str] = mapped_column(String(300))
    linea2: Mapped[str | None] = mapped_column(String(300))
    ciudad: Mapped[str] = mapped_column(String(120))
    cp: Mapped[str] = mapped_column(String(20))
    provincia: Mapped[str | None] = mapped_column(String(120))
    pais: Mapped[str] = mapped_column(String(2), default="ES")
    telefono: Mapped[str | None] = mapped_column(String(40))
    predeterminada: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="addresses")


# ---------------------------------------------------------------------------
# Carrito y pedidos
# ---------------------------------------------------------------------------

class Cart(Base):
    """Carrito persistente: de un usuario logueado o de una sesión anónima."""

    __tablename__ = "carts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    session_id: Mapped[str | None] = mapped_column(String(64), unique=True)  # cookie anónima
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list["CartItem"]] = relationship(back_populates="cart", cascade="all, delete-orphan")


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "item_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    cart_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    # Para segona_ma siempre 1 (una copia física). Para nou, cantidad deseada
    # de esa línea de stock agregado.
    cantidad: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    cart: Mapped[Cart] = relationship(back_populates="items")
    item: Mapped[Item] = relationship()


class OrderStatus(str, enum.Enum):
    pendiente_pago = "pendiente_pago"
    pagado = "pagado"
    enviado = "enviado"
    entregado = "entregado"
    cancelado = "cancelado"


class OrderOrigen(str, enum.Enum):
    """De dónde viene el pedido: checkout propio o venta detectada al Marketplace de Discogs.
    Comparten el mismo modelo (Order/OrderItem) y la misma pantalla de admin (Vendes web)."""

    web = "web"
    discogs = "discogs"
    subscripcio = "subscripcio"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    # SET NULL: una cuenta se puede anonimizar/borrar (RGPD) sin destruir el pedido
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    email_contacto: Mapped[str] = mapped_column(String(320))
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"), default=OrderStatus.pendiente_pago, index=True
    )
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    # Snapshot del cost d'enviament calculat a /checkout/confirm (veure
    # services/enviament.py); ja inclòs a `total`. 0 si recogida_tienda.
    coste_envio: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"), server_default="0")
    metodo_envio: Mapped[str] = mapped_column(String(40))  # "envio" | "recogida_tienda"
    # "redsys" (pago online) | "tienda" (paga al recoger; solo con recogida_tienda,
    # útil también para hacer pruebas de checkout sin pasarela real)
    metodo_pago: Mapped[str] = mapped_column(String(20), default="redsys", server_default="redsys")
    direccion_envio: Mapped[dict | None] = mapped_column(JSON)  # snapshot; null si recogida en tienda
    notas: Mapped[str | None] = mapped_column(Text)
    # Snapshot del idioma en que se hizo el checkout: para invitados (user_id
    # nulo) es la única señal de idioma disponible para el email de
    # confirmación y no se puede resolver más tarde (el webhook de Redsys que
    # confirma el pago no tiene contexto de request/sesión).
    idioma: Mapped[str] = mapped_column(String(5), default="ca", server_default="ca")
    cobrat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Etiqueta/enviament: de moment sempre a mà (número de seguiment i
    # transportista introduïts per l'admin); no hi ha integració amb cap API
    # de missatgeria.
    numero_seguiment: Mapped[str | None] = mapped_column(String(100))
    transportista: Mapped[str | None] = mapped_column(String(100))
    # Recollida a botiga: quan s'avisa el client per email que ja pot venir a
    # buscar la comanda (veure POST /admin/orders/{id}/avisar-recollida). Null
    # mentre encara no se li ha avisat.
    avisada_recollida_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Venda detectada al Marketplace de Discogs (origen='discogs'): mateix model, mateixa pantalla.
    origen: Mapped[OrderOrigen] = mapped_column(
        Enum(OrderOrigen, name="order_origen"), default=OrderOrigen.web, server_default="web", index=True
    )
    discogs_order_id: Mapped[str | None] = mapped_column(String(40), unique=True, index=True)
    discogs_buyer: Mapped[str | None] = mapped_column(String(120))

    # Carrito que reservó los ejemplares (ver services/reservations.py). Se
    # guarda para poder llamar a confirm_sale desde la notificación de pago
    # (server-to-server, sin cookie de carrito) una vez Redsys autoriza el cobro.
    cart_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("carts.id", ondelete="SET NULL"))

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")
    payments: Mapped[list["Payment"]] = relationship(back_populates="order", order_by="Payment.created_at")


class PaymentStatus(str, enum.Enum):
    creado = "creado"
    autorizado = "autorizado"
    denegado = "denegado"
    error = "error"


class Payment(Base):
    """Intento de cobro con una pasarela externa (Redsys). Un pedido puede
    tener varios intentos (p. ej. si el primero es denegado y se reintenta);
    el pedido solo pasa a `pagado` cuando UN intento llega a `autorizado`,
    vía la notificación server-to-server (ver routers/payments.py)."""

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    proveedor: Mapped[str] = mapped_column(String(20), default="redsys")
    # Ds_Merchant_Order: código que identifica el intento ante Redsys (4-12
    # caracteres, los 4 primeros numéricos). No es el id del Order.
    ds_order: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    importe: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    moneda: Mapped[str] = mapped_column(String(3), default="EUR")
    estado: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"), default=PaymentStatus.creado, index=True
    )
    ds_response_code: Mapped[str | None] = mapped_column(String(10))
    ds_authorisation_code: Mapped[str | None] = mapped_column(String(20))
    raw_notification: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    order: Mapped["Order"] = relationship(back_populates="payments")


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        # Una copia de segunda mano solo puede venderse una vez — igual que
        # antes, pero ahora como índice único PARCIAL: una línea `nou` (stock
        # agregado) puede aparecer en varios OrderItem a lo largo del tiempo,
        # o con cantidad>1 en una misma línea. `condicion` es un snapshot (ver
        # más abajo), así que este índice no depende del estado actual de Item.
        Index(
            "ix_order_items_item_id_unico_segona_ma", "item_id",
            unique=True,
            postgresql_where=text("condicion = 'segona_ma'"),
            sqlite_where=text("condicion = 'segona_ma'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    # Nullable: línia "de reserva" d'una petició de client pagada per
    # endavant (Via 1) que encara no té exemplar físic assignat — en aquest
    # cas `release_id` diu quin disc s'ha de lliurar; quan arriba l'exemplar
    # real, s'omple `item_id` i es buida `release_id` (veure erp.py,
    # resolució de peticions).
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("items.id", ondelete="RESTRICT"))
    release_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("releases.id", ondelete="RESTRICT"), index=True)
    precio: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # snapshot del precio al comprar
    # Snapshot de la condición al vender (igual criterio que `precio`): para
    # nou puede haber varias OrderItem sobre la misma línea de Item a lo
    # largo del tiempo, así que hace falta guardar aquí qué condición tenía
    # en el momento de la venta, no leerla de `item.condicion` (que además
    # puede quedar en None si `item_id` es una línea de reserva sin asignar).
    condicion: Mapped[CondicionItem | None] = mapped_column(Enum(CondicionItem, name="condicion_item"))
    # Unidades vendidas en esta línea. Para segona_ma siempre 1; para nou
    # puede ser N (varias unidades de la misma línea en un mismo pedido).
    cantidad: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    # Snapshot del tipus d'IVA aplicat en el moment de la venda (nou vs segona mà/REBU).
    # Per a línies de reserva (item_id=None) es queda a None fins que
    # s'assigna l'exemplar real: l'IVA (REBU o no) depèn de la seva condició.
    tipus_iva_id: Mapped[int | None] = mapped_column(
        ForeignKey("tipus_iva.id", ondelete="SET NULL"), index=True
    )
    iva_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    iva_import: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    order: Mapped[Order] = relationship(back_populates="items")
    item: Mapped["Item | None"] = relationship()
    release: Mapped["Release | None"] = relationship()
    tipus_iva: Mapped["TipusIva | None"] = relationship()


# ---------------------------------------------------------------------------
# ERP — entradas de stock (compras) y ventas externas
# ---------------------------------------------------------------------------

class Proveedor(Base):
    """Proveedor unificat: discos i serveis generals (llum, gestor, transport...)."""

    __tablename__ = "proveedores"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    nombre: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    # tipo: distribuidor | proveidor_online | subministrador | professional | transport | particular | altres
    tipo: Mapped[str | None] = mapped_column(String(60))
    nif: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(320))
    telefon: Mapped[str | None] = mapped_column(String(40))
    direccion: Mapped[str | None] = mapped_column(String(500))
    contacto: Mapped[str | None] = mapped_column(String(300))
    actiu: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    iban_proveidor: Mapped[str | None] = mapped_column(String(34))
    # transferencia | rebut_domiciliat | targeta | efectiu | paypal_altres
    metode_pagament: Mapped[str | None] = mapped_column(String(30))
    dies_pagament: Mapped[int | None] = mapped_column(Integer)     # 0, 30, 60, 90...
    dia_pagament_mes: Mapped[int | None] = mapped_column(Integer)  # dia fix del mes (1-31)
    notas: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    compras: Mapped[list["Compra"]] = relationship(back_populates="proveedor")
    despeses: Mapped[list["Despesa"]] = relationship(back_populates="proveidor", foreign_keys="Despesa.proveidor_id")
    historial_compres: Mapped[list["HistorialCompra"]] = relationship(back_populates="proveedor")


class TipoCompra(str, enum.Enum):
    proveedor = "proveedor"
    particular = "particular"


class Compra(Base):
    """Lote de entrada de stock: compra a proveedor o a un particular en mostrador."""

    __tablename__ = "compras"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    tipo: Mapped[TipoCompra] = mapped_column(
        Enum(TipoCompra, name="tipo_compra"), index=True
    )
    proveedor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), index=True
    )
    nombre_particular: Mapped[str | None] = mapped_column(String(300))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # Referència de l'albarà/nota d'entrega (no és la factura: la factura es
    # registra a part i pot agrupar diverses recepcions, vegeu Despesa).
    num_albaran: Mapped[str | None] = mapped_column(String(200))
    notas: Mapped[str | None] = mapped_column(Text)
    # Coste total de ESTA recepción, fijado al crearla. Antes del stock
    # agregado bastaba con sumar `Item.coste_adquisicion` de `Compra.items`
    # (cada Item pertenecía a una sola Compra); ahora una línea `nou` puede
    # acumular varias recepciones en la MISMA fila `Item` (que solo puede
    # apuntar a una `compra_id`, la última), así que ese cálculo derivado ya
    # no basta para saber cuánto costó cada recepción concreta — por eso se
    # guarda aquí explícitamente (usado por comptabilitat.py al facturar).
    coste_total: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    comanda_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comandas.id", ondelete="SET NULL"), index=True
    )

    # Diverses recepcions (Compra) es poden facturar juntes amb una única Despesa.
    despesa_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("despeses.id", ondelete="SET NULL"), index=True
    )

    proveedor: Mapped["Proveedor | None"] = relationship(back_populates="compras")
    client: Mapped["User | None"] = relationship(back_populates="compres_client", foreign_keys=[user_id])
    items: Mapped[list["Item"]] = relationship(back_populates="compra")
    despesa: Mapped["Despesa | None"] = relationship(back_populates="compras")
    comanda: Mapped["Comanda | None"] = relationship(back_populates="compras")


class EstadoComanda(str, enum.Enum):
    esborrany = "esborrany"
    enviada = "enviada"
    rebuda_parcial = "rebuda_parcial"
    rebuda = "rebuda"
    cancelada = "cancelada"


class Comanda(Base):
    """Comanda a proveïdor: es genera abans que arribi la mercaderia. La
    recepció (total o parcial) crea una Compra -> Items reals (pujada a stock),
    enllaçada aquí per traçabilitat."""

    __tablename__ = "comandas"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    proveedor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), index=True
    )
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[EstadoComanda] = mapped_column(
        Enum(EstadoComanda, name="estado_comanda"), default=EstadoComanda.esborrany, index=True
    )
    num_comanda: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # "2026-000001"
    notas: Mapped[str | None] = mapped_column(Text)
    enviada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    proveedor: Mapped["Proveedor"] = relationship()
    lineas: Mapped[list["ComandaLinea"]] = relationship(
        back_populates="comanda", cascade="all, delete-orphan", order_by="ComandaLinea.created_at"
    )
    compras: Mapped[list["Compra"]] = relationship(back_populates="comanda")


class ComandaLinea(Base):
    """Línia d'una comanda: disc + quantitat demanada. cantidad_rebuda es va
    incrementant a cada recepció (pot ser parcial, en diverses tongades)."""

    __tablename__ = "comanda_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    comanda_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("comandas.id", ondelete="CASCADE"), index=True
    )
    release_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("releases.id", ondelete="RESTRICT"), index=True
    )
    cantidad: Mapped[int] = mapped_column(Integer)
    precio_unitario_estimado: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    cantidad_rebuda: Mapped[int] = mapped_column(Integer, default=0)
    notas: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    comanda: Mapped["Comanda"] = relationship(back_populates="lineas")
    release: Mapped["Release"] = relationship()


class HistorialCompra(Base):
    """Línia de compra històrica (dels fulls de càlcul propis, anteriors al
    sistema de Comanda/Compra). No genera stock ni toca `items`: és només
    senyal de lectura per al motor de recomanació de proveïdor — donat un
    disc que es vol comprar, quin proveïdor l'ha subministrat abans (per
    segell/artista) i amb quina recència, abans de crear una Comanda real."""

    __tablename__ = "historial_compres"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    proveedor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), index=True
    )
    fecha: Mapped[date] = mapped_column(Date, index=True)
    artista: Mapped[str | None] = mapped_column(String(300), index=True)
    titulo: Mapped[str | None] = mapped_column(String(300), index=True)
    sello: Mapped[str | None] = mapped_column(String(500), index=True)
    formato: Mapped[str | None] = mapped_column(String(120))
    cantidad: Mapped[int] = mapped_column(Integer, default=1)
    precio_coste: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    # Enllaç opcional al catàleg actual, si la importació ha pogut fer el matching.
    release_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("releases.id", ondelete="SET NULL"), index=True
    )
    notas: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    proveedor: Mapped["Proveedor"] = relationship(back_populates="historial_compres")
    release: Mapped["Release | None"] = relationship()


class EstadoSolicitud(str, enum.Enum):
    oberta = "oberta"
    resolta = "resolta"
    cancelada = "cancelada"


class OrigenSolicitud(str, enum.Enum):
    manual = "manual"
    refill_stock = "refill_stock"  # generada pel futur motor de reposició segons vendes
    peticion_cliente = "peticion_cliente"  # generada a partir d'una PeticionCliente acceptada


class SolicitudCompra(Base):
    """Llista de discos que es volen comprar, sense proveïdor encara triat
    (a diferència de `Comanda`, que sempre en té un). És el punt d'entrada
    flexible del flux de compres: es pot començar aquí, o saltar-se-la i
    crear una `Comanda` directament quan ja se sap a qui es compra. Cada
    línia es 'resol' quan s'assigna a una `ComandaLinea` d'un proveïdor
    concret; la sol·licitud pot acabar repartida entre diverses comandes."""

    __tablename__ = "solicitudes_compra"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    estado: Mapped[EstadoSolicitud] = mapped_column(
        Enum(EstadoSolicitud, name="estado_solicitud"), default=EstadoSolicitud.oberta, index=True
    )
    origen: Mapped[OrigenSolicitud] = mapped_column(
        Enum(OrigenSolicitud, name="origen_solicitud"), default=OrigenSolicitud.manual, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    notas: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lineas: Mapped[list["SolicitudCompraLinea"]] = relationship(
        back_populates="solicitud", cascade="all, delete-orphan", order_by="SolicitudCompraLinea.created_at"
    )
    user: Mapped["User | None"] = relationship()


class SolicitudCompraLinea(Base):
    """Línia: un disc que es vol comprar. `release_id` si ja existeix al
    catàleg; si no, es descriu a mà (artista/titulo/sello/formato), com a
    l'alta d'un disc nou. `proveedor_sugerido_id` és el proveïdor
    suggerit (avui es tria a mà; en el futur, el motor de recomanació per
    historial de compres). Es resol de dues maneres possibles, mai les
    dues alhora: `comanda_linea_id` (s'ha comprat a proveïdor) o
    `item_resuelto_id` (ja hi havia un exemplar a estoc i no ha calgut
    comprar-lo)."""

    __tablename__ = "solicitud_compra_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    solicitud_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("solicitudes_compra.id", ondelete="CASCADE"), index=True
    )
    release_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("releases.id", ondelete="SET NULL"), index=True
    )
    artista: Mapped[str | None] = mapped_column(String(300))
    titulo: Mapped[str | None] = mapped_column(String(300))
    sello: Mapped[str | None] = mapped_column(String(500))
    formato: Mapped[str | None] = mapped_column(String(120))
    cantidad: Mapped[int] = mapped_column(Integer, default=1)
    proveedor_sugerido_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("proveedores.id", ondelete="SET NULL"), index=True
    )
    comanda_linea_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comanda_items.id", ondelete="SET NULL"), index=True
    )
    item_resuelto_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("items.id", ondelete="SET NULL"), index=True
    )
    notas: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    solicitud: Mapped["SolicitudCompra"] = relationship(back_populates="lineas")
    release: Mapped["Release | None"] = relationship()
    proveedor_sugerido: Mapped["Proveedor | None"] = relationship()
    comanda_linea: Mapped["ComandaLinea | None"] = relationship()
    item_resuelto: Mapped["Item | None"] = relationship()


class EstadoPeticionCliente(str, enum.Enum):
    pendent = "pendent"                    # creada pel client
    pendent_acceptacio = "pendent_acceptacio"  # l'admin ha posat preu, esperant que el client accepti
    acceptada = "acceptada"                # client ha acceptat el preu (encara no s'ha comprat res)
    rebutjada = "rebutjada"                # client ha rebutjat el preu — fi, no es compra
    en_tramit = "en_tramit"                # enllaçada a una SolicitudCompra/Comanda real
    reservada = "reservada"                # exemplar arribat, recollida a botiga sense pagar (72h)
    recollida = "recollida"                # completada (recollida o Order pagat)
    caducada = "caducada"                  # no ha respost a temps, o no ha vingut a recollir-la
    cancelada = "cancelada"


class PeticionCliente(Base):
    """Petició d'un client per un disc SENSE ESTOC (ja al catàleg o no).
    No és una reserva: és una intenció de compra. Només es compra a
    proveïdor si el client accepta el preu abans (per no acabar amb estoc
    que ningú vol). Quan arriba l'exemplar: si el client paga online
    (enviament o recollida pagada), és un Order normal sense caducitat; si
    tria recollir i pagar a botiga, aquí sí que s'aplica una reserva de 72h
    sobre l'Item (veure `Item.reserved_for_peticion_id`)."""

    __tablename__ = "peticiones_cliente"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # web (creada pel client) | tienda (l'admin la crea per una trucada o un
    # client de mostrador). En 'tienda' es salta l'acceptació online del preu:
    # fijar_precio_peticion la passa directament a 'acceptada' amb entrega
    # 'recollida_paga_botiga' (veure erp.py).
    canal: Mapped[str] = mapped_column(String(20), default="web")

    # Un dels dos: disc ja catalogat sense estoc, o descripció lliure (fora de catàleg).
    release_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("releases.id", ondelete="SET NULL"), index=True
    )
    artista_lliure: Mapped[str | None] = mapped_column(String(300))
    titulo_lliure: Mapped[str | None] = mapped_column(String(300))
    notas_cliente: Mapped[str | None] = mapped_column(Text)

    estado: Mapped[EstadoPeticionCliente] = mapped_column(
        Enum(EstadoPeticionCliente, name="estado_peticion_cliente"),
        default=EstadoPeticionCliente.pendent, index=True,
    )
    precio_estimado: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    # envio | recollida_paga_ara | recollida_paga_botiga — triat pel client en acceptar el preu.
    metodo_entrega_triat: Mapped[str | None] = mapped_column(String(30))

    solicitud_compra_linea_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("solicitud_compra_items.id", ondelete="SET NULL"), index=True
    )
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("items.id", ondelete="SET NULL"), index=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), index=True
    )

    notas_admin: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="peticiones")
    release: Mapped["Release | None"] = relationship()
    solicitud_compra_linea: Mapped["SolicitudCompraLinea | None"] = relationship()
    item: Mapped["Item | None"] = relationship(foreign_keys=[item_id])
    order: Mapped["Order | None"] = relationship()


class CanalVenta(str, enum.Enum):
    mostrador = "mostrador"
    discogs = "discogs"
    otro = "otro"


class MetodoPago(str, enum.Enum):
    efectivo = "efectivo"
    tarjeta = "tarjeta"
    bizum = "bizum"
    bono_cultural = "bono_cultural"


class VentaExterna(Base):
    """Venta no realizada por la web: mostrador (TPV) o Discogs."""

    __tablename__ = "ventas_externas"
    __table_args__ = (
        # Mismo criterio que order_items: una copia de segunda mano solo se
        # vende una vez; una línea nou (stock agregado) puede aparecer en
        # varias ventas externas a lo largo del tiempo.
        Index(
            "ix_ventas_externas_item_id_unico_segona_ma", "item_id",
            unique=True,
            postgresql_where=text("condicion = 'segona_ma'"),
            sqlite_where=text("condicion = 'segona_ma'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    # Agrupa totes les línies venudes en una mateixa operació de TPV (venda
    # individual o cistella sencera): comparteixen el mateix `ticket_id`
    # encara que cadascuna tingui el seu propi `id`. Permet mostrar el
    # "Resum vendes" com a tiquet (capçalera: data/client/pagament/total) +
    # línies, en lloc d'una fila solta per exemplar venut. Assignat sempre
    # explícitament a erp.py (`create_venta_externa`/`_lote`), mai deixat al
    # default de la columna — si no, cada línia d'un mateix lot en tindria un
    # de diferent.
    ticket_id: Mapped[uuid.UUID] = mapped_column(index=True, default=_uuid)
    # Nullable: un "article manual" (llibre, samarreta...) no ve del catàleg
    # d'`items`, així que no té ejemplar que reservar — porta `descripcion`
    # en el seu lloc (veure abajo).
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("items.id", ondelete="RESTRICT"))
    # Snapshot de la condición al vender (mismo criterio que en OrderItem).
    condicion: Mapped[CondicionItem | None] = mapped_column(Enum(CondicionItem, name="condicion_item"))
    # Unidades vendidas. Para segona_ma siempre 1; para nou puede ser N.
    cantidad: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    # Només per a articles manuals (item_id NULL): descripció lliure del que
    # es ven (p.ex. "Llibre - Vinyl. La biblia del col·leccionista").
    descripcion: Mapped[str | None] = mapped_column(String(300))
    canal: Mapped[CanalVenta] = mapped_column(
        Enum(CanalVenta, name="canal_venta"), index=True
    )
    metodo_pago: Mapped[MetodoPago] = mapped_column(
        Enum(MetodoPago, name="metodo_pago"), default=MetodoPago.efectivo, index=True
    )
    precio_venta: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    nombre_cliente: Mapped[str | None] = mapped_column(String(300))
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    discogs_sale_id: Mapped[int | None] = mapped_column(BigInteger)
    notas: Mapped[str | None] = mapped_column(Text)
    # NULL = pendent de cobrar (targeta/Discogs); non-NULL = cobrat (efectiu sempre immediat)
    cobrat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Snapshot del tipus d'IVA aplicat en el moment de la venda (nou vs segona mà/REBU).
    tipus_iva_id: Mapped[int | None] = mapped_column(
        ForeignKey("tipus_iva.id", ondelete="SET NULL"), index=True
    )
    iva_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    iva_import: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    item: Mapped["Item | None"] = relationship()
    client: Mapped["User | None"] = relationship(back_populates="vendes", foreign_keys=[user_id])
    tipus_iva: Mapped["TipusIva | None"] = relationship()


class CajaSession(Base):
    """Sesión de caja: apertura y cierre de un turno, con control de efectivo."""

    __tablename__ = "caja_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    fecha_apertura: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    fondo_inicial: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    fecha_cierre: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_ventas_efectivo: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    total_entradas: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    total_salidas: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    conteo_real: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    notas: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    movimientos: Mapped[list["CajaMovimiento"]] = relationship(back_populates="session", order_by="CajaMovimiento.fecha")


class TipoMovimiento(str, enum.Enum):
    entrada = "entrada"
    salida = "salida"


class CajaMovimiento(Base):
    """Movimiento manual de caja: entrada de efectivo o salida (compra, ingreso en banco...)."""

    __tablename__ = "caja_movimientos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("caja_sessions.id", ondelete="CASCADE"), index=True
    )
    tipo: Mapped[TipoMovimiento] = mapped_column(
        Enum(TipoMovimiento, name="tipo_movimiento"), index=True
    )
    concepto: Mapped[str] = mapped_column(String(300))
    importe: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["CajaSession"] = relationship(back_populates="movimientos")


# ---------------------------------------------------------------------------
# Comunidad: blog y agenda
# ---------------------------------------------------------------------------

class DevolucionVenta(Base):
    """Devolución de una venta (web o TPV). No borra el registro original."""

    __tablename__ = "devolucions_venta"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    # Exactamente uno de los dos debe estar relleno
    order_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("order_items.id", ondelete="RESTRICT"), index=True
    )
    venta_externa_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ventas_externas.id", ondelete="RESTRICT"), index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("items.id", ondelete="RESTRICT"), index=True
    )
    # Unidades devueltas. Para segona_ma siempre 1; para nou puede ser N (no
    # hace falta que coincida con toda la cantidad vendida en la línea original).
    cantidad: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    motivo: Mapped[str] = mapped_column(Text)
    # Qué pasa con el disco: vuelve a la venta o se retira (dañado)
    destino_item: Mapped[str] = mapped_column(String(20), default="disponible")
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    notas: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    item: Mapped["Item"] = relationship()
    order_item: Mapped["OrderItem | None"] = relationship()
    venta_externa: Mapped["VentaExterna | None"] = relationship()


class DevolucionCompra(Base):
    """Devolución de una compra al proveedor o particular."""

    __tablename__ = "devolucions_compra"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("items.id", ondelete="RESTRICT"), index=True
    )
    compra_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("compras.id", ondelete="SET NULL"), index=True
    )
    # Unidades devueltas al proveedor/particular. Para segona_ma siempre 1.
    cantidad: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    motivo: Mapped[str] = mapped_column(Text)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    notas: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    item: Mapped["Item"] = relationship()
    compra: Mapped["Compra | None"] = relationship()


# ---------------------------------------------------------------------------
# Comptabilitat — despeses, banc i periodes
# ---------------------------------------------------------------------------

class CategoriaDespesa(str, enum.Enum):
    compres_material = "compres_material"        # discos (vinculat a Compra)
    subministraments = "subministraments"        # llum, aigua, gas
    lloguer = "lloguer"
    comunicacions = "comunicacions"              # telèfon, internet
    serveis_professionals = "serveis_professionals"
    transport = "transport"
    material_oficina = "material_oficina"
    publicitat = "publicitat"
    altres = "altres"


class EstatPagamentDespesa(str, enum.Enum):
    pendent = "pendent"
    pagat = "pagat"
    vencut = "vencut"


class EstatConciliacio(str, enum.Enum):
    pendent = "pendent"
    conciliat = "conciliat"
    ignorat = "ignorat"   # transferència entre comptes propis, etc.


class TipusIva(Base):
    """Tipus d'IVA configurables: percentatge i quin règim representen.

    `per_defecte_nou` / `per_defecte_segona_ma` marquen quin tipus s'aplica
    automàticament a una venda segons `Item.condicion` (només n'hi pot haver
    un actiu de cada a la vegada, validat a l'endpoint). A compra es tria
    sempre a mà entre els tipus actius.
    """

    __tablename__ = "tipus_iva"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nom: Mapped[str] = mapped_column(String(200))
    percentatge: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    # Règim especial de béns usats: l'IVA es calcula sobre el marge (venda - cost), no sobre el preu.
    es_rebu: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    per_defecte_nou: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    per_defecte_segona_ma: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    actiu: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MargeConfig(Base):
    """Marges configurables per suggerir el preu de venda a la recepció de
    stock (compra_adquisicion -> preu). `per_defecte_nou`/`per_defecte_segona_ma`
    marquen quin marge es fa servir automàticament segons la condició triada
    (només un actiu de cada a la vegada, validat a l'endpoint, mateix patró
    que TipusIva). El càlcul és sempre un suggeriment: el preu final es pot
    editar sempre a mà a la recepció."""

    __tablename__ = "marges_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nom: Mapped[str] = mapped_column(String(200))
    percentatge: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    per_defecte_nou: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    per_defecte_segona_ma: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    actiu: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TramEnviament(Base):
    """Trams de pes per país per calcular el cost d'enviament al checkout
    (veure services/enviament.py): cada línia és (país, pes màxim, preu). Un
    país només és venedor si té almenys un tram actiu — no hi ha cap llista
    de països hardcodejada, afegir-ne un de nou és només crear un tram des
    de l'admin, sense tocar codi. No hi ha cap API de tarifes de missatgeria
    en temps real: aquesta taula és la nostra pròpia tarifa, editable des de
    l'admin sense redesplegar, mateix patró que `MargeConfig`/`TipusIva`."""

    __tablename__ = "trams_enviament"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pais: Mapped[str] = mapped_column(String(2), index=True)  # ISO 3166-1 alpha-2, p. ex. "ES", "FR"
    pes_maxim_g: Mapped[int] = mapped_column(Integer)  # tram vàlid fins aquest pes (inclusiu)
    preu: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    actiu: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PesFormat(Base):
    """Pes per defecte (grams) segons `Release.formato`, per no haver
    d'omplir `Release.pes_g` disc a disc. Resolució a services/enviament.py:
    pes propi de la còpia > pes per defecte del seu format > DEFAULT_PES_G
    global. Editable des de l'admin, mateix patró que `TramEnviament`."""

    __tablename__ = "pes_format"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    formato: Mapped[str] = mapped_column(String(120), unique=True)
    pes_g: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConfiguracioBotiga(Base):
    """Configuració general de la botiga: fila singleton (sempre id=1).

    Dades fiscals (capçalera del PDF de comandes), contacte/xarxes (footer
    públic) i paràmetres operatius (minuts de reserva de stock). Abans
    vivien a `Settings`/`.env`; aquí són editables des de l'admin sense
    redesplegar."""

    __tablename__ = "configuracio_botiga"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nom_fiscal: Mapped[str] = mapped_column(String(200))
    nif: Mapped[str | None] = mapped_column(String(20))
    adreca: Mapped[str] = mapped_column(Text)
    telefon: Mapped[str | None] = mapped_column(String(30))
    email_contacte: Mapped[str | None] = mapped_column(String(200))
    instagram_url: Mapped[str | None] = mapped_column(String(300))
    horari: Mapped[str | None] = mapped_column(Text)
    reserva_minuts: Mapped[int] = mapped_column(Integer, default=20)
    # Interruptor general del club de subscripció: si és False, l'API pública
    # de plans no retorna res i el front no mostra l'opció (veure
    # routers/subscripcions_public.py).
    subscripcions_actives: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Mode manteniment: bloqueja /checkout/start i /checkout/confirm per a
    # qualsevol usuari que no sigui admin (veure routers/checkout.py) i el
    # front mostra un banner "en construcció" (veure useManteniment.js).
    # L'admin sempre pot provar el flux de compra sencer amb aquest actiu.
    manteniment_actiu: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Despesa(Base):
    """Factura de despesa: discos (compres_material) o serveis generals (llum, gestor...)."""

    __tablename__ = "despeses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    num_factura: Mapped[str | None] = mapped_column(String(200), index=True)
    data_factura: Mapped[date] = mapped_column(Date, index=True)
    data_venciment: Mapped[date | None] = mapped_column(Date, index=True)

    proveidor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), index=True
    )
    proveidor_nom: Mapped[str] = mapped_column(String(300))  # sempre informat (copiat o manual)

    categoria: Mapped[CategoriaDespesa] = mapped_column(
        Enum(CategoriaDespesa, name="categoria_despesa"), index=True
    )
    concepte: Mapped[str] = mapped_column(String(500))

    base_imposable: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    tipus_iva_id: Mapped[int | None] = mapped_column(
        ForeignKey("tipus_iva.id", ondelete="SET NULL"), index=True
    )
    iva_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))    # snapshot del percentatge triat
    iva_import: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    estat_pagament: Mapped[EstatPagamentDespesa] = mapped_column(
        Enum(EstatPagamentDespesa, name="estat_pagament_despesa"),
        default=EstatPagamentDespesa.pendent, index=True
    )
    data_pagament: Mapped[date | None] = mapped_column(Date)
    # transferencia | rebut_domiciliat | targeta | efectiu | paypal_altres
    metode_pagament: Mapped[str | None] = mapped_column(String(30))

    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    proveidor: Mapped["Proveedor | None"] = relationship(back_populates="despeses", foreign_keys=[proveidor_id])
    # Una factura de proveïdor pot cobrir diverses recepcions (Compra); cadascuna
    # només pot pertànyer a una factura (vegeu Compra.despesa_id).
    compras: Mapped[list["Compra"]] = relationship(back_populates="despesa")
    moviments: Mapped[list["MovimentBancari"]] = relationship(back_populates="despesa")
    tipus_iva: Mapped["TipusIva | None"] = relationship()


class CompteBancari(Base):
    """Compte bancari de l'empresa."""

    __tablename__ = "comptes_bancaris"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nom: Mapped[str] = mapped_column(String(200))
    iban: Mapped[str | None] = mapped_column(String(34))
    entitat: Mapped[str | None] = mapped_column(String(100))   # "CaixaBank", "BBVA"...
    actiu: Mapped[bool] = mapped_column(Boolean, default=True)
    saldo_inicial: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    data_saldo_inicial: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    moviments: Mapped[list["MovimentBancari"]] = relationship(
        back_populates="compte", order_by="MovimentBancari.data_operacio"
    )


class MovimentBancari(Base):
    """Línia d'extracte bancari. Concilia amb despeses, vendes web o vendes externes."""

    __tablename__ = "moviments_bancaris"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    compte_id: Mapped[int] = mapped_column(
        ForeignKey("comptes_bancaris.id", ondelete="RESTRICT"), index=True
    )
    data_operacio: Mapped[date] = mapped_column(Date, index=True)
    data_valor: Mapped[date | None] = mapped_column(Date)
    concepte: Mapped[str] = mapped_column(String(500))
    import_moviment: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # + ingrés / - despesa
    saldo: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    estat: Mapped[EstatConciliacio] = mapped_column(
        Enum(EstatConciliacio, name="estat_conciliacio"),
        default=EstatConciliacio.pendent, index=True
    )
    # Un sol d'aquests quan conciliat
    despesa_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("despeses.id", ondelete="SET NULL"), index=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), index=True
    )
    venta_externa_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ventas_externas.id", ondelete="SET NULL"), index=True
    )
    notes_conciliacio: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    compte: Mapped["CompteBancari"] = relationship(back_populates="moviments")
    despesa: Mapped["Despesa | None"] = relationship(back_populates="moviments", foreign_keys=[despesa_id])
    order: Mapped["Order | None"] = relationship(foreign_keys=[order_id])
    venta_externa: Mapped["VentaExterna | None"] = relationship(foreign_keys=[venta_externa_id])


class PeriodeComptable(Base):
    """Mes comptable. Quan 'tancat=True' el mes es considera revisat i aprovat."""

    __tablename__ = "periodes_comptables"
    __table_args__ = (UniqueConstraint("year", "mes"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    mes: Mapped[int] = mapped_column(Integer, index=True)    # 1-12
    tancat: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    data_tancament: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaixaDiaria(Base):
    """Full de caixa diària: cobraments manuals per mètode de pagament i tipus
    d'IVA, un registre per dia. És l'equivalent digital de l'Excel que portava
    la botiga per quadrar caixa cada dia — no es deriva de `VentaExterna`/`Order`
    (aquestes no distingeixen Bizum/Paypal/Bono cultural ni el desglossament per
    IVA per mètode), s'omple a mà des de `/admin/resultat`."""

    __tablename__ = "caixa_diaria"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    data: Mapped[date] = mapped_column(Date, unique=True, index=True)

    targeta_21: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    targeta_4: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    efectiu_21: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    efectiu_4: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    bizum_21: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    bizum_4: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    paypal_21: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    paypal_4: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    transfer_21: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    bono_cultural: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Translation(Base):
    """Traducciones de la UI. key = 'nav.purchases', lang = 'ca'|'es'|'en'."""

    __tablename__ = "translations"
    __table_args__ = (UniqueConstraint("key", "lang"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    key: Mapped[str] = mapped_column(String(200), index=True)
    lang: Mapped[str] = mapped_column(String(5), index=True)
    value: Mapped[str] = mapped_column(Text)


class Pagina(Base):
    """Secció/pàgina del lloc: apareix al nav i té la seva pròpia ruta (/blog, /podcast, ...)."""

    __tablename__ = "pagines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    nom: Mapped[str] = mapped_column(String(200))
    tipus: Mapped[str] = mapped_column(String(40), default="llista-posts")
    # 'llista-posts' → mostra posts assignats, amb sidebar d'arxiu
    # 'estatica'     → mostra `contingut` (HTML lliure)
    # 'agenda'       → mostra events
    posicio: Mapped[int] = mapped_column(Integer, default=0)
    visible_menu: Mapped[bool] = mapped_column(Boolean, default=True)
    contingut: Mapped[str | None] = mapped_column(Text)  # per a pàgines estàtiques
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    posts: Mapped[list["Post"]] = relationship(
        secondary="posts_pagines", back_populates="pagines"
    )


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    titulo: Mapped[str] = mapped_column(String(400))
    contenido: Mapped[str] = mapped_column(Text)  # HTML (los posts de Blogger vienen en HTML)
    idioma: Mapped[str] = mapped_column(String(5), default="ca")
    publicado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    legacy_blogger_url: Mapped[str | None] = mapped_column(String(800))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    pagines: Mapped[list["Pagina"]] = relationship(
        secondary="posts_pagines", back_populates="posts"
    )


class PostPagina(Base):
    """M2M: un post pot aparèixer a múltiples pàgines."""

    __tablename__ = "posts_pagines"

    post_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True
    )
    pagina_id: Mapped[int] = mapped_column(
        ForeignKey("pagines.id", ondelete="CASCADE"), primary_key=True
    )


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    titulo: Mapped[str] = mapped_column(String(400))
    descripcion: Mapped[str | None] = mapped_column(Text)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    lugar: Mapped[str] = mapped_column(String(300), default="Ultra-Local Records, Pujades 113, Barcelona")
    link: Mapped[str | None] = mapped_column(String(800))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SpotifyConnection(Base):
    """Connexió Spotify d'un usuari per a recomanacions de catàleg."""

    __tablename__ = "spotify_connections"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    spotify_user_id: Mapped[str] = mapped_column(String(100), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(200))
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str] = mapped_column(Text)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship()


# ---------------------------------------------------------------------------
# Newsletter
# ---------------------------------------------------------------------------

class NewsletterCampaignStatus(str, enum.Enum):
    esborrany = "esborrany"
    enviant = "enviant"
    enviada = "enviada"


class NewsletterSendStatus(str, enum.Enum):
    pendent = "pendent"
    enviat = "enviat"
    error = "error"


class NewsletterCampaign(Base):
    __tablename__ = "newsletter_campaigns"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    assumpte: Mapped[str] = mapped_column(String(200))
    contingut_html: Mapped[str] = mapped_column(Text)
    idioma: Mapped[str] = mapped_column(String(5), default="ca")
    estat: Mapped[NewsletterCampaignStatus] = mapped_column(
        Enum(NewsletterCampaignStatus, name="newsletter_campaign_status"),
        default=NewsletterCampaignStatus.esborrany,
        index=True,
    )
    creat_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    enviament_iniciat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enviament_acabat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sends: Mapped[list["NewsletterSend"]] = relationship(back_populates="campaign")


class NewsletterSend(Base):
    """Traça d'enviament per destinatari (permet reprendre i portar el compte de baixes)."""

    __tablename__ = "newsletter_sends"
    __table_args__ = (UniqueConstraint("campaign_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("newsletter_campaigns.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    email: Mapped[str] = mapped_column(String(320))  # snapshot: sobreviu a anonimització/baixes
    estat: Mapped[NewsletterSendStatus] = mapped_column(
        Enum(NewsletterSendStatus, name="newsletter_send_status"),
        default=NewsletterSendStatus.pendent,
        index=True,
    )
    error_msg: Mapped[str | None] = mapped_column(Text)
    unsubscribe_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    enviat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    campaign: Mapped["NewsletterCampaign"] = relationship(back_populates="sends")


# ---------------------------------------------------------------------------
# Subscripcions ("club del disc")
# ---------------------------------------------------------------------------
#
# Decisions de disseny (veure discussió d'arquitectura):
# - El cobrament periòdic (`CobramentSubscripcio`) i l'enviament d'un disc
#   concret (`Assignacio` -> `Order`) són coses separades: es cobra sempre
#   per data (Redsys amb credencial guardada, sense intervenció de l'admin),
#   i l'admin decideix DESPRÉS quin exemplar físic correspon a cada cobrament
#   ja fet. Això evita cobrar dues vegades i permet que la validació manual
#   vagi per darrere del cobrament sense bloquejar-lo.
# - L'exclusió d'historial (no repetir mai un disc a un client) es fa per
#   `Release`, no per `Item`: al client li importa l'àlbum, no quin exemplar
#   físic concret rep.

class EstatSubscripcio(str, enum.Enum):
    # A l'espera de la notificació de Redsys de l'alta (captura del token
    # COF); si es denega, l'alta es descarta (veure routers/subscripcions_public.py).
    pendent_pagament = "pendent_pagament"
    activa = "activa"
    pausada = "pausada"
    cancel_lada = "cancel_lada"


class ConfiguracioSubscripcio(Base):
    """Configuració general del club del disc: fila singleton (sempre id=1),
    mateix patró que `ConfiguracioBotiga`. No hi ha "plans": el client
    configura la seva pròpia subscripció (periodicitat, quantitat) dins dels
    valors que aquí s'ofereixen; el preu resulta de `preu_per_disc *
    quantitat`. `marge_min_pct`/`marge_max_pct` són només els valors per
    defecte del filtre a la pantalla de tria de catàleg de l'admin (veure
    routers/admin_subscripcions.py) — no filtren res automàticament."""

    __tablename__ = "configuracio_subscripcio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    preu_per_disc: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    marge_min_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("70"))
    marge_max_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("120"))
    periodicitats_mesos_disponibles: Mapped[list] = mapped_column(JSON, default=list)
    quantitats_disponibles: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Subscripcio(Base):
    """Alta d'un client: estat, configuració pròpia (periodicitat, quantitat,
    seccions preferides) i credencial de cobrament recurrent."""

    __tablename__ = "subscripcions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    estat: Mapped[EstatSubscripcio] = mapped_column(
        Enum(EstatSubscripcio, name="estat_subscripcio"), default=EstatSubscripcio.pendent_pagament, index=True
    )
    address_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("addresses.id", ondelete="RESTRICT"))
    # Gèneres musicals (Discogs) que el client ha triat com a preferits —
    # veure `services.subscripcions.GENERES_DISCOGS` per a la llista tancada
    # d'opcions i el matching (substring sobre `Release.genero`, mateix
    # patró que el filtre del catàleg públic). Llista buida = sense
    # preferència, qualsevol gènere val. NO són `Seccio` (cubetes físiques
    # de la botiga): és un concepte diferent, tot i que abans s'hi va confondre.
    generes_preferits: Mapped[list | None] = mapped_column(JSON)
    # Cada quants mesos es factura/envia, i quants discs per enviament: triats
    # pel client a l'alta entre els valors que oferia `ConfiguracioSubscripcio`
    # en aquell moment. Fixos un cop donat d'alta (per canviar-los cal
    # cancel·lar i tornar a apuntar-se, veure routers/me.py).
    periodicitat_mesos: Mapped[int] = mapped_column(Integer)
    quantitat: Mapped[int] = mapped_column(Integer)
    # Snapshot de preu_per_disc * quantitat en el moment de l'alta (mateix
    # esperit que OrderItem.precio): un canvi futur del preu no afecta
    # subscriptors ja donats d'alta.
    preu_periode: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    # Identificador reutilitzable que retorna Redsys (Ds_Merchant_Identifier)
    # en captar-lo amb DS_MERCHANT_IDENTIFIER=REQUIRED a l'alta; permet cobrar
    # els períodes següents servidor-a-servidor, sense redirigir el client
    # (veure services/redsys.py::charge_recurring).
    redsys_identifier: Mapped[str | None] = mapped_column(String(40))
    # Ds_Merchant_Cof_Txnid de la transacció CIT original (l'alta): identifica
    # la sèrie de cobraments recurrents davant Visa/Mastercard. S'envia a cada
    # cobrament MIT posterior (opcional per Redsys, molt recomanat).
    redsys_cof_txnid: Mapped[str | None] = mapped_column(String(40))
    proxima_facturacio: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    cancel_lada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship()
    address: Mapped["Address"] = relationship()
    cobraments: Mapped[list["CobramentSubscripcio"]] = relationship(
        back_populates="subscripcio", order_by="CobramentSubscripcio.periode"
    )


class EstatCobrament(str, enum.Enum):
    # Redirecció a Redsys enviada, a l'espera de la notificació servidor-a-
    # servidor (només l'alta passa per aquí; les renovacions per COF són
    # síncrones i mai queden en aquest estat, veure services/subscripcions.py).
    pendent = "pendent"
    cobrat = "cobrat"
    fallit = "fallit"


class CobramentSubscripcio(Base):
    """Un càrrec periòdic (alta o renovació): un enviament. No implica encara
    cap disc assignat: això és feina de les `Assignacio` (una per disc, tantes
    com `subscripcio.quantitat`) que pengen d'aquí un cop l'admin les ha
    revisat (veure services/subscripcions.py::facturar_subscripcio)."""

    __tablename__ = "cobraments_subscripcio"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    subscripcio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subscripcions.id", ondelete="CASCADE"), index=True
    )
    periode: Mapped[date] = mapped_column(Date)
    import_: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    estat: Mapped[EstatCobrament] = mapped_column(
        Enum(EstatCobrament, name="estat_cobrament_subscripcio"), index=True
    )
    ds_order: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    raw_notification: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    subscripcio: Mapped["Subscripcio"] = relationship(back_populates="cobraments")
    assignacions: Mapped[list["Assignacio"]] = relationship(back_populates="cobrament")


class EstatAssignacio(str, enum.Enum):
    proposada = "proposada"
    confirmada = "confirmada"
    omesa = "omesa"
    sense_match = "sense_match"


class Assignacio(Base):
    """Quin disc concret correspon a un dels N discs d'un cobrament (enviament)
    ja fet: `cobrament_id` ja NO és únic, un cobrament té tantes `Assignacio`
    com `subscripcio.quantitat`. `proposada` la crea l'algorisme automàtic
    (veure services/subscripcions.py), triant només entre els exemplars que
    l'admin ha marcat com a elegibles (`Item.subscripcio_pool`); l'admin la
    revisa, la reassigna o confirma tot el cobrament d'un cop (moment en què
    es genera un únic `Order` amb totes les línies, mateix circuit que
    qualsevol altra venda web)."""

    __tablename__ = "subscripcio_assignacions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    cobrament_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cobraments_subscripcio.id", ondelete="CASCADE"), index=True
    )
    subscripcio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscripcions.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("items.id", ondelete="SET NULL"))
    # Denormalitzat perquè l'exclusió d'historial ("no repetir aquest àlbum")
    # sobrevisqui encara que l'item s'esborri o es retiri del catàleg.
    release_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("releases.id", ondelete="SET NULL"), index=True)
    estat: Mapped[EstatAssignacio] = mapped_column(
        Enum(EstatAssignacio, name="estat_assignacio"), default=EstatAssignacio.proposada, index=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    cobrament: Mapped["CobramentSubscripcio"] = relationship(back_populates="assignacions")
    subscripcio: Mapped["Subscripcio"] = relationship()
    item: Mapped["Item | None"] = relationship(foreign_keys=[item_id])
    release: Mapped["Release | None"] = relationship()
    order: Mapped["Order | None"] = relationship()


# ---------------------------------------------------------------------------
# Reservas de stock agregado (solo condicion='nou')
# ---------------------------------------------------------------------------

class StockHold(Base):
    """Retención de N unidades de una línea `Item` con stock agregado (nou).

    Para segona_ma, cada copia es su propia fila y la reserva vive en la
    propia fila (`Item.status`/`reserved_by_cart_id`/`reserved_for_peticion_id`/
    `reserved_for_assignacio_id`/`reserved_until`) porque solo puede haber un
    titular a la vez. Una línea `nou` puede tener varias retenciones
    simultáneas de orígenes distintos (dos carritos pujando por las últimas
    unidades, una petición de cliente, una asignación de club...), así que
    hace falta una tabla en vez de columnas únicas en `Item`.

    Exactamente uno de `cart_id` / `peticion_id` / `assignacio_id` / `order_id`
    debe estar relleno (se valida a nivel de aplicación, no de esquema):
    - `cart_id`: reserva normal de carrito (caduca a los ~20 min, igual que
      las reservas de segona_ma, ver services/reservations.py).
    - `peticion_id`: reserva larga (72h) de una PeticionCliente que recoge y
      paga en tienda, equivalente a `Item.reserved_for_peticion_id`.
    - `assignacio_id`: retención mientras el admin revisa una propuesta de
      asignación del club del disco, equivalente a
      `Item.reserved_for_assignacio_id` (sin caducidad, `reserved_until=None`).
    - `order_id`: pedido con `metodo_pago='tienda'` ya confirmado pero
      pendiente de recoger y pagar (72h), equivalente a la extensión de
      `reserved_until` que hoy se hace sobre el Item en checkout.py.
    """

    __tablename__ = "stock_holds"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    cantidad: Mapped[int] = mapped_column(Integer)

    cart_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"), index=True)
    peticion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("peticiones_cliente.id", ondelete="CASCADE"), index=True
    )
    assignacio_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("subscripcio_assignacions.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)

    # None = sin caducidad automática (p.ej. retención de club hasta que el
    # admin decide). Con caducidad, se libera de forma perezosa igual que las
    # reservas de segona_ma (ver services/reservations.py::release_expired).
    reserved_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    item: Mapped["Item"] = relationship()
