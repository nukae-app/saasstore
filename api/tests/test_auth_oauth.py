"""Cobreix el flux d'OAuth amb Google (authlib), sense sortir a la xarxa real.

authlib valida el paràmetre `state` contra el que ha desat a la sessió abans
de canviar el `code` per un token (veure `StarletteOAuth2App.authorize_access_token`).
Aquest test verifica que aquest lligam es manté després de pujar authlib de
1.4 a 1.7 (CVE-2025-68158 / CVE-2026-27962 eren sobre precisament aquesta
comprovació de `state`).
"""

from fastapi.testclient import TestClient

from app.main import app
from app.routers.auth import oauth


def test_google_login_redirects_and_binds_state_to_session(client, monkeypatch):
    async def fake_create_authorization_url(redirect_uri, **kwargs):
        return {"url": "https://accounts.google.com/o/oauth2/auth?state=abc123", "state": "abc123"}

    monkeypatch.setattr(oauth.google, "create_authorization_url", fake_create_authorization_url)

    resp = client.get("/auth/google/login", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers["location"].startswith("https://accounts.google.com/")
    # SessionMiddleware guarda el `state` en una cookie de sessió signada
    assert "session" in resp.cookies


def test_google_callback_rejects_forged_state(monkeypatch):
    # Client sense passar abans per /auth/google/login: no hi ha `state` a la sessió.
    no_raise_client = TestClient(app, base_url="https://testserver", raise_server_exceptions=False)

    resp = no_raise_client.get(
        "/auth/google/callback?state=forged-state&code=whatever-code",
        follow_redirects=False,
    )

    # authlib ha de rebutjar-ho (OAuthError) abans d'arribar a bescanviar el `code`;
    # en cap cas ha de crear una sessió vàlida (no hi pot haver cookie de refresh).
    assert resp.status_code >= 400
    assert "refresh_token" not in resp.cookies
