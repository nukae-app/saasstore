# Registro de actividades de tratamiento (RGPD art. 30) — borrador

Documento interno. Responsable: Ultra-Local Records (Poblenou, Barcelona). **Borrador técnico elaborado a partir del código; la gestoría/asesoría legal debe validarlo y completar los datos marcados con [COMPLETAR].** Última revisión: 2026-11-12.

## 1. Tratamientos

| # | Tratamiento | Finalidad | Base jurídica | Datos | Interesados | Conservación | Destinatarios / encargados |
|---|-------------|-----------|---------------|-------|-------------|--------------|----------------------------|
| 1 | Cuenta de usuario | Acceso, historial, direcciones | Ejecución de contrato (6.1.b) | Email, nombre, hash de contraseña, identidad Google (sub), idioma, direcciones | Clientes | Mientras la cuenta exista; anonimización a petición (los pedidos se conservan) | AWS (hosting, RDS), Google (login OIDC, opcional) |
| 2 | Pedidos y pagos | Venta, envío, facturación, garantía y desistimiento | Contrato (6.1.b); obligación legal fiscal (6.1.c) | Contacto, dirección de envío (snapshot), importes, estado de pago. **No se guardan datos de tarjeta** | Compradores (también invitados) | Plazos mercantiles/fiscales (mínimo 4-6 años) [COMPLETAR plazo definitivo] | Redsys (pasarela), transportista, AWS |
| 3 | Newsletter | Comunicaciones comerciales | Consentimiento (6.1.a), LSSI art. 21 | Email, idioma, `consent_newsletter`, `consent_newsletter_at` | Suscriptores | Hasta la baja | Brevo (SMTP), AWS |
| 4 | Emails transaccionales | Confirmaciones, magic link, desistimiento | Contrato / interés legítimo | Email, referencia de pedido | Clientes | Logs del proveedor [COMPLETAR] | Brevo |
| 5 | Analítica web (Faro) | Medir tráfico y errores | Consentimiento (ePrivacy / LSSI 22.2); solo si el usuario acepta el banner | URL, user agent, referrer, id de sesión | Visitantes | Según stack Grafana [COMPLETAR] | Grafana Labs (stack eu-west-6) |
| 6 | Logs técnicos y seguridad | Seguridad, rate limiting, depuración | Interés legítimo (6.1.f) | IP, user agent, rutas | Visitantes | Rotación de logs [COMPLETAR] | AWS, Grafana (Alloy) |
| 7 | Contabilidad | Libros, IVA, facturas recibidas | Obligación legal (6.1.c) | Datos de proveedores y clientes | Proveedores, clientes | Plazos fiscales | Gestoría; Anthropic (OCR de facturas, si se usa) |
| 8 | Peticiones / club del disco | Encargos y avisos de stock | Contrato / consentimiento | Email, preferencias | Clientes | Hasta cumplir o baja | AWS |
| 9 | Contenido embebido (Mixcloud, Bandcamp, SoundCloud, Spotify, YouTube) | Mostrar multimedia | Consentimiento (`EmbedConsent`) | IP y cookies del tercero al cargar el embed | Visitantes | Del tercero | Terceros respectivos |

## 2. Encargados y transferencias internacionales

| Proveedor | Servicio | Ubicación | Mecanismo | Verificar |
|-----------|----------|-----------|-----------|-----------|
| AWS | EC2, RDS, ECR, Secrets Manager | eu-west-1 (Irlanda) | UE | DPA de AWS aceptado |
| Redsys | Pasarela de pago | España | UE | Contrato con la entidad |
| Brevo | Email | UE | UE | DPA aceptado |
| Grafana Labs | Observabilidad (Faro, Alloy) | stack `eu-west-6` (UE) | Empresa matriz en EEUU: confirmar DPF/SCC | DPA + DPF |
| Anthropic | OCR de facturas (admin) | EEUU | DPF/SCC [COMPLETAR] | DPA; no enviar datos personales innecesarios |
| Google | Login OIDC | EEUU/UE | DPF | Solo si el usuario elige Google |
| Discogs | Catálogo (alta de discos) | EEUU | No se envían datos personales | — |

## 3. Medidas de seguridad (resumen técnico)

TLS (Caddy, HSTS), contraseñas con bcrypt, tokens guardados como hash, refresh rotatorio, aislamiento por tenant (RLS), rate limiting por IP real, validación de subidas, CSP en report-only, secretos en AWS Secrets Manager. Ver `docs/PLAN_SEGURETAT_COMPLIMENT.md`.

## 4. Derechos de los interesados

Acceso, rectificación, supresión (anonimización conservando pedidos por obligación fiscal), oposición y baja de newsletter (enlace + one-click). Canal: `info@labotigaaquesta.com`. Plazo de respuesta: 1 mes.

## 5. Pendiente para la gestoría (1.3 / 1.5)

1. **Condiciones de venta** (`/condicions-venda`, texto en BD): comprobar que incluyen
   - desistimiento de 14 días desde la recepción, con enlace a `/desistiment` (la función existe en footer y en «El meu compte») y modelo de formulario;
   - excepción de discos precintados que se han desprecintado (art. 103 TRLGDCU);
   - garantía legal: 3 años en nuevo; en segunda mano, mínimo 1 año pactado por escrito;
   - régimen especial de bienes usados (REBU) en facturas de segunda mano;
   - gastos de devolución a cargo del consumidor solo si se informó antes de comprar;
   - hojas de reclamaciones.
2. **Política de privacidad**: incorporar las secciones 1 y 2 de este documento.
3. **Política de cookies** (`/cookies`, texto en BD): técnicas (sesión, carrito, preferencia de consentimiento) y analítica (Faro, solo con consentimiento).
4. **Aviso legal**: identidad, NIF, domicilio, contacto (LSSI art. 10).
5. Confirmar DPF/SCC de Grafana Labs y Anthropic y firmar los DPA.
