"""Tests del mòdul de newsletter: CRUD de campanyes, enviament i baixa."""

import contextlib
import io
import re
import uuid

from sqlalchemy import select

from app.models import NewsletterCampaign, NewsletterCampaignStatus, NewsletterSend, NewsletterSendStatus, User
from app.services.metrics import newsletter_send_result_total
from app.services.security import _hash
from app.tasks.newsletter import send_campaign


def _login(client, email: str) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": email}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    resp = client.post(f"/auth/magic-link/verify?token={token}")
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _admin_token(client, db) -> str:
    access = _login(client, "admin@example.com")
    user = db.scalar(select(User).where(User.email == "admin@example.com"))
    user.rol = "admin"
    db.commit()
    return access


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_crear_i_editar_esborrany(client, db):
    token = _admin_token(client, db)
    resp = client.post(
        "/admin/newsletter",
        json={"assumpte": "Novetats de la setmana", "contingut_html": "<p>Hola</p>"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    campaign_id = resp.json()["id"]
    assert resp.json()["estat"] == "esborrany"

    resp = client.patch(
        f"/admin/newsletter/{campaign_id}",
        json={"assumpte": "Novetats actualitzades"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["assumpte"] == "Novetats actualitzades"


def test_no_es_pot_editar_ni_esborrar_un_cop_enviada(client, db, monkeypatch):
    token = _admin_token(client, db)
    monkeypatch.setattr("app.routers.admin_newsletter.send_campaign.delay", lambda *a, **k: None)

    resp = client.post(
        "/admin/newsletter",
        json={"assumpte": "Assumpte", "contingut_html": "<p>Contingut</p>"},
        headers=_auth(token),
    )
    campaign_id = resp.json()["id"]

    resp = client.post(f"/admin/newsletter/{campaign_id}/send", headers=_auth(token))
    assert resp.status_code == 202

    campaign = db.get(NewsletterCampaign, uuid.UUID(campaign_id))
    assert campaign.estat == NewsletterCampaignStatus.enviant

    resp = client.patch(f"/admin/newsletter/{campaign_id}", json={"assumpte": "x"}, headers=_auth(token))
    assert resp.status_code == 409

    resp = client.delete(f"/admin/newsletter/{campaign_id}", headers=_auth(token))
    assert resp.status_code == 409

    resp = client.post(f"/admin/newsletter/{campaign_id}/send", headers=_auth(token))
    assert resp.status_code == 409


def test_send_test_no_crea_files_de_seguiment(client, db, monkeypatch):
    token = _admin_token(client, db)
    resp = client.post(
        "/admin/newsletter",
        json={"assumpte": "Assumpte", "contingut_html": "<p>Contingut</p>"},
        headers=_auth(token),
    )
    campaign_id = resp.json()["id"]

    resp = client.post(
        f"/admin/newsletter/{campaign_id}/send-test",
        json={"email": "proves@example.com"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert db.scalar(select(NewsletterSend).where(NewsletterSend.campaign_id == uuid.UUID(campaign_id))) is None


def test_recipients_count_nomes_compta_actius_amb_consentiment(client, db):
    token = _admin_token(client, db)
    db.add(User(email="subscriu1@example.com", activo=True, consent_newsletter=True))
    db.add(User(email="subscriu2@example.com", activo=True, consent_newsletter=True))
    db.add(User(email="sense-consentiment@example.com", activo=True, consent_newsletter=False))
    db.add(User(email="inactiu@example.com", activo=False, consent_newsletter=True))
    db.commit()

    resp = client.get("/admin/newsletter/recipients/count", headers=_auth(token))
    assert resp.status_code == 200
    # +1 perquè l'admin de test també té consent_newsletter=False per defecte, no compta
    assert resp.json()["total"] == 2


def test_baixa_desactiva_consent_newsletter(client, db):
    user = User(email="subscriptor@example.com", activo=True, consent_newsletter=True)
    db.add(user)
    db.commit()
    db.refresh(user)

    campaign = NewsletterCampaign(assumpte="x", contingut_html="<p>x</p>")
    db.add(campaign)
    db.commit()

    raw_token = "token-de-prova-123"
    send = NewsletterSend(
        campaign_id=campaign.id,
        user_id=user.id,
        email=user.email,
        unsubscribe_token_hash=_hash(raw_token),
    )
    db.add(send)
    db.commit()

    resp = client.get(f"/newsletter/baixa?token={raw_token}")
    assert resp.status_code == 200
    db.refresh(user)
    assert user.consent_newsletter is False


def test_baixa_amb_token_invalid_dona_404(client, db):
    resp = client.get("/newsletter/baixa?token=token-inexistent")
    assert resp.status_code == 404


def test_send_campaign_compta_metrica_per_exit_i_error(client, db, monkeypatch):
    monkeypatch.setattr("app.tasks.newsletter.time.sleep", lambda *a, **k: None)
    ok_user = User(email="ok@example.com", activo=True, consent_newsletter=True)
    fail_user = User(email="fail@example.com", activo=True, consent_newsletter=True)
    db.add_all([ok_user, fail_user])
    campaign = NewsletterCampaign(
        assumpte="x", contingut_html="<p>x</p>", estat=NewsletterCampaignStatus.enviant
    )
    db.add(campaign)
    db.commit()

    def _send_email(to, **kwargs):
        if to == "fail@example.com":
            raise RuntimeError("SMTP caigut")

    monkeypatch.setattr("app.tasks.newsletter.send_email", _send_email)

    abans_ok = newsletter_send_result_total.labels(result="enviat")._value.get()
    abans_error = newsletter_send_result_total.labels(result="error")._value.get()

    send_campaign(campaign.id)

    assert newsletter_send_result_total.labels(result="enviat")._value.get() == abans_ok + 1
    assert newsletter_send_result_total.labels(result="error")._value.get() == abans_error + 1

    sends = {s.email: s.estat for s in db.scalars(select(NewsletterSend)).all()}
    assert sends["ok@example.com"] == NewsletterSendStatus.enviat
    assert sends["fail@example.com"] == NewsletterSendStatus.error
