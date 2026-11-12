# Plan: seguridad y cumplimiento normativo (UE/EEUU)

Origen: auditoría estática del 2026-11-11. Contexto: el SaaS multi-tenant **no se va a comercializar**; el único tenant real es Ultra-Local. Por eso se descartan los puntos de cumplimiento propios de un SaaS (DPA con tenants, lista de subencargados para terceros) y se propone simplificar la superficie que solo existía para ello (ver Fase 5).

Estado (2026-11-11): Fase 5 = opción A aprobada. Fase 2 implementada en el repo salvo 2.4 (Alloy) y la restricción de imágenes de Next (ver «Fase 2: estado»). Sin desplegar.

### Fase 2: estado
- 2.1 hecho: `--proxy-headers --forwarded-allow-ips=*` en `api/Dockerfile`; límites en `/checkout/validate-coupon` (30/h) y `/auth/set-password` (10/h).
- 2.2 hecho: `infra/Caddyfile` con snippets `api_proxy`/`web_proxy` (bloquean `/api/metrics` e `/api/internal` en todos los bloques), nosniff en `/uploads`, CSP en report-only con receptor `POST /csp-report` (registra en el log → Grafana). Bloques de superadmin y landing SaaS eliminados (opción A).
- 2.3 hecho: `config.assert_production_secrets()` llamado desde `main.py`.
- 2.4 hecho: Alloy ya no monta `docker.sock`; usa `docker-socket-proxy` de solo lectura (contenedores y redes). Redacción de emails, `token=` y Bearer en los logs antes de enviarlos a Grafana (`loki.process`). Colectores del exporter limitados. Riesgo residual: se mantiene `/:/rootfs:ro` (necesario para las métricas de disco).
- 2.5 hecho salvo `remotePatterns`: validación real de imágenes (`services/uploads.py`: magic bytes, extensión coherente, 10 MB) en los 4 endpoints. `remotePatterns "**"` de Next se mantiene como RIESGO ACEPTADO: portadas con URL manual lo requieren; Next 16 solo admite HTTPS y bloquea IPs privadas, así que no hay SSRF; el residuo es consumo de ancho de banda por el optimizador.
- 2.5b hecho: cookie de carrito `secure`, `/auth/register` genérico (202), tope de 72 bytes en contraseñas, verificación de `Ds_Amount`/`Ds_Currency`/`Ds_MerchantCode` en la notificación de Redsys. Lista corta de contraseñas comunes rechazada (`services/security.py`).

---

## Fase 1 — Cumplimiento con riesgo de sanción real (prioridad máxima)

### 1.1 Consentimiento para Faro / analítica — IMPLEMENTADO en el repo (sin desplegar)
Hecho: `components/lib/analyticsConsent.js` (preferencia en localStorage, 12 meses), `components/store/CookieConsent.jsx` (banner con Acceptar/Rebutjar de igual peso, ca/es/en), `FaroInit` solo inicializa con consentimiento y se pausa y limpia su storage al retirarlo, botón «Preferències de cookies» en el footer. Texto propuesto en `docs/TEXT_PAGINA_COOKIES.md` (pendiente de pegar en el CMS tras validación). Pendiente: verificar en navegador.

- **Problema:** `web/components/observability/FaroInit.jsx` se inicializa siempre desde `web/app/layout.jsx`. Guarda sesión en el navegador y envía URL, UA y referrer a Grafana Cloud sin consentimiento (LSSI 22.2 / ePrivacy; criterio AEPD).
- **Cambios:**
  - Componente `CookieConsent` (banner ca/es/en, botones «Acceptar» y «Rebutjar» con el mismo peso visual, enlace a `/cookies`, opción de cambiar la decisión desde el footer).
  - Decisión guardada en `localStorage` (clave versionada, con caducidad de 12 meses).
  - `FaroInit` solo llama a `initializeFaro` si hay consentimiento `analytics=true`. Si se retira, `faro.api.pause()` y borrar la clave de sesión de Faro.
  - Actualizar la página `cookies` (CMS) con la lista real: técnicas (refresh, carrito) vs analítica (Faro).
  - Reutilizar `EmbedConsent` para los iframes (ya cumple), unificando el almacenamiento de preferencias.
- **Verificación:** con consentimiento rechazado, no hay peticiones al collector ni claves `com.grafana.faro*` en storage (comprobar con DevTools/Chrome MCP). Test de componente.

### 1.2 Newsletter: baja y consentimiento — IMPLEMENTADO en el repo (sin desplegar)
Hecho: cabeceras `List-Unsubscribe` + `List-Unsubscribe-Post` (RFC 8058); `GET /newsletter/baixa` solo valida y `POST` da de baja; nueva página web `/{lang}/newsletter/baixa` (antes el enlace de los correos apuntaba a una ruta inexistente → 404); pie legal con motivo, baja y dirección postal en el idioma del destinatario; `users.consent_newsletter_at` (migración `a3c9d51e7f02`, se rellena sola por listener del modelo; NULL para quienes ya consentían). Requiere `alembic upgrade head` al desplegar.

- Añadir `List-Unsubscribe` + `List-Unsubscribe-Post: List-Unsubscribe=One-Click` (RFC 8058) en `services/emailer.py` para envíos de newsletter.
- `GET /newsletter/baixa` pasa a confirmar con POST (el GET solo muestra página de confirmación; el POST ejecuta). Evita bajas por escáneres de enlaces.
- Verificar/registrar fecha y texto del consentimiento (`consent_newsletter` hoy es solo un bool): añadir `consent_newsletter_at`. Requiere migración Alembic.
- Pie con dirección postal (ya existe en `emailer.py`; comprobar que se aplica a newsletter).

### 1.3 Desistimiento (Directiva 2023/2673) — revisado
Hecho: la función `/desistiment` (pública, con acuse por email) ya estaba en el footer; añadido enlace en «El meu compte». La revisión de textos de condiciones queda en la lista de `docs/REGISTRE_TRACTAMENTS.md` §5 (viven en BD, los valida la gestoría).
- Comprobar que el botón/enlace de desistimiento es visible en footer y en «El meu compte» y que genera acuse en soporte duradero (email ya implementado).
- Revisar textos de condiciones de venta: excepciones al desistimiento, garantía (3 años nuevo / mínimo 1 año usado), REBU.

### 1.4 Sanciones (OFAC) y envíos — IMPLEMENTADO en el repo (sin desplegar)
Hecho: `PAISOS_SANCIONATS` (CU, IR, KP, SY) en `services/enviament.py`; `compute_coste_enviament` lo rechaza y `paisos_disponibles` lo oculta aunque exista un tramo; test parametrizado. Limitación: Crimea/Donetsk/Luhansk comparten código UA, no se bloquean por país (requeriría filtrar por código postal; decisión pendiente, riesgo bajo al ser envíos manuales).
- Revisar `services/enviament.py::paisos_disponibles` y excluir países/regiones sancionados. Test que lo garantice.
- Documentar en el plan de envíos que no se vende a esos destinos.

### 1.5 Documentación legal — borrador hecho
Hecho: `docs/REGISTRE_TRACTAMENTS.md` (registro art. 30, encargados, transferencias y checklist para la gestoría). Pendiente: validación externa y firma de DPA.
- Aviso legal, privacidad, condiciones, cookies: revisión con la gestoría. Incluir encargados reales (Grafana Cloud, Brevo, Anthropic, Google, AWS, Redsys) y base jurídica de cada tratamiento.
- Registro de actividades de tratamiento (documento interno corto).
- Verificar que Grafana Cloud (región del stack) y Anthropic cuentan con DPF o cláusulas tipo.

---

## Fase 2 — Vulnerabilidades de seguridad (media)

### 2.1 Rate limit por IP real
- `api/Dockerfile`: añadir `--proxy-headers --forwarded-allow-ips="*"` (la API solo es alcanzable desde Caddy dentro de la red Docker; confirmar que `expose` sin `ports` se mantiene).
- Test: con `X-Forwarded-For` distinto, buckets distintos.
- Añadir `@limiter.limit` a `/checkout/validate-coupon` y a `set-password`.

### 2.2 Caddy
- Bloquear `/api/metrics` y `/api/internal/*` en **todos** los bloques que hacen proxy a `/api/*` (`infra/Caddyfile`), o extraer un snippet común `(api_proxy)` para que no vuelvan a divergir.
- Añadir CSP. Empezar en `Content-Security-Policy-Report-Only`, revisar violaciones una semana (Faro/Next inline scripts, iframes Mixcloud/Bandcamp/YouTube/Spotify/SoundCloud, imágenes Discogs), y pasar a enforce. Incluir `frame-ancestors 'self'`.
- `Permissions-Policy` ya está solo en el bloque principal: unificar.
- `X-Content-Type-Options: nosniff` también para `/uploads/*`.

### 2.3 Guarda de arranque para secretos
- En `config.py`/`main.py`: si `redsys_environment == "production"` (o variable `ENVIRONMENT=production`), abortar el arranque si `secret_key` o `superadmin_secret_key` valen el default o tienen menos de 32 caracteres.
- Test unitario.

### 2.4 Alloy
- Quitar el montaje `/:/rootfs` y limitar métricas del host a lo imprescindible (o usar un exporter dedicado). Sustituir el acceso directo a `docker.sock` por un `docker-socket-proxy` de solo lectura (contenedores/logs) o recoger logs con el driver de logging.
- Revisar que los logs no contienen emails ni tokens; añadir redacción en la config de Alloy.

### 2.5 Imágenes y uploads
- `web/next.config.mjs`: sustituir `hostname: "**"` por allowlist (`i.discogs.com`, `img.discogs.com`, dominio propio, S3 si procede) o `unoptimized` para imágenes de host libre.
- Uploads (`admin/images.py`, `home_blocks.py`, `configuracio.py`, `admin_newsletter.py`): extraer un helper común que compruebe magic bytes (Pillow `verify()`), límite de tamaño y re-codifique la imagen. Test con fichero `.png` que es HTML.

### 2.5b Observaciones menores
- Cookie del carrito con `secure=True`.
- `/auth/register`: respuesta genérica 202 igual exista o no el email (y avisar por email si ya existía).
- Redsys notify: verificar `Ds_Amount`, `Ds_Currency` y `Ds_MerchantCode` contra el pedido y el tenant.
- Contraseñas: capar a 72 bytes explícitamente (bcrypt) y rechazar claves en lista de contraseñas comunes.

---

## Fase 3 — Higiene del repo e infraestructura — HECHA
Hecho: `db.txt` fuera del repo y en `.gitignore`; `deletion_protection` activado en las dos RDS (AWS CLI + `.tf` actualizados, `nukaesaas` con snapshot final); `pip-audit` sin vulnerabilidades. Pendiente opcional: integrar `pip-audit` en CI.

- Quitar `db.txt` del repo (`git rm`), añadirlo a `.gitignore`. El endpoint RDS y la IP del bastión no son secretos, pero no deberían versionarse.
- RDS: `deletion_protection = true`, y backups fuera del VPS ya previstos en CLAUDE.md (verificar restore).
- Instalar y ejecutar `pip-audit` (api) y `npm audit` (web, ya a 0) en CI/pre-deploy.
- Ejecutar `claude-security:scan` sobre todo el repo tras la Fase 2 para cubrir el control de acceso por objeto que esta auditoría no revisó.

---

## Fase 4 — Auditoría — HECHA
Resultado: `/me/*`, carrito (cookie de sesión) y `GET /checkout/{id}` (UUID aleatorio, datos mínimos, comprobación de tenant) correctos. SSRF: sin vectores (URLs fijas; el CSV es configuración; `fontsource` solo descarga ids de su lista). Corregido en `admin_users`: rol validado (`cliente`/`admin`), no se puede degradar/desactivar al último admin, `set-password` con tope de 72 bytes y lista de contraseñas comunes. Corregido bug intermitente en `_free_external_id` (UPDATE ordenado por UUID chocaba con la unicidad del `external_id` al mover un código de Discogs entre ítems). No auditado por falta de acceso: datos reales en producción.

- IDOR/autorización por objeto en `/me/*`, carrito de invitados y pedidos de invitado.
- Revisar `admin_users` (cambio de rol, anonimizar) y `comptabilitat` con datos fiscales.
- SSRF: `CATALOG_SHEET_CSV_URL` y fuentes (`fontsource`) con URL configurable.
- Pruebas de rate limit y concurrencia en checkout/reservas con el nuevo bucket por IP.

---

## Fase 5 — Simplificación por «SaaS descartado» (decisión tuya)

Si el SaaS no se va a vender, reducir superficie de ataque en vez de mantenerla:
- **Opción A (mínima):** dejar el código, pero no exponer `SUPERADMIN_HOST` ni la landing `NEXT_PUBLIC_APP_HOST` en Caddy; no registrar dominios. Cero cambios de código.
- **Opción B:** eliminar bloques de Caddy, middleware y rutas `/superadmin`, `billing_webhooks.py` (Revolut) y `internal.py::ask_domain` si deja de usarse TLS on-demand. Menos que mantener y auditar.
- Recomendación: A ahora (con Fase 2.2 ya cubre lo importante) y B cuando haya tiempo, sin prisa.

---

## Orden y esfuerzo estimado

| # | Tarea | Esfuerzo |
|---|-------|----------|
| 1 | 2.1 + 2.2 (rate limit, Caddy, CSP report-only) | medio día |
| 2 | 2.3 guarda de secretos | 1 h |
| 3 | 1.1 banner + Faro condicionado | 1 día |
| 4 | 1.2 newsletter (cabeceras, POST, migración) | medio día |
| 5 | 1.4 sanciones + test | 1-2 h |
| 6 | 2.5 / 2.5b uploads, imágenes, Redsys, cookies | 1 día |
| 7 | 2.4 Alloy | medio día |
| 8 | Fase 3 + Fase 4 | 1-2 días |
| 9 | 1.3 / 1.5 documentación legal | externo (gestoría) |

## Decisiones que necesito de ti
1. Fase 5: ¿opción A o B?
2. CSP: ¿empezamos en report-only una semana?
3. Banner de cookies: ¿texto/estilo propio de la tienda o el más neutro posible?
4. ¿Quién hace la revisión de los textos legales (gestoría)?

## Criterio de cierre
- `cd api && python -m pytest` verde con tests nuevos por cada cambio de backend.
- Verificación manual en navegador del banner y de las cabeceras (`curl -I`).
- Re-escaneo final con `claude-security` sin hallazgos medios o superiores abiertos.
