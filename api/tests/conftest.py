import os

# Debe fijarse ANTES de importar nada de app (get_settings está cacheado)
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["REFRESH_COOKIE_PATH"] = "/auth"  # sin Caddy delante no hay prefijo /api
# Clave pública de pruebas de Redsys (la misma que usa su documentación de
# integración/sandbox): sirve para firmar y verificar en los tests sin
# depender de credenciales reales del banco.
os.environ["REDSYS_MERCHANT_CODE"] = "999008881"
os.environ["REDSYS_SECRET_KEY"] = "sq7HjrUOBfKmC576ILgskD5srU870gJ7"
os.environ["REDSYS_NOTIFY_URL"] = "https://testserver/api/checkout/pay/redsys/notify"
# TestClient reutiliza la misma IP sintética en todas las peticiones: sin esto
# el rate limiting de /auth/* agotaría el límite entre tests distintos.
os.environ["RATE_LIMIT_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient

from app import models  # noqa: F401  registra las tablas
from app.database import Base, SessionLocal, engine
from app.main import app


@pytest.fixture()
def db():
    Base.metadata.create_all(engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client():
    # https: la cookie de refresh lleva Secure y no viajaría por http
    return TestClient(app, base_url="https://testserver")
