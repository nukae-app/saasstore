# Subidas del admin en S3 + CloudFront

Estado (2026-11-12): código, Terraform y scripts listos en el repo. **Sin aplicar ni desplegar** hasta confirmar.

## Diseño
- Bucket privado `nukaesaas-uploads-<cuenta>` (eu-west-1): acceso público bloqueado, cifrado, **versionado** (las versiones antiguas se conservan 90 días). El versionado sustituye a una copia diaria.
- Prefijos: `public/` (imágenes, vídeos, tipografías, imágenes de newsletter) y `private/despeses/` (facturas de gastos).
- Lo público lo sirve **CloudFront** (OAC, solo `public/`) a través de Caddy en `/uploads/*`: mismo origen, sin CORS ni cambios de CSP, y las URLs guardadas en la BD (`/uploads/<uuid>.ext`) no cambian.
- Las **facturas ya no son públicas** (antes se servían por `/uploads/despeses/` sin autenticación): Caddy responde 404 a esa ruta y el admin las abre con una URL firmada de 5 minutos (`GET /admin/despeses/imports/{id}/file-url`).
- API: `app/services/storage.py` con backends `local` (dev/tests, por defecto) y `s3` (`UPLOADS_BACKEND=s3`, `S3_UPLOADS_BUCKET`).

## Piezas
| Qué | Dónde |
|---|---|
| Servicio de almacenamiento | `api/app/services/storage.py` (+ `tests/test_storage.py`) |
| Infra (bucket, CloudFront, permiso EC2) | `infra/terraform-uploads/` (state propio, sin `db_password`) |
| Copia de los archivos existentes | `scripts/migrate_uploads_to_s3.sh dry|run` |
| Caddy | `infra/Caddyfile` (`UPLOADS_CDN_HOST`) |
| Variables en el servidor | las escribe `scripts/deploy_nukaesaas.sh` en `.env` |
| Presupuesto de la cuenta | `infra/terraform-budget/` (40 USD/mes, aviso al 50 %) — ya aplicado |

## Orden de puesta en marcha
1. `terraform -chdir=infra/terraform-uploads apply` (10 recursos nuevos, nada se modifica ni se borra).
2. `scripts/migrate_uploads_to_s3.sh dry` y luego `run`.
3. `scripts/deploy_nukaesaas.sh` (activa `UPLOADS_BACKEND=s3`, el bucket y el dominio de CloudFront a la vez).
4. Repetir `migrate_uploads_to_s3.sh run` por si se subió algo entre el paso 2 y el 3.
5. Verificar: imagen de la home, logo, subir una imagen nueva, abrir una factura, `/uploads/despeses/<x>` → 404.

## Vuelta atrás
`UPLOADS_BACKEND=local` en el `.env` del servidor + redeploy del commit anterior (Caddy vuelve a servir el volumen). El volumen `nukaesaas_uploads` no se toca: se conserva como copia hasta dar la migración por buena.

## Coste
CloudFront dentro de la capa gratuita permanente (1 TB y 10 M de peticiones al mes); S3 de céntimos. Presupuesto general de la cuenta en 40 USD con alerta al 50 %.

## Pendiente aparte
Snapshots diarios del disco EBS con retención de 30 días (Data Lifecycle Manager) y cifrado del disco.
