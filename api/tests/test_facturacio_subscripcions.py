"""Tests del cicle mensual únic (data de tall + facturació global) i del
cobrament recurrent automàtic (services/subscripcions.py i el job de Celery
que l'orquestra): només es cobren les subscripcions actives vençudes, un
cobrament autoritzat avança `proxima_facturacio` al cicle següent, un de
denegat no l'avança (es reintentarà l'endemà) i no toca res
d'`Assignacio`/`Order`."""

from datetime import date, timedelta
from decimal import Decimal

from app.models import Address, EstatCobrament, EstatSubscripcio, Subscripcio, Tenant, User
from app.services import subscripcions as subscripcions_service
from app.tenancy import scoped_to


def _user_amb_subscripcio(
    db, *, proxima_facturacio, estat=EstatSubscripcio.activa, periodicitat_mesos=1, quantitat=1,
) -> Subscripcio:
    user = User(email=f"{proxima_facturacio}-{estat}-{periodicitat_mesos}@example.com", name="Fan")
    db.add(user)
    db.flush()
    address = Address(user_id=user.id, recipient_name="Fan", address_line1="C", city="BCN", postal_code="08001")
    db.add(address)
    db.flush()
    sub = Subscripcio(
        user_id=user.id, address_id=address.id, estat=estat,
        periodicitat_mesos=periodicitat_mesos, quantitat=quantitat, preu_periode=Decimal("25.00") * quantitat,
        redsys_identifier="TOKEN-1", proxima_facturacio=proxima_facturacio,
    )
    db.add(sub)
    db.commit()
    return sub


def test_penultim_divendres():
    # gener 2026: divendres 2, 9, 16, 23, 30 -> penúltim = 23
    assert subscripcions_service.penultim_divendres(2026, 1) == date(2026, 1, 23)
    # febrer 2026 (28 dies): divendres 6, 13, 20, 27 -> penúltim = 20
    assert subscripcions_service.penultim_divendres(2026, 2) == date(2026, 2, 20)


def test_primer_dia_habil_salta_cap_de_setmana():
    # agost 2026 comença en dissabte -> primer hàbil és dilluns 3
    assert subscripcions_service.primer_dia_habil(2026, 8) == date(2026, 8, 3)
    # juny 2026 comença en dilluns -> primer hàbil és el mateix dia 1
    assert subscripcions_service.primer_dia_habil(2026, 6) == date(2026, 6, 1)


def test_proxima_facturacio_alta_abans_i_despres_del_tall():
    tall = subscripcions_service.penultim_divendres(2026, 3)  # divendres 20 de març del 2026
    abans_del_tall = tall
    despres_del_tall = tall + timedelta(days=1)

    # apuntar-se el mateix dia del tall (inclusiu) o abans -> factura's al cicle del mes vinent
    assert subscripcions_service.proxima_facturacio_alta(abans_del_tall) == subscripcions_service.primer_dia_habil(2026, 4)
    # apuntar-se just després del tall -> la finestra d'aquest mes ja ha tancat, espera un mes més
    assert subscripcions_service.proxima_facturacio_alta(despres_del_tall) == subscripcions_service.primer_dia_habil(2026, 5)


def test_proxima_facturacio_seguent_encadena_cicles_consecutius():
    cicle_1 = subscripcions_service.primer_dia_habil(2026, 1)
    cicle_2 = subscripcions_service.proxima_facturacio_seguent(cicle_1, 1)
    cicle_3 = subscripcions_service.proxima_facturacio_seguent(cicle_2, 1)

    assert cicle_2 == subscripcions_service.primer_dia_habil(2026, 2)
    assert cicle_3 == subscripcions_service.primer_dia_habil(2026, 3)

    # amb periodicitat_mesos=3, es salta directament 3 cicles
    assert subscripcions_service.proxima_facturacio_seguent(cicle_1, 3) == subscripcions_service.primer_dia_habil(2026, 4)


def test_facturar_subscripcio_autoritzada_avanca_al_cicle_seguent(db, monkeypatch):
    cicle_actual = subscripcions_service.primer_dia_habil(2026, 1)
    sub = _user_amb_subscripcio(db, proxima_facturacio=cicle_actual, periodicitat_mesos=2)

    monkeypatch.setattr(
        subscripcions_service.redsys, "charge_recurring",
        lambda **kw: {"Ds_Order": "x", "Ds_Response": "0000"},
    )

    cobrament = subscripcions_service.facturar_subscripcio(db, sub)

    assert cobrament.estat == EstatCobrament.cobrat
    assert cobrament.import_ == sub.preu_periode
    db.refresh(sub)
    assert sub.proxima_facturacio == subscripcions_service.primer_dia_habil(2026, 3)


def test_facturar_subscripcio_denegada_no_avanca_la_data(db, monkeypatch):
    venciment = date(2026, 1, 1)
    sub = _user_amb_subscripcio(db, proxima_facturacio=venciment)

    monkeypatch.setattr(
        subscripcions_service.redsys, "charge_recurring",
        lambda **kw: {"Ds_Order": "x", "Ds_Response": "0180"},
    )

    cobrament = subscripcions_service.facturar_subscripcio(db, sub)

    assert cobrament.estat == EstatCobrament.fallit
    db.refresh(sub)
    assert sub.proxima_facturacio == venciment  # es reintentarà l'endemà


def test_facturar_subscripcions_vencudes_nomes_cobra_actives_vençudes(db, monkeypatch):
    avui = date.today()
    vençuda = _user_amb_subscripcio(db, proxima_facturacio=date(2026, 1, 1))
    encara_no = _user_amb_subscripcio(db, proxima_facturacio=date(2099, 1, 1))
    pausada = _user_amb_subscripcio(db, proxima_facturacio=date(2026, 1, 1), estat=EstatSubscripcio.pausada)

    monkeypatch.setattr(
        subscripcions_service.redsys, "charge_recurring",
        lambda **kw: {"Ds_Order": "x", "Ds_Response": "0000"},
    )

    cobraments = subscripcions_service.facturar_subscripcions_vencudes(db)

    assert [c.subscripcio_id for c in cobraments] == [vençuda.id]
    db.refresh(encara_no)
    db.refresh(pausada)
    assert encara_no.proxima_facturacio == date(2099, 1, 1)
    assert pausada.proxima_facturacio == date(2026, 1, 1)


def test_job_de_celery_crida_la_facturacio(db, monkeypatch):
    from app.tasks.subscripcions import facturar_pendents

    _user_amb_subscripcio(db, proxima_facturacio=date(2026, 1, 1))

    monkeypatch.setattr(
        "app.services.subscripcions.redsys.charge_recurring",
        lambda **kw: {"Ds_Order": "x", "Ds_Response": "0000"},
    )

    resultat = facturar_pendents()
    assert resultat == {"cobraments": 1, "cobrats": 1, "fallits": 0}


def test_job_de_celery_factura_a_tots_els_tenants(db, monkeypatch):
    """Regresión de la Fase 4: `facturar_pendents` abre su propia sesión
    (no pasa por get_db, no hay request) e itera todos los tenants activos
    — sin ese bucle, con Subscripcio ya TenantScoped, la tarea dejaría de
    facturar a todo el mundo en silencio (RLS sin app.tenant_id puesto =
    0 filas). Dos tenants, uno vencido cada uno, confirma que se cobra a
    ambos, no solo al de la sesión de tests por defecto."""
    from app.tasks.subscripcions import facturar_pendents

    tenant_a_id = db.info["tenant_id"]
    _user_amb_subscripcio(db, proxima_facturacio=date(2026, 1, 1))

    tenant_b = Tenant(slug="tenant-b-facturacio", domain="b-facturacio.testserver", nombre="Tenant B", vertical_id="records")
    db.add(tenant_b)
    db.commit()
    with scoped_to(db, tenant_b.id):
        _user_amb_subscripcio(db, proxima_facturacio=date(2026, 1, 1))
    db.info["tenant_id"] = tenant_a_id

    monkeypatch.setattr(
        "app.services.subscripcions.redsys.charge_recurring",
        lambda **kw: {"Ds_Order": "x", "Ds_Response": "0000"},
    )

    resultat = facturar_pendents()
    assert resultat == {"cobraments": 2, "cobrats": 2, "fallits": 0}
