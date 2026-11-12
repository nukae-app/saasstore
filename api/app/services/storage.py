"""Almacenamiento de los ficheros que sube el admin (imágenes, vídeos, tipografías
y facturas de gastos).

Dos backends, elegidos por `UPLOADS_BACKEND`:
- `local` (por defecto: desarrollo y tests): carpeta `UPLOADS_LOCAL_DIR`
  (`/app/uploads`), la que Caddy sirve en dev.
- `s3` (producción): bucket `S3_UPLOADS_BUCKET`, con dos prefijos:
    `public/...`   imágenes, vídeos, fuentes → las sirve CloudFront por /uploads/*.
    `private/...`  facturas de gastos → NUNCA públicas; el admin las abre con una
                   URL firmada de corta duración (`private_url`).

Un nombre es privado si empieza por `despeses/` (ver `is_private`). Las URLs que
se guardan en la BD siguen siendo `/uploads/<nombre>`, igual que antes: la
migración al bucket no cambia ningún dato guardado.
"""

import mimetypes
import os
import re
import shutil
from functools import lru_cache

PRIVATE_PREFIXES = ("despeses/",)
_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)?$")
PUBLIC_CACHE_CONTROL = "public, max-age=31536000, immutable"  # nombres = UUID, nunca se reescriben
PRIVATE_CACHE_CONTROL = "private, no-store"


def is_private(name: str) -> bool:
    return name.startswith(PRIVATE_PREFIXES)


def _check(name: str) -> str:
    # Un solo nivel de subcarpeta como máximo y sin `..`: el nombre acaba en una ruta/clave.
    if not _NAME_RE.match(name) or ".." in name:
        raise ValueError(f"Nombre de fichero no válido: {name!r}")
    return name


def _content_type(name: str, explicit: str | None) -> str:
    return explicit or mimetypes.guess_type(name)[0] or "application/octet-stream"


class LocalStorage:
    backend = "local"

    @staticmethod
    def base_dir() -> str:
        return os.environ.get("UPLOADS_LOCAL_DIR", "/app/uploads")

    def _path(self, name: str) -> str:
        return os.path.join(self.base_dir(), _check(name))

    def save(self, name: str, content: bytes, content_type: str | None = None) -> None:
        path = self._path(name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(content)

    def save_file(self, name: str, source_path: str, content_type: str | None = None) -> None:
        path = self._path(name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        shutil.copyfile(source_path, path)

    def read(self, name: str) -> bytes | None:
        try:
            with open(self._path(name), "rb") as fh:
                return fh.read()
        except FileNotFoundError:
            return None

    def delete(self, name: str) -> None:
        try:
            os.remove(self._path(name))
        except FileNotFoundError:
            pass

    def private_url(self, name: str, expires: int = 300, filename: str | None = None) -> str:
        # En local no hay firma: Caddy de desarrollo sirve la carpeta tal cual.
        return f"/uploads/{_check(name)}"


class S3Storage:
    backend = "s3"

    def __init__(self, bucket: str, client=None, region: str = "eu-west-1"):
        self.bucket = bucket
        self._client = client
        self._region = region

    @property
    def client(self):
        if self._client is None:
            self._client = _s3_client(self._region)
        return self._client

    @staticmethod
    def key(name: str) -> str:
        return f"{'private' if is_private(name) else 'public'}/{_check(name)}"

    def _extra(self, name: str, content_type: str | None) -> dict:
        return {
            "ContentType": _content_type(name, content_type),
            "CacheControl": PRIVATE_CACHE_CONTROL if is_private(name) else PUBLIC_CACHE_CONTROL,
        }

    def save(self, name: str, content: bytes, content_type: str | None = None) -> None:
        self.client.put_object(Bucket=self.bucket, Key=self.key(name), Body=content, **self._extra(name, content_type))

    def save_file(self, name: str, source_path: str, content_type: str | None = None) -> None:
        self.client.upload_file(source_path, self.bucket, self.key(name), ExtraArgs=self._extra(name, content_type))

    def read(self, name: str) -> bytes | None:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=self.key(name))["Body"].read()
        except self.client.exceptions.NoSuchKey:
            return None

    def delete(self, name: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self.key(name))

    def private_url(self, name: str, expires: int = 300, filename: str | None = None) -> str:
        params = {"Bucket": self.bucket, "Key": self.key(name)}
        if filename:
            safe = re.sub(r'[^A-Za-z0-9._ -]', "_", filename)
            params["ResponseContentDisposition"] = f'inline; filename="{safe}"'
        return self.client.generate_presigned_url("get_object", Params=params, ExpiresIn=expires)


@lru_cache(maxsize=4)
def _s3_client(region: str):
    import boto3

    return boto3.client("s3", region_name=region, config=_s3_config())


def _s3_config():
    from botocore.config import Config

    # Firma v4 y direccionamiento regional: las URLs firmadas salen contra el endpoint de la región.
    return Config(signature_version="s3v4", s3={"addressing_style": "virtual"})


def get_storage() -> LocalStorage | S3Storage:
    if os.environ.get("UPLOADS_BACKEND", "local").lower() == "s3":
        bucket = os.environ.get("S3_UPLOADS_BUCKET")
        if not bucket:
            raise RuntimeError("UPLOADS_BACKEND=s3 requiere S3_UPLOADS_BUCKET")
        return S3Storage(bucket, region=os.environ.get("AWS_REGION", "eu-west-1"))
    return LocalStorage()
