import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from ._base import TenantScoped, _uuid


class NewsletterCampaignStatus(str, enum.Enum):
    esborrany = "esborrany"
    enviant = "enviant"
    enviada = "enviada"


class NewsletterSendStatus(str, enum.Enum):
    pendent = "pendent"
    enviat = "enviat"
    error = "error"


class NewsletterCampaign(TenantScoped, Base):
    __tablename__ = "newsletter_campaigns"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    # Fase 4 Etapa B: atributo Python en inglés, ya alineado con el nombre
    # de columna que fijó la Etapa A.
    subject: Mapped[str] = mapped_column(String(200))
    content_html: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(5), default="ca")
    status: Mapped[NewsletterCampaignStatus] = mapped_column(
        Enum(NewsletterCampaignStatus, name="newsletter_campaign_status"),
        default=NewsletterCampaignStatus.esborrany,
        index=True,
    )
    creat_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sending_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sending_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sends: Mapped[list["NewsletterSend"]] = relationship(back_populates="campaign")


class NewsletterSend(TenantScoped, Base):
    """Traça d'enviament per destinatari (permet reprendre i portar el compte de baixes)."""

    __tablename__ = "newsletter_sends"
    __table_args__ = (UniqueConstraint("campaign_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("newsletter_campaigns.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    email: Mapped[str] = mapped_column(String(320))  # snapshot: sobreviu a anonimització/baixes
    # Fase 4 Etapa B: atributo Python en inglés, ya alineado con el nombre
    # de columna que fijó la Etapa A.
    status: Mapped[NewsletterSendStatus] = mapped_column(
        Enum(NewsletterSendStatus, name="newsletter_send_status"),
        default=NewsletterSendStatus.pendent,
        index=True,
    )
    error_msg: Mapped[str | None] = mapped_column(Text)
    unsubscribe_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

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
