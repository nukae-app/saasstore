"""Servicio de almacenamiento de subidas (disco local / S3) y su uso en los endpoints."""

import contextlib
import io
import re

import pytest
from PIL import Image
from sqlalchemy import select

from app.models import DespesaImport, DespesaImportStatus, User
from app.services import storage as storage_mod
from app.services.storage import LocalStorage, S3Storage, get_storage, is_private


class _NoSuchKey(Exception):
    pass


class FakeS3:
    """Cliente S3 mínimo: guarda objetos en memoria y registra los parámetros."""

    class exceptions:  # noqa: N801 — imita `client.exceptions.NoSuchKey` de boto3
        NoSuchKey = _NoSuchKey

    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body, **extra):
        self.objects[Key] = (Body, extra)

    def upload_file(self, path, Bucket, Key, ExtraArgs=None):
        with open(path, "rb") as fh:
            self.objects[Key] = (fh.read(), ExtraArgs or {})

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise _NoSuchKey()
        return {"Body": io.BytesIO(self.objects[Key][0])}

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)

    def generate_presigned_url(self, op, Params, ExpiresIn):
        return f"https://signed.example/{Params['Key']}?ttl={ExpiresIn}&cd={Params.get('ResponseContentDisposition', '')}"


# --- nombres -------------------------------------------------------------------------------

def test_is_private_solo_para_facturas():
    assert is_private("despeses/abc.pdf")
    assert not is_private("abc.png")
    assert not is_private("despesesabc.png")


@pytest.mark.parametrize("nombre", ["../x.png", "a/../b.png", "/etc/passwd", "a/b/c.png", "a b.png", "", "..", "x\\y.png"])
def test_nombres_peligrosos_se_rechazan(nombre, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOADS_LOCAL_DIR", str(tmp_path))
    with pytest.raises(ValueError):
        LocalStorage().save(nombre, b"x")
    with pytest.raises(ValueError):
        S3Storage("b", client=FakeS3()).save(nombre, b"x")


# --- local ---------------------------------------------------------------------------------

def test_local_guarda_lee_y_borra(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOADS_LOCAL_DIR", str(tmp_path))
    st = LocalStorage()
    st.save("a.png", b"hola")
    st.save("despeses/f.pdf", b"pdf")
    assert (tmp_path / "a.png").read_bytes() == b"hola"
    assert (tmp_path / "despeses" / "f.pdf").read_bytes() == b"pdf"
    assert st.read("a.png") == b"hola"
    st.delete("a.png")
    assert st.read("a.png") is None
    st.delete("a.png")  # idempotente


def test_local_save_file_copia_el_fichero(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOADS_LOCAL_DIR", str(tmp_path / "dst"))
    src = tmp_path / "v.mp4"
    src.write_bytes(b"video")
    LocalStorage().save_file("v.mp4", str(src))
    assert (tmp_path / "dst" / "v.mp4").read_bytes() == b"video"


def test_get_storage_local_por_defecto_y_s3_por_entorno(monkeypatch):
    monkeypatch.delenv("UPLOADS_BACKEND", raising=False)
    assert isinstance(get_storage(), LocalStorage)
    monkeypatch.setenv("UPLOADS_BACKEND", "s3")
    monkeypatch.delenv("S3_UPLOADS_BUCKET", raising=False)
    with pytest.raises(RuntimeError):
        get_storage()
    monkeypatch.setenv("S3_UPLOADS_BUCKET", "mi-bucket")
    st = get_storage()
    assert isinstance(st, S3Storage) and st.bucket == "mi-bucket"


# --- S3 ------------------------------------------------------------------------------------

def test_s3_usa_prefijos_public_y_private_y_cabeceras_de_cache():
    fake = FakeS3()
    st = S3Storage("bkt", client=fake)
    st.save("logo.png", b"img")
    st.save("despeses/fac.pdf", b"pdf", content_type="application/pdf")
    assert set(fake.objects) == {"public/logo.png", "private/despeses/fac.pdf"}
    assert fake.objects["public/logo.png"][1]["ContentType"] == "image/png"
    assert "immutable" in fake.objects["public/logo.png"][1]["CacheControl"]
    assert fake.objects["private/despeses/fac.pdf"][1]["CacheControl"] == "private, no-store"
    assert fake.objects["private/despeses/fac.pdf"][1]["ContentType"] == "application/pdf"


def test_s3_lee_borra_y_devuelve_none_si_no_existe():
    st = S3Storage("bkt", client=FakeS3())
    assert st.read("nope.png") is None
    st.save("a.png", b"x")
    assert st.read("a.png") == b"x"
    st.delete("a.png")
    assert st.read("a.png") is None


def test_s3_save_file_sube_el_fichero(tmp_path):
    fake = FakeS3()
    src = tmp_path / "v.mp4"
    src.write_bytes(b"video")
    S3Storage("bkt", client=fake).save_file("v.mp4", str(src), content_type="video/mp4")
    assert fake.objects["public/v.mp4"][0] == b"video"
    assert fake.objects["public/v.mp4"][1]["ContentType"] == "video/mp4"


def test_s3_url_firmada_de_la_factura_caduca_y_limpia_el_nombre():
    st = S3Storage("bkt", client=FakeS3())
    url = st.private_url("despeses/f.pdf", expires=300, filename='fac"tura\n1.pdf')
    assert "private/despeses/f.pdf" in url and "ttl=300" in url
    assert 'inline; filename="fac_tura_1.pdf"' in url


# --- endpoints -----------------------------------------------------------------------------

def _admin(client, db, email="admin-storage@example.com"):
    import contextlib as _c
    buf = io.StringIO()
    with _c.redirect_stdout(buf):
        assert client.post("/auth/magic-link", json={"email": email}).status_code == 202
    token = re.search(r"token=([\w\-]+)", buf.getvalue()).group(1)
    resp = client.post(f"/auth/magic-link/verify?token={token}")
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    db.scalar(select(User).where(User.email == email)).role = "admin"
    db.commit()
    return headers


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 4), "red").save(buf, "PNG")
    return buf.getvalue()


def test_subida_de_fondo_de_bloque_de_la_home_funciona(client, db, tmp_path, monkeypatch):
    """Regresión: este endpoint daba 500 (NameError por un import que faltaba)."""
    monkeypatch.setenv("UPLOADS_LOCAL_DIR", str(tmp_path))
    monkeypatch.delenv("UPLOADS_BACKEND", raising=False)
    headers = _admin(client, db)
    r = client.post("/admin/home-blocks/upload-background", headers=headers,
                    files={"file": ("fondo.png", _png(), "image/png")})
    assert r.status_code == 200, r.text
    name = r.json()["url"].removeprefix("/uploads/")
    assert (tmp_path / name).exists()


def test_subida_va_a_s3_cuando_el_backend_es_s3(client, db, monkeypatch):
    fake = FakeS3()
    monkeypatch.setattr(storage_mod, "get_storage", lambda: S3Storage("bkt", client=fake))
    # los routers importan `get_storage` por nombre: se parchea donde se usa
    from app.routers import home_blocks
    monkeypatch.setattr(home_blocks, "get_storage", lambda: S3Storage("bkt", client=fake))
    headers = _admin(client, db, "admin-s3@example.com")
    r = client.post("/admin/home-blocks/upload-background", headers=headers,
                    files={"file": ("fondo.png", _png(), "image/png")})
    assert r.status_code == 200
    key = "public/" + r.json()["url"].removeprefix("/uploads/")
    assert key in fake.objects


def test_url_firmada_de_factura_solo_para_admin_y_es_privada(client, db, monkeypatch):
    fake = FakeS3()
    from app.routers.comptabilitat import despeses_imports as mod
    monkeypatch.setattr(mod, "get_storage", lambda: S3Storage("bkt", client=fake))
    headers = _admin(client, db, "admin-fac@example.com")

    imp = DespesaImport(file_url="/uploads/despeses/abc.pdf", original_filename="Factura Z.pdf",
                        status=DespesaImportStatus.pendent)
    db.add(imp)
    db.commit()

    assert client.get(f"/admin/despeses/imports/{imp.id}/file-url").status_code in (401, 403)
    r = client.get(f"/admin/despeses/imports/{imp.id}/file-url", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "private/despeses/abc.pdf" in body["url"] and body["expires_in"] == 300

    # una importación cuyo fichero no es privado no genera URL
    otro = DespesaImport(file_url="/uploads/x.png", original_filename="x.png", status=DespesaImportStatus.pendent)
    db.add(otro)
    db.commit()
    assert client.get(f"/admin/despeses/imports/{otro.id}/file-url", headers=headers).status_code == 404
