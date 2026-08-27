"""Aislamiento multi-tenant: resolución del tenant de cada request y los
listeners de SQLAlchemy que hacen el filtrado automático.

Mecanismo (ver plan en /Users/paumartinez/.claude/plans/swift-gathering-bengio.md):

- El tenant activo se guarda en `Session.info["tenant_id"]` — un dict propio
  de cada instancia de `Session`, NO en un `contextvars.ContextVar` a nivel
  de módulo. Esto no es una elección arbitraria: FastAPI ejecuta cada mitad
  de una dependencia generadora síncrona (`get_db`, antes y después del
  `yield`) en llamadas de threadpool SEPARADAS (`anyio.to_thread.run_sync`),
  cada una con su propia copia del contexto — un valor fijado con
  `ContextVar.set()` antes del `yield` no es visible ni siquiera dentro del
  propio handler de la ruta, y `Token.reset()` revienta con
  "was created in a different Context" al llegar al `finally`. `Session.info`
  no tiene ese problema: es un atributo normal del objeto sesión, viaja con
  él lo use quien lo use, sin depender de en qué hilo/contexto se ejecute.
- `_filter_by_tenant` (do_orm_execute) es la capa PRINCIPAL de aislamiento:
  añade un WHERE tenant_id=... a cualquier SELECT/UPDATE/DELETE ORM contra una
  clase que herede de `TenantScoped`. Funciona igual en SQLite (tests) que en
  Postgres (producción) — es la única capa que los tests pueden verificar de
  verdad.
- `_autofill_tenant_id` (before_flush) rellena `tenant_id` en objetos nuevos
  que aún no lo tengan puesto, para que un INSERT sin acordarse de fijarlo a
  mano no sea una vía de fuga.
- `_set_local_tenant` (after_begin) es el cinturón de seguridad extra en
  Postgres (RLS): reemite `SET LOCAL app.tenant_id` en cada transacción nueva
  de la sesión, no solo una vez al abrir la conexión — el checkout hace varios
  `commit()` dentro de la misma request, y `SET LOCAL` no sobrevive a un
  commit.
"""

import contextlib
import uuid
from typing import Iterator

from sqlalchemy import event, select, text
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from .models import Tenant, TenantScoped


def resolve_tenant_by_domain(db: Session, host: str) -> Tenant | None:
    """Busca el Tenant por dominio. `Tenant` no hereda de `TenantScoped`, así
    que esta consulta nunca se ve afectada por el filtro — se puede llamar
    aunque `db.info` todavía no tenga tenant fijado (es precisamente su
    trabajo: resolverlo)."""
    domain = host.split(":")[0]  # el Host header puede traer puerto, p.ej. "localhost:8000"
    return db.scalar(select(Tenant).where(Tenant.domain == domain, Tenant.activo.is_(True)))


def tenant_frontend_url(tenant: Tenant) -> str:
    """URL base del front de este tenant, derivada de `Tenant.domain` — ya
    no es un campo de `Settings` (Fase 2): era global y estaba roto de
    facto con más de un tenant (los magic links de un segundo tenant
    apuntaban al dominio del primero). `http://` solo para dominios locales
    de desarrollo/test conocidos; cualquier otro dominio es `https://`."""
    domain = tenant.domain
    if domain in ("localhost", "testserver") or domain.endswith(".local"):
        return f"http://{domain}"
    return f"https://{domain}"


def _sql_uuid_literal(value: uuid.UUID) -> str:
    """`SET LOCAL` no admite parámetros ligados en Postgres, hay que
    interpolar el valor en el SQL — este cast obliga a que sea de verdad un
    uuid.UUID antes de interpolarlo (su str() solo contiene hex y guiones),
    para no abrir la puerta a que un valor inesperado en `db.info`/`session.info`
    se cuele como SQL."""
    if not isinstance(value, uuid.UUID):
        raise TypeError(f"tenant_id debe ser uuid.UUID, no {type(value)!r}")
    return str(value)


def apply_local_tenant(db: Session) -> None:
    """Emite `SET LOCAL app.tenant_id` para la transacción EN CURSO de esta
    sesión (Postgres solamente). Hace falta llamarlo a mano justo después de
    fijar `db.info["tenant_id"]`, no basta con el listener `after_begin` de
    más abajo: la primera consulta de cada request (la propia resolución del
    tenant, antes de saber quién es) ya abre una transacción con
    `db.info["tenant_id"]` todavía vacío, así que `after_begin` la deja sin
    `SET LOCAL` — sin esta llamada explícita, RLS no se aplicaría hasta el
    primer `commit()` de la request."""
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return
    tenant_id = db.info.get("tenant_id")
    if tenant_id is None:
        return
    db.execute(text(f"SET LOCAL app.tenant_id = '{_sql_uuid_literal(tenant_id)}'"))


@contextlib.contextmanager
def scoped_to(db: Session, tenant_id: uuid.UUID) -> Iterator[None]:
    """Fija el tenant actual (en `db.info`, ver arriba) para el bloque
    `with`. Uso normal: tareas de Celery que iteran todos los tenants sobre
    la MISMA sesión (ver app/tasks/peticiones.py), o el webhook de Redsys una
    vez ha identificado a qué tenant pertenece el pago (ver
    routers/checkout.py). `get_db` no necesita esto: al ser una sesión nueva
    por request, basta con fijar `db.info["tenant_id"]` directamente."""
    previous = db.info.get("tenant_id")
    db.info["tenant_id"] = tenant_id
    apply_local_tenant(db)
    try:
        yield
    finally:
        db.info["tenant_id"] = previous


@event.listens_for(Session, "do_orm_execute")
def _filter_by_tenant(orm_execute_state: ORMExecuteState) -> None:
    if not orm_execute_state.is_orm_statement or orm_execute_state.is_column_load:
        return
    tenant_id = orm_execute_state.session.info.get("tenant_id")
    if tenant_id is None:
        return
    orm_execute_state.statement = orm_execute_state.statement.options(
        with_loader_criteria(
            TenantScoped, lambda cls: cls.tenant_id == tenant_id, include_aliases=True
        )
    )


@event.listens_for(Session, "before_flush")
def _autofill_tenant_id(session: Session, flush_context, instances) -> None:
    tenant_id = session.info.get("tenant_id")
    if tenant_id is None:
        return
    for obj in session.new:
        if isinstance(obj, TenantScoped) and obj.tenant_id is None:
            obj.tenant_id = tenant_id


@event.listens_for(Session, "after_begin")
def _set_local_tenant(session: Session, transaction, connection) -> None:
    """Reemite SET LOCAL cada vez que la sesión abre una transacción NUEVA
    (p.ej. tras un commit() a media request/tarea) — complementa, no
    sustituye, la llamada explícita de `apply_local_tenant` (ver arriba),
    que cubre la primera transacción de cada request."""
    if connection.dialect.name != "postgresql":
        return  # SQLite (tests/dev) no tiene RLS; el filtro de arriba ya aplica igual
    tenant_id = session.info.get("tenant_id")
    if tenant_id is None:
        return
    connection.execute(text(f"SET LOCAL app.tenant_id = '{_sql_uuid_literal(tenant_id)}'"))
