# Apps nativas — admin y tienda/comunidad (propuesta)

**Estado: propuesta, no aplicada.** No se ha tocado modelo, schema, endpoint ni frontend. Sigue el mismo protocolo que el resto de fases de este proyecto: proponer, discutir, no escribir migración/código hasta aprobarlo.

Contexto: con el ERP (compras, TPV), el admin web y la plataforma multi-vertical ya en marcha (ver `docs/ARQUITECTURA_CORE_VERTICAL.md`), el SaaS gana una capa más: gestión desde móvil/tablet y presencia de venta nativa por tienda. Este documento diseña **cómo se gestiona eso**, no si se construye — la decisión de negocio ya está tomada, esto es la arquitectura.

---

## 1. Dos apps, no una — y son arquitecturas distintas

| | App de Admin | App de Tienda/Comunidad |
|---|---|---|
| Usuario | Personal de cada tienda (gestión) | Clientes finales de cada tienda |
| Identidad en la store | **Una sola ficha**, multi-tenant (login elige el tenant) | **Una ficha por tenant** (icono/nombre propio) |
| Por qué | Herramienta interna, como el `/admin` web hoy — nadie necesita "la app de admin de Escaparate" en su home screen | Cara al público: un cliente busca "la app de [su tienda]", no una app genérica de la plataforma |
| Coste de publicar | Una vez, sirve a todos los tenants presentes y futuros | Una vez por tenant que quiera tener su propia app |

Esta distinción es la decisión de diseño más importante: **la app de Admin es exactamente el mismo modelo multi-tenant que ya tiene el admin web** (un dominio, login resuelve el tenant). La complejidad de "build por tenant" solo aplica a la app de Tienda/Comunidad, porque solo ahí importa la marca de cada negocio en el dispositivo del cliente.

---

## 2. Lo que ya existe y se reutiliza tal cual

- **Tokens de tema por tenant** (`api/app/schemas/configuracio.py::ThemeTokens`, expuestos por `GET /config/public`): `primary`, `secondary`, `accent`, `background`, `foreground`, `border` (+`_foreground`), `font_headline`, `font_body`, `radius_card`, `radius_button`, `logo_url`, `favicon_url`. Hoy `web/app/layout.jsx` los pinta como variables CSS; un `ThemeProvider` nativo leería exactamente el mismo JSON, mismos nombres de clave — cero vocabulario nuevo.
- **Registro de verticals** (`verticals`: `product_archetype`, `catalog_provider`, `default_features`) y `tenant_features` — ambas apps deciden qué pantallas/campos mostrar consultando lo mismo que ya consulta el admin web, no un mecanismo paralelo.
- **API ya es API-only** (principio de CLAUDE.md: "el front solo habla con la API") — no hay lógica de negocio escondida en el frontend web que haya que duplicar para nativo.
- **`Tenant.slug`** (`api/app/models/platform.py:31`, `String(60) unique`) ya existe como identificador estable independiente del dominio — es el candidato natural para identificar tenant sin `Host` header.

---

## 3. Lo que falta construir (aditivo, no toca el flujo web)

### 3.1 Resolución de tenant sin dominio — aplica a LAS DOS apps

Hoy `get_db()` (`api/app/database.py:23-55`) resuelve el tenant **solo** por `Host`/`X-Forwarded-Host` vía `resolve_tenant_by_domain()` (`api/app/tenancy.py:42-48`), y lanza 404 si no hay match — y esto pasa **antes** de que se ejecute ninguna lógica de autenticación, porque `apply_local_tenant()` fija el aislamiento a nivel de sesión de BD para toda la request (login incluido). Consecuencia importante, verificada en el código (corrige una suposición anterior de este documento): **no hay forma de diferir la resolución de tenant a "después de decodificar el JWT"** — toda request, incluida la del propio login, necesita ya un tenant resuelto. Esto aplica igual a las dos apps, no solo a la de Tienda.

`get_db()` intenta primero por `Host` (comportamiento actual, sin cambios); si no hay match, cae a un header `X-Tenant-Slug` y resuelve por `Tenant.slug` en vez de `Tenant.domain`. Mismo `HTTPException(404, ...)` si tampoco hay match ahí. Es un `or` adicional en una función ya centralizada — un solo punto de cambio, cero riesgo para el tráfico web (que nunca manda ese header).

```python
tenant = resolve_tenant_by_domain(db, host)
if tenant is None:
    slug = request.headers.get("x-tenant-slug")
    if slug:
        tenant = resolve_tenant_by_slug(db, slug)
if tenant is None:
    raise HTTPException(404, "Tienda no encontrada")
```

- **App de Tienda/Comunidad**: el slug va fijado en build-time (`app.config.js` del build de ese tenant) — cada binario "sabe" quién es, ni pantalla de selección ni ambigüedad.
- **App de Admin**: una sola app sirve a todos los tenants, así que el slug no puede ir fijado en build. Lo captura la pantalla de login (el usuario introduce el slug/subdominio de su tienda una vez — patrón "workspace URL" tipo Slack), se guarda en local storage del dispositivo, y viaja como `X-Tenant-Slug` en cada request posterior, incluida la del propio login.

### 3.2 Auth nativo — decisión final (2026-09-09)

`POST /auth/*` (login/magic-link/google callback, `api/app/routers/auth.py:98` y `:292`) ya devuelve el access token en el **body JSON** (`TokenOut`). El refresh token, en cambio, solo sale por `set_cookie(..., httponly=True)` — un cliente nativo no tiene cookie jar de navegador y no debería depender de él.

**Descartado deliberadamente**: ramificar los endpoints web existentes con un header tipo `X-Client: native` para decidir si el refresh sale en JSON. Es explotable: un XSS en la web podría mandar ese mismo header en su propio `fetch()` y sacarse por JSON el refresh token que hoy la cookie `httpOnly` protege de JS — el propio mecanismo de protección quedaría anulado por su flexibilidad. No es una hipótesis lejana, es exactamente el vector que `httpOnly` existe para cerrar.

**Diseño adoptado — endpoints nativos dedicados, en paralelo, no una rama sobre los existentes:**

- `POST /auth/mobile/magic-link/verify`, `POST /auth/mobile/google/callback`, `POST /auth/mobile/refresh`, `POST /auth/mobile/logout` — nuevos. Los `/auth/*` actuales (web) no se tocan, ni un carácter: cero riesgo de regresión sobre el flujo hoy en producción.
- Reutilizan las mismas primitivas de `services/security.py` (`create_access_token`, `issue_refresh_token`, `rotate_refresh_token`, `revoke_refresh_token`) — son una capa HTTP distinta sobre la misma lógica de sesión, no una reimplementación paralela.
- `POST /auth/mobile/refresh` exige el refresh token **explícito en el body**, nunca lo lee de cookie. Esto es lo que cierra el vector del XSS: aunque un atacante llame a este endpoint desde JS inyectado en la web, no tiene ningún token válido que mandar (el de la web es `httpOnly`, nunca fue legible por JS).

**Endurecimiento añadido, beneficia a ambos flujos:** `rotate_refresh_token()` (`services/security.py:81-91`) hoy, si le llega un token ya revocado, solo devuelve `None` (401). Se añade detección de reuso: si el token presentado ya tiene `revoked_at` fijado (alguien está reutilizando uno que ya fue rotado — señal de robo, no de carrera legítima), revocar **todos** los refresh tokens activos de ese usuario, forzando relogin en todos los dispositivos. Con un refresh token viviendo 30 días en un móvil que se puede perder o robar, esta detección deja de ser opcional.

**Almacenamiento y transporte en el dispositivo (no negociable, no "ya lo ajustamos luego"):**
- Refresh token → `expo-secure-store` (Keychain iOS / Keystore Android), nunca `AsyncStorage` ni almacenamiento plano.
- Google login → `expo-auth-session` contra el navegador del sistema (PKCE), nunca un WebView embebido — evita que la app pueda interceptar credenciales en una pantalla de login que no controla.
- Magic link → Universal Links (iOS) / App Links (Android) con dominio verificado, no un esquema custom (`miapp://`) — un esquema custom lo puede registrar otra app instalada en Android y secuestrar el enlace; un Universal/App Link verificado por dominio no se puede suplantar así.

### 3.3 Modelo de datos: ciclo de vida de "una app por tenant"

Falta un sitio donde vivan los metadatos de publicación de cada app de tienda (no existen hoy en `Tenant` ni `ConfiguracioBotiga`). Propuesta de tabla nueva, a discutir:

```
tenant_apps
  tenant_id         FK -> tenants.id (unique — una app de tienda por tenant, de momento)
  bundle_id_ios     string null   -- "com.ultralocal.escaparate"
  bundle_id_android string null
  app_store_url     string null
  play_store_url    string null
  status            enum          -- "not_built" | "in_review" | "published" | "needs_update"
  icon_asset_url    string null   -- si difiere del logo_url ya existente en ConfiguracioBotiga
  last_built_at      timestamp null
  last_submitted_at  timestamp null
```

Puntos a decidir contigo antes de modelarlo en firme:
1. ¿`icon_asset_url` separado, o basta reutilizar `ConfiguracioBotiga.logo_url` recortado/adaptado en el propio pipeline de build (menos campos, un asset menos que mantener sincronizado)?
2. ¿Este ciclo de vida lo gestiona superadmin (una pantalla más, análoga a `superadmin/verticals`) o es puramente operativo (vosotros lo lleváis a mano al principio, y se modela cuando haya más de 2-3 tenants con app propia)?
3. `status` como enum fijo vs texto libre — mismo criterio que ya se aplicó a `catalog_provider`/`product_archetype`: registro cerrado, no texto libre.

---

## 4. Stack y pipeline de build

- **React Native + Expo** para ambas apps: el equipo ya está en React/Next, y Expo (EAS Build + EAS Submit + EAS Update) resuelve exactamente el problema de "un codebase, N binarios con distinta identidad" sin mantener proyectos Xcode/Android Studio a mano por tenant.
- **App de Admin**: un solo `app.config.js`, un solo perfil de build, un solo submit. Reaprovecha el `TokenOut`/refresh de §3.2 y las mismas pantallas conceptuales que el admin web (pedidos, TPV, compras, catálogo) — su prioridad de construcción es independiente de la app de Tienda.
- **App de Tienda/Comunidad**: un `app.config.js` **generado**, no escrito a mano por tenant — un script lee `Tenant`+`ConfiguracioBotiga` (nombre, slug, logo, tokens de tema) de la fila real y produce la config de ese build (`eas build --profile <slug>`). Mismo principio que ya usa `import_catalog.py`: automatizar el dato repetitivo en vez de mantenerlo a mano N veces.
- **EAS Update (OTA)** para todo cambio JS/contenido — no pasa por review de Apple/Google. Solo un cambio nativo real (permiso nuevo, librería nativa, cambio de icono) fuerza un resubmit por tenant.
- **Cuenta de developer**: una sola cuenta Apple/Google para toda la plataforma — cada tenant es una ficha (app) distinta bajo la misma cuenta, no una cuenta separada.

---

## 5. Fases propuestas (orden, no calendario)

1. **App de Admin primero.** Menor riesgo (una sola app, no N), mayor apalancamiento inmediato (sirve a los 5 tenants reales de golpe en cuanto se publica una vez). Requiere §3.2 (auth nativo) pero no §3.3 (modelo de ciclo de vida de apps) ni el generador de config por tenant.
2. **Resolución de tenant sin dominio (§3.1)** — necesaria para ambas apps, pero solo se ejercita de verdad con la segunda.
3. **App de Tienda/Comunidad, piloto en un solo tenant real** (candidato: `recordstore` o `escaparate` como demo) — valida el pipeline de build generado + theming en runtime antes de decidir si se ofrece como opción a las demás tiendas.
4. **Modelo `tenant_apps` (§3.3) y automatización del alta** — solo cuando haya más de un tenant pidiendo su propia app; antes de eso, gestionarlo a mano es más barato que construir la pantalla de superadmin para ello.

---

## 6. Fase 1 — alcance del MVP de la App de Admin (acordado, 2026-09-09)

División deliberada entre lo que gana algo real siendo nativo/móvil y lo que se queda en el admin web (que sigue siendo responsive y accesible desde cualquier tablet — no se pierde nada, solo no se porta a nativo todavía):

- **Nativo desde el día 1**: **Pedidos** (consultar estado, marcar enviado/nº seguimiento), **TPV** (venta de mostrador), **Compra particular** (alta de compra a particular en mostrador), **Catálogo** (edición rápida de stock/precio/grading de items existentes + alta nueva de release con el mismo buscador de Discogs que ya usa el admin web). Las cuatro reutilizan endpoints ya existentes (`/admin/orders`, `/admin/tpv/*`, `/admin/compras/*`, `/admin/releases`, `/admin/items`, `/admin/discogs/search`) — los cambios de backend que requieren son §3.1 (resolución de tenant por `X-Tenant-Slug`) y §3.2 (endpoints `/auth/mobile/*`).
- **Se queda en web por ahora** (formularios densos, uso infrecuente, mejor con teclado/ratón): configuración/tema, resultat/contabilidad, CMS de blog/agenda, subscripcions.

Orden de construcción dentro del MVP: spike de auth (§5, punto 2) primero, validado con una lista simple de Pedidos; Catálogo (edición + alta) y TPV después, en el orden que convenga según carga de trabajo real de la tienda piloto.

### 6.1 Stack técnico (decidido, 2026-09-09)

Elegido en sus propios méritos para una app nativa — deliberadamente **no** se copia el stack de `web/` (Next.js/React 19, sin TypeScript, Tailwind v4 + shadcn) solo por consistencia; se reutiliza únicamente lo que sigue siendo la misma pieza de infraestructura (la API, los mismos endpoints) y lo que resuelve mejor un problema nativo real, no lo que "ya se hace en web".

| Pieza | Elección | Por qué |
|---|---|---|
| Framework | Expo (managed) | EAS Build/Update ya forma parte del diseño de la app de Tienda (§4); sin necesidad prevista de módulos nativos custom. |
| Lenguaje | **TypeScript** | Decisión explícita del usuario: para una app que toca TPV y stock (dinero y existencias reales), el tipado atrapa errores de contrato con la API antes de producción. |
| Routing | Expo Router | Layouts anidados, tabs, y deep-linking nativo — necesario de todos modos para el callback de Google/magic link (§3.2), no por parecerse al App Router de Next.js. |
| Estilos | NativeWind | Motor de estilos utilitario, no un lenguaje visual impuesto — permite construir una identidad visual **nueva, desde cero** (decisión explícita del usuario: no se hereda el MD3 del admin web) tan rápido como cualquier alternativa. |
| Kit de componentes | Ninguno (componentes propios) | Se descarta React Native Paper/Tamagui/Gluestack por venir con un lenguaje visual propio (MD3 en el caso de Paint) que chocaría con "identidad nueva desde cero". |
| Datos/API | TanStack Query | Cache/retry en cliente — sin SSR, hace falta explícitamente; importante en TPV con wifi de tienda poco fiable. |
| Auth storage | `expo-secure-store` + `expo-auth-session` | Ver §3.2 — Keychain/Keystore para el refresh token, navegador del sistema con PKCE para Google. |
| Ubicación | `admin-app/` en la raíz del repo, junto a `web/`/`api/`/`infra/` | Monorepo simple, sin workspaces — no hay código compartido real con `web/` que lo justifique todavía. |
| Plataforma | **Android primero, iOS más adelante** | Herramienta interna, no cara al cliente: distribución vía APK directo/Play "Internal testing" (sin coste, sin revisión) — iOS exige Apple Developer Program (99€/año) incluso para distribución interna vía TestFlight, coste que no compensa antes de tener uso real en un dispositivo Apple. Con Expo el código sigue siendo el mismo para los dos; esto es una decisión de secuencia de distribución, no de arquitectura. |

**Pendiente, es trabajo de diseño, no una decisión técnica más**: paleta, tipografía y tono visual propios de la app — a definir aparte, no se hereda nada de `web/admin` ni de las tiendas.

---

## 7bis. Backend — implementado (2026-09-09)

Los tres cambios de §3.1/§3.2 están hechos y con tests:

- `app/tenancy.py::resolve_tenant_by_slug` + fallback en `app/database.py::get_db` (header `X-Tenant-Slug`, solo si no hay match por `Host`/`X-Forwarded-Host` — el tráfico web no lo manda nunca, cero cambio de comportamiento ahí).
- `app/routers/auth_mobile.py` (nuevo): `POST /auth/mobile/magic-link/verify`, `POST /auth/mobile/refresh`, `POST /auth/mobile/logout` — devuelven `MobileTokenOut` (`access_token` + `refresh_token` en JSON), nunca cookie. `/auth/*` (web) no se ha tocado.
- `services/security.py::get_or_create_user` — se sacó de `routers/auth.py` (era privada, `_get_or_create_user`) para que la comparta también `auth_mobile.py`, una sola implementación.
- `services/security.py::rotate_refresh_token` — detección de reuso: si el token presentado ya estaba revocado, `revoke_all_refresh_tokens` tumba todos los refresh tokens activos del usuario (fuerza relogin en todos los dispositivos), no solo se rechaza ese intento.
- `api/tests/test_auth_mobile.py` (nuevo, 7 tests): tokens en JSON sin cookie, rotación, rechazo de reuso, revocación en cascada tras reuso, logout, y las dos ramas del fallback `X-Tenant-Slug` (válido/inválido).
- `pytest`: 630 passed, 1 failed (`test_superadmin_tenant_features.py::test_features_por_defecto_desactivadas` — mismo fallo preexistente y no relacionado que ya documentan otras fases de `ARQUITECTURA_CORE_VERTICAL.md`).

**Fuera de esta entrega, a propósito**: `POST /auth/mobile/google/callback` (login con Google nativo) — necesita el lado cliente (`expo-auth-session`, PKCE) para tener sentido probarlo de verdad; se añade cuando se construya esa pantalla, no antes. Tampoco se ha tocado el email de `/auth/magic-link` para que enlace a un Universal Link — eso depende de que exista ya el bundle id/dominio asociado de la app (infra del scaffold de Expo, no del backend); mientras tanto, el token se puede copiar a mano desde el enlace para probar el endpoint móvil durante el desarrollo.

---

## 7ter. Scaffold — spike de auth implementado (2026-09-09)

`admin-app/` (raíz del repo, junto a `web/`/`api/`): Expo SDK 57 + TypeScript + Expo Router + NativeWind + TanStack Query + `expo-secure-store`, tal como se decidió en §6.1. Cubre el spike de §5 punto 2: login por magic link contra la API real, sesión persistida en el dispositivo (refresh token en Keychain/Keystore, nunca `AsyncStorage`), y una lista de Pedidos autenticada (`GET /admin/orders`).

- `lib/config.ts` — base de la API, con el alias `10.0.2.2` del emulador de Android hacia el host por defecto (override por `EXPO_PUBLIC_API_URL` en `.env` para dispositivo físico).
- `lib/secureStorage.ts` — refresh token + slug de tenant en `expo-secure-store`. El access token vive solo en memoria (estado de React), se recupera con un refresh silencioso al abrir la app.
- `lib/api.ts` — cliente de API tipado (`fetch` + `X-Tenant-Slug` + `Authorization: Bearer`), llamadas a `/auth/magic-link`, `/auth/mobile/*` (§7bis) y `/admin/orders`.
- `lib/auth.tsx` — `AuthProvider`/`useAuth()`: estado `loading`/`signedOut`/`signedIn`, intenta recuperar sesión al arrancar, expone `requestLink`/`verifyToken`/`signOut`.
- `app/_layout.tsx`, `app/index.tsx` (redirect según estado de auth), `app/login.tsx` (slug + email → pedir enlace → pegar token → verificar), `app/orders.tsx` (lista con `useQuery`, pull-to-refresh, cerrar sesión).
- Verificado: `tsc --noEmit` sin errores; `npx expo export --platform android` bundlea sin fallos (1636 módulos) — confirma que Metro/Babel/NativeWind/Reanimated están correctamente encadenados antes de depender de un emulador real.
- Fricciones reales encontradas y resueltas (quedan documentadas para no repetirlas): `babel-preset-expo` no viene como dependencia explícita en la plantilla en blanco — hace falta instalarlo a mano en cuanto se usa un `babel.config.js` propio (necesario para NativeWind). El motor CSS de NativeWind (`react-native-css-interop`) importa `react-native-reanimated` en tiempo de ejecución (para animaciones CSS) aunque el código de la app no la use directamente — y Reanimated 4.x a su vez exige `react-native-worklets` como paquete aparte (antes iba embebido). Conflicto de peer dependencies entre la versión de `react` fijada por el propio Expo SDK y `react-dom` (target web, que no usamos) — resuelto con `legacy-peer-deps=true` en `.npmrc` del proyecto, aceptable porque es un desfase de versiones del propio ecosistema Expo, no algo bajo nuestro control.
- `admin-app/README.md` documenta cómo arrancarlo y cómo probar el login en dev (sin SMTP configurado, el contenido del email —incluido el token— se imprime en `docker compose logs -f api`; se copia a mano mientras no exista Universal Link, ver §7bis).

**Probado de punta a punta (2026-09-09), spike cerrado:**

- Backend desplegado en dev (`docker compose up --build api`, confirmado con el usuario antes de tocar el contenedor).
- Verificado por curl contra la API real (simulando exactamente lo que manda la app: `Host` sin match + `X-Tenant-Slug: escaparate`): magic link → `/auth/mobile/magic-link/verify` (tokens en JSON), `GET /admin/orders` (datos reales), rotación de refresh, **detección de reuso confirmada en real** (reutilizar un token viejo revoca también el que lo había sustituido), `X-Tenant-Slug` inválido sigue dando 404, tráfico web normal (Host real) no se ve afectado.
- Verificado en dispositivo real vía **Expo Go** (SDK 57, misma WiFi que el Mac, `.env` con `EXPO_PUBLIC_API_URL` a la IP de LAN): login completo con slug `escaparate` + email de prueba, token pegado a mano desde los logs de dev, lista de Pedidos cargando datos reales del tenant.

Con esto, el spike de §5 punto 2 queda cerrado — el resto del MVP (TPV, Compra particular, Catálogo) puede construirse sobre esta misma base de auth sin re-validarla desde cero.

---

## 7quater. Login sin escribir el nombre de la tienda + contraseña como segunda vía (2026-09-09)

Dos cambios de diseño pedidos por el usuario tras probar el spike a mano, implementados y verificados en real (curl + `docker compose up --build api`):

### 7quater.1 — Resolución de tenant por email/token, no por texto escrito a mano

El spike inicial (§7bis/§7ter) pedía el slug de la tienda como campo de formulario antes de poder pedir el enlace — funcional, pero mala UX para algo que el servidor puede averiguar solo. Rediseñado:

- `POST /auth/mobile/magic-link` pasa a tomar **solo email** (antes reenviaba al `/auth/magic-link` compartido con web, que exige tenant ya conocido). Con `get_db_unscoped`, busca en qué tenant(s) ese email es **`admin`** (nunca donde solo tiene cuenta de cliente) y manda un magic link por cada uno — 0, 1 o varios. Respuesta siempre `202` con el mismo texto genérico sin importar cuántos matches haya (mismo criterio anti-enumeración que ya usaba `/auth/magic-link`/`/auth/resend-verification`): revelar la lista de tiendas en la respuesta HTTP permitiría a cualquiera usar esto para saber de qué tiendas es admin un email ajeno; la única forma real de verlo es teniendo acceso a esa bandeja de entrada.
- `POST /auth/mobile/magic-link/verify` ya no necesita `X-Tenant-Slug` en absoluto: `AuthToken.token_hash` es único a **nivel global** (`models/users.py`, no compuesto con tenant), así que el propio token basta para encontrar de qué tenant es — mismo patrón que ya usa `routers/checkout.py::redsys_notify` (`get_db_unscoped` + `tenancy.scoped_to`) para el mismo problema estructural (identificar el tenant antes de poder resolverlo por dominio/slug). La respuesta (`MobileTokenOut`) ahora incluye `tenant_slug` — es la primera vez que el cliente lo sabe, lo guarda para las llamadas siguientes.
- A diferencia del flujo web (`get_or_create_user`), verify **nunca crea un usuario nuevo**: solo se emitió el token porque el email ya era admin de ese tenant en el momento de pedirlo; si para cuando se canjea ya no lo es (degradado a cliente, cuenta borrada), se rechaza con 403 en vez de crear una cuenta sin permisos.
- `app/login.tsx` pierde el campo "slug de la tienda" — solo pide email.

### 7quater.2 — Corrección de CLAUDE.md + login por contraseña

Al pedir esto, salió a la luz una discrepancia real entre `CLAUDE.md` (decisión de diseño protegida #4, "Auth sin contraseñas") y el código: `web/app/[locale]/login/LoginClient.jsx` tiene login por contraseña **como pestaña por defecto**, con `/auth/register`/`/auth/login`/`/auth/set-password` completos y funcionales en el backend desde el primer commit del proyecto — no es código heredado ni sin usar. Decisión (con el usuario): el código manda, se corrige el documento (§4 de CLAUDE.md pasa a documentar las tres vías — Google, magic link, contraseña — como igual de válidas), no al revés.

Con eso resuelto, `POST /auth/mobile/login` (usuario/contraseña) se añade con el mismo espíritu que el magic link, pero con una ambigüedad que este no tiene: un mismo email+contraseña **sí** puede coincidir como admin en más de un tenant a la vez (dos cuentas propias con la misma contraseña) — un token, en cambio, nunca "coincide" en dos sitios.

- Primera llamada (sin `tenant_slug`): busca todos los `User` admin con ese email (`get_db_unscoped`), verifica la contraseña **contra el hash de cada fila individualmente** (cada tenant tiene su propio `password_hash`, aunque el email se repita) — filtra a los que de verdad coinciden.
  - 0 matches → `401` inmediato (igual que el `/auth/login` de web — no es el patrón anti-enumeración silencioso del magic link; login por contraseña síncrono ya revela "credenciales incorrectas" hoy en web, no se introduce un modelo de seguridad nuevo, se replica el existente).
  - 1 match → `MobileLoginOut.status="signed_in"`, tokens + `tenant_slug`, igual que el magic link.
  - >1 match → `status="choose_tenant"` + `tenants: [{slug, name}, ...]`, **sin tokens**. La app muestra un selector; al elegir, repite la llamada con `tenant_slug` fijado — esa segunda llamada busca directo en ese tenant, sin ambigüedad posible.
- `app/login.tsx`: pestañas "Contrasenya" (por defecto, igual que web) / "Enllaç per email"; pantalla de selección de tienda cuando `signInWithPassword()` devuelve opciones en vez de iniciar sesión directamente.
- Tests nuevos en `test_auth_mobile.py`: contraseña correcta/incorrecta, cuenta solo-magic-link sin contraseña, incidente de ambigüedad real (mismo email+contraseña en dos tenants → pide elegir → la segunda llamada sí entra), y el caso *no* ambiguo (mismo email, contraseña *distinta* por tenant → entra directo al que corresponde, sin listar el otro).
- Verificado por curl contra el backend real (`docker compose up --build api`, confirmado con el usuario): login por contraseña real devuelve `tenant_slug` correcto; contraseña incorrecta da 401.
- `pytest`: 640 passed (mismo fallo preexistente y no relacionado).

**Deliberadamente fuera de esta entrega**: `/auth/mobile/google/callback` (login con Google nativo) sigue pendiente, sin cambios respecto a lo ya documentado en §7bis.

---

## 7quinquies. Identidad visual — "Soft Pro" (2026-09-09)

Decisión pendiente desde §6.1 ("paleta, tipografía y tono visual propios... a definir aparte") cerrada con ayuda de la skill `ui-ux-pro-max` (búsqueda de design system + paletas + tipografías para el stack React Native, no improvisado). Tres direcciones evaluadas (claro tipo "hoja de cuentas", oscuro para mostrador con poca luz, y "soft UI" con profundidad tipo Stripe/Square) — elegida la tercera.

**Tokens** (`theme.tokens.js`, raíz de `admin-app/` — fuente única, `tailwind.config.js` y `lib/theme.ts` la reexportan, nunca se duplica el valor de un color en dos sitios):

| Token | Valor | Uso |
|---|---|---|
| `background` | `#F8FAFC` | fondo de pantalla |
| `foreground` | `#0F172A` | texto principal |
| `card` | `#FFFFFF` | tarjetas, inputs |
| `primary` | `#1E3A5F` | botón primario, iconografía activa |
| `accent` | `#059669` | estados positivos (pagado/enviado) |
| `warning` | `#D97706` | estados pendientes |
| `destructive` | `#DC2626` | cancelado, acciones peligrosas |
| `border` / `muted` / `mutedForeground` | `#E4E7EB` / `#F1F5F9` / `#64748B` | separadores, texto secundario |

Deliberadamente **independiente** de los otros dos temas de la plataforma (decisión explícita del usuario, ver §6.1): no hereda el MD3/sidebar-teal del admin web ni la marca cálida de la tienda online.

**Tipografía**: Fira Sans (texto) + Fira Code (cifras — `font-mono`/`font-monoSemibold` en precios, totales y el slug del tenant) vía `@expo-google-fonts/*`, cargadas con `useFonts` en `app/_layout.tsx` (pantalla de carga hasta que están listas, evita el "flash" de fuente del sistema). Números tabulares en tablas/precios es un requisito real de UX para una app que muestra dinero, no un capricho tipográfico.

**Hallazgo real de rendimiento, corregido de paso**: importar de `@expo-google-fonts/fira-sans` (el índice del paquete) hace que Metro empaquete los `.ttf` de las 9 variantes de la familia entera (~6MB), aunque `useFonts` solo declare 4 pesos — el índice reexporta todos, y Metro no hace tree-shaking de assets. Arreglado importando cada peso desde su ruta directa (`@expo-google-fonts/fira-sans/700Bold/FiraSans_700Bold.ttf`) — de 17 `.ttf` empaquetados a 7, verificado con `npx expo export --platform android` antes/después.

**Componentes base** (`components/ui/`, usados por `login.tsx`/`orders.tsx` y pensados para las 3 pantallas que faltan): `Screen` (fondo + `useSafeAreaInsets` real, nunca padding-top a ojo), `Card` (radio 16 + sombra suave nativa vía `style`, no `shadow-*` de Tailwind — RN no la traduce igual en las dos plataformas), `Button` (4 variantes, min-height 44pt, estado `loading` con spinner), `Input`/`FormField`, `StatusBadge` (mapea `status` de negocio a color semántico mediante un vocabulario cerrado, `lib/theme.ts::statusColorToken` — mismo criterio que ya usa el backend para `catalog_provider`/`product_archetype`: registro cerrado, no texto libre).

Verificado: `tsc --noEmit` limpio, `npx expo export --platform android` bundlea sin fallos tras el cambio de tokens/fuentes/componentes.

---

## 7sexies. Alcance ampliado — de 4 pantallas a "casi todo el admin" (2026-09-09)

El MVP original (§6) se queda corto: el usuario quiere llevar a la app prácticamente todo el flujo operativo diario, dejando en web solo lo denso/infrecuente/de configuración. Inventario completo hecho leyendo `web/app/admin/layout.jsx` (la navegación real, no de memoria) — 29 pantallas en 7 secciones. Alcance confirmado:

**Migra a la app** (orden de construcción, por dependencias reales, no solo prioridad):

1. **Pedidos** (Vendes web) — completo, no solo lista. Ver §7septies, ya implementado.
2. **TPV** — venta de mostrador.
3. **Compras, completo**: Resum, Sol·licituds, Comandes (con recepción por escaneo de EAN — ver hallazgo abajo), Compres particulars, Historial, Proveïdors.
4. **Catálogo, completo**: alta + edición + Discogs + imágenes (no solo edición rápida como decía §6).
5. **Peticions**.
6. **Ofertes, Cupons, Etiquetes** — para poder mantener precios/promos también desde el móvil.
7. **Dashboard** — al final a propósito: en web no tiene endpoint propio, es una pantalla que agrega llamadas a Pedidos/Peticions/Compras/TPV (`web/app/admin/page.jsx`, `authFetch` a `/admin/orders`, `/admin/peticiones`, `/admin/solicitudes-compra`, `/admin/compras/stats`, `/admin/ventas-externas`, `/admin/subscripcions*`) — construirlo antes de tener esas pantallas sería repetir trabajo dos veces.

**Se queda en web** (sin cambios respecto al razonamiento de §6): Comptabilitat completo (15 pantallas), CMS completo (5), Admin (Usuaris/Configuració), y dentro de ERP el Club del disc (gestión mensual, no de mostrador).

**Hallazgo técnico sobre el escaneo de EAN (Compras/Comandes, punto 3)**: mucho más viable de lo que parecía, verificado leyendo el código real, no asumido:
- `Release.ean` ya existe (`api/app/models/catalog.py:90`, indexado) y `GET /admin/releases` ya acepta filtrar por EAN exacto (`admin/releases.py:149`) — la búsqueda por código de barras ya funciona en el backend hoy, cero trabajo nuevo ahí.
- El único hueco: `ComandaLineaOut` (`api/app/schemas/erp_comandas.py`) no expone `ean` por línea todavía — un campo suelto que añadir cuando se construya esa pantalla, no un rediseño.
- El escaneo en sí sería `expo-camera` (lector de códigos de barras nativo, sin librería externa) en el lado de la app — la app pide el detalle de una comanda ya seleccionada, escanea, hace el match local `ean → comanda_linea_id`, y manda la recepción acumulada a `POST /erp/comandas/{id}/recepcio` (que ya existe, sin cambios).

---

## 7septies. Pedidos — completo (2026-09-09)

Primera pieza del alcance ampliado (§7sexies punto 1). Sin cambios de backend — los cuatro endpoints que hacían falta ya existían (`GET /admin/orders/{id}`, `PATCH /admin/orders/{id}/status`, `POST /admin/orders/{id}/avisar-recollida`, `POST /admin/orders/{id}/marcar-pagado-tienda`), leídos directamente de `api/app/routers/admin/orders.py` antes de tocar la app, no asumidos.

- `app/orders.tsx` → `app/orders/index.tsx` (Expo Router: hacía falta el directorio para poder añadir la ruta dinámica de detalle debajo). Cada fila navega a `app/orders/[id].tsx`.
- `app/orders/[id].tsx` (nuevo): ficha completa — cliente, artículos con condición/grading, total, envío, y acciones **contextuales según el estado real del pedido** (el cliente no reimplementa las reglas de transición, que viven en el backend — `_ESTATS_LOGISTICS`/`_ESTATS_CANCELABLES` en `orders.py`; el cliente solo muestra/oculta botones según el estado actual y deja que el backend acepte o rechace):
  - `pendiente_pago` + pago en tienda → botones "Efectiu"/"Targeta" (`marcar-pagado-tienda`).
  - `pagado`/`enviado`/`entregado` → selector de 3 botones, libre en cualquier dirección (igual que permite el backend).
  - Envío a domicilio → campos de nº de seguimiento/transportista, editables independientemente del cambio de estado (el endpoint acepta payload parcial).
  - Recogida en tienda, pagado, sin líneas pendientes de llegar → botón "Avisar recollida".
  - Estados cancelables → "Cancel·lar comanda", con `Alert.alert` de confirmación nativo antes de una acción destructiva.
- `lib/api.ts`: `fetchOrderDetail`, `updateOrderStatus`, `avisarRecollida`, `marcarPagadoTienda`.
- Verificado: `tsc --noEmit` limpio, `npx expo export --platform android` bundlea sin fallos con la nueva ruta anidada.

**Deliberadamente fuera de esta pieza**: el descuento manual de precio al cobrar en tienda (`OrderMarcarPagadoTiendaIn.price`, solo válido con un único disco en el pedido) — se añade si hace falta de verdad en el día a día, no antes.

---

## 7octies. Navegación por pestañas + TPV (2026-09-09)

Con dos pantallas ya (Pedidos, TPV) y hasta 5 previstas (§7sexies: + Compras, Catálogo, Peticions — encaja justo en el límite de 5 que recomienda un bottom nav), se introduce la estructura de navegación ahora que es barata, en vez de más adelante con más pantallas que migrar:

- `app/(tabs)/` (grupo de rutas de Expo Router, invisible en la URL): `_layout.tsx` con un `Tabs` navigator (iconos de `@expo/vector-icons/MaterialCommunityIcons`, colores de `lib/theme.ts`), `orders/` (con su propio `_layout.tsx` de `Stack` para que lista→detalle navegue con transición) y `tpv.tsx`. `app/login.tsx`/`app/index.tsx` se quedan fuera del grupo (no autenticados).
- **Hallazgo de rendimiento, mismo patrón que las fuentes (§7quinquies)**: `import { MaterialCommunityIcons } from "@expo/vector-icons"` (el índice del paquete) hace que Metro empaquete los `.ttf` de las **15** familias de iconos del paquete (~3.5MB), aunque solo se use una. Arreglado importando del subpath directo (`@expo/vector-icons/MaterialCommunityIcons`) — de 15 fuentes a 1, verificado con `expo export` antes/después.

**TPV** (`app/(tabs)/tpv.tsx`), sin cambios de backend — los tres endpoints ya existían (`GET /catalog?q=`, `GET /admin/tipus-iva?nomes_actius=true`, `POST /admin/ventas-externas/lote`), confirmado leyendo `catalog.py`/`ventas_externas.py` antes de construir, no asumido del resumen del audit inicial:

- Buscador con debounce (`lib/useDebouncedValue.ts`, genérico — lo reutilizarán Catálogo/Compras) + botón de escaneo EAN.
- `components/ui/BarcodeScanButton.tsx` (nuevo, reutilizable): modal a pantalla completa con `expo-camera` (`CameraView`+`onBarcodeScanned`, tipos `ean13`/`ean8`/`upc_a`/`upc_e`), sin librería externa. Lo reutilizará Comandas cuando se aborde Compras.
- Los resultados de `GET /catalog` son por **release**, no por item — cada release lista sus `items[]` (grading/precio/condición) individualmente pulsables, porque vender exige un `item_id` concreto, no un release.
- Carrito local: cantidad editable en `nou` (tope = `quantity - reserved_quantity`), precio editable por línea, artículo manual con selector de IVA (excluye REBU, igual que ya valida el backend). Cobro inline (sin modal): cliente opcional + 4 métodos de pago → `POST .../lote`, todo o nada.
- Pantalla de confirmación tras vender (total, método, hora) — sin recibo, tal como se acordó en el diseño.
- **Bug real encontrado y corregido de paso**: `components/ui/Input.tsx` no aceptaba `className` propio — un `{...props}` tras el `className` base lo habría *sustituido* entero en vez de combinarse (típico bug de spread en JSX), descubierto al querer un input más estrecho en la fila del carrito. Corregido combinando ambas cadenas; no afectaba a los usos anteriores (login) porque ninguno pasaba `className`.
- Verificado: `tsc --noEmit` limpio, `npx expo export --platform android` bundlea sin fallos con pestañas + cámara + iconos.

**Deliberadamente fuera de esta pieza** (igual que ya adelantaba el diseño previo): impresión de recibo, vincular usuario registrado a la venta, pestañas Reserves web/Resum/Caixa.

---

## 7novies. Compras — Comandes, primera de las 4 pantallas (2026-09-09)

Auditoría completa de las 6 pantallas de "Compres" hecha; decisión de consolidarlas en 4 en la app (Comandes, Compres particulars, Proveïdors, Sol·licituds — Compres/resum e Historial se quedan en web, ninguna de las dos gana nada siendo nativa: la primera es un dashboard sin acción propia, la segunda una consulta de escritorio ya gateada a vertical `records`). Orden de construcción: Comandes primero (mayor valor nativo real, motivó explorar el escaneo EAN), luego Compres particulars (comparte el picker de release), Proveïdors, Sol·licituds al final.

**Cambio de backend, mínimo** (`api/app/routers/erp/comandas.py`, `api/app/schemas/erp_comandas.py`): `ComandaLineaOut` gana un campo `ean` (del `Release` de la línea) — sin él la app no tiene con qué comparar un código escaneado contra las líneas pendientes de una comanda. Sin migración (no toca modelo, solo el schema de salida). Test nuevo en `test_comandas.py`. `pytest`: 640 passed (mismo fallo preexistente).

**Comandes** (`app/(tabs)/compras/`), tres pantallas:

- `index.tsx` — lista con filtro Actives/Rebudes/Cancel·lades, aviso de unidades pendientes por comanda.
- `nova.tsx` — proveedor (chips), notas, líneas añadidas vía `ReleasePicker` (ver abajo) con cantidad/precio estimado editables → `POST /admin/comandas`.
- `[id].tsx` — detalle con acciones según estado (`marcar-enviada`, `cancelar`, igual que Pedidos: el backend manda, la app solo muestra/oculta) y el **modo de recepción**: al pulsar "Rebre mercaderia", la pantalla cambia a una vista de captura — escanear con `BarcodeScanButton` busca el EAN entre las líneas pendientes cargadas y suma 1 a la cantidad a recibir de la que coincida (con aviso breve si no hay match), con steppers manuales de refuerzo y selector nou/2a mà (+ grading si aplica) por línea; todo se acumula en cliente y se manda de una vez con `POST /admin/comandas/{id}/recepcio` — mismo patrón "acumular, un solo POST" que ya usa el carrito del TPV.

**`components/ReleasePicker.tsx`** (nuevo, reutilizable — lo usará también Compres particulars y, más adelante, Catálogo): modal de búsqueda (reutiliza `searchCatalog`, el mismo que TPV) + `BarcodeScanButton` + alta manual si no se encuentra (`POST /admin/releases`, solo `title` obligatorio — CLAUDE.md: el alta siempre debe permitir meter datos a mano). Deliberadamente **sin** integración de Discogs en esta pieza — se deja para cuando se aborde Catálogo, donde es más central; aquí la búsqueda local + alta manual basta.

**Verificado de punta a punta contra el backend real** (`docker compose up --build api`, confirmado con el usuario): proveedor → release con EAN → comanda → marcar enviada → recepción parcial (2 de 3 unidades) por `comanda_linea_id` → estado `rebuda_parcial` correcto. `tsc --noEmit` limpio, `npx expo export --platform android` bundlea sin fallos.

**Deliberadamente fuera de esta pieza**: PDF de comanda, envío por email al proveedor, edición de una comanda ya creada (solo se puede eliminar en `esborrany`, igual que en web).

---

## 7decies. Compras — Discogs + Sol·licituds completo (2026-09-09)

El usuario pidió expresamente completar el módulo (no la versión recortada que se había propuesto) — sin backend nuevo, todo lo que hacía falta ya existía, solo estaba sin auditar a fondo.

**Discogs, en `ReleasePicker.tsx`**: pasa de 2 a 3 pestañas (Catàleg / Discogs / Manual). `GET /admin/discogs/search` (ligero, sin tracklist) + `GET /admin/discogs/release/{id}` (ficha completa, se pide justo antes de crear) + `GET /admin/releases/check-duplicate` (evita duplicar el catálogo) + `POST /admin/releases` — se porta la función `resolveOrCreateRelease` de `web/app/lib/discogs.js` tal cual a `lib/api.ts::resolveOrCreateDiscogsRelease`, sin reinventar la lógica. El rate limit de Discogs (~60/min) lo throttla el propio backend (`services/discogs.py`) — la app nunca pega directo, sigue sin ser su problema. La pestaña Discogs se oculta sola si `GET /config/public` dice `discogs_habilitat: false` — verificado contra el tenant real `escaparate`, que lo tiene desactivado.

**Sol·licituds completo** (no solo lectura, la recomendación inicial de esta sesión estaba equivocada — se replanteó desde cero auditando el código real): 4 pantallas en `app/(tabs)/compras/solicituds/`:

- `index.tsx` — lista de `SolicitudCompra` (entidad consolidada, numerada) con filtro por estado.
- `pool.tsx` — línies SIN consolidar (`solicitud_id IS NULL`): selección múltiple + sugerencias de reposición (`GET .../refill-sugerencias`, lectura, botón "Afegir al pool" por sugerencia) + alta manual vía `ReleasePicker` (con Discogs ya integrado) + "Crear sol·licitud" (`POST .../generar`, consolida las líneas marcadas).
- `[id].tsx` — detalle de una solicitud consolidada: por línea, "Resoldre des d'estoc" (abre un picker de `Item`s disponibles de ese release vía `GET /catalog/releases/{id}`, llama a `POST .../lineas/{id}/resoldre-estoc` — si la línea viene de una `PeticionCliente`, el backend ya reserva el ejemplar y avisa al cliente, la app no hace nada especial ahí) y modo inline "Resoldre a comanda" (mismo patrón que Comandes/receiving: proveedor + líneas con cantidad/precio editables, `ReleasePicker` inline para las que aún no tienen `release_id` — el backend exige que todas lo tengan antes de `POST .../resolver`) → navega directo a `compras/{id}`, la pantalla de Comanda que ya existía.
- Regla real de negocio verificada leyendo el código, no asumida: una línea del **pool** (sin consolidar) NO se puede resolver directamente a comanda — primero hay que generar la sol·licitud. La app respeta esto en el flujo (resolver solo vive en el detalle de una sol·licitud ya consolidada), no lo re-valida por su cuenta.

**Verificado de punta a punta contra el backend real**: pool (alta manual) → generar sol·licitud (`SOL-2026-000001`) → resolver a comanda (`2026-000002`) → sol·licitud pasa a `resolta` automáticamente. `refill-sugerencias` da 200 (lista vacía, sin histórico de ventas en dev). Discogs no se ha podido probar en vivo (`escaparate` no tiene token configurado) — el contrato se verificó leyendo el código, no probando contra la API real de Discogs. `tsc --noEmit` limpio, bundle Android sin fallos.

**Deliberadamente fuera de esta pieza**: edición de una línea ya consolidada (`DELETE .../lineas/{linea_id}` existe pero no se ha portado — quitar una línea de una comanda ya creada es un caso raro, se hace desde web si hace falta).

---

## 7undecies. Historial de compres — el alta real, no solo consulta (2026-09-09)

El usuario pidió expresamente ampliar el módulo más allá de lo ya construido: alta al pool con cantidad/proveedor (hueco real detectado — el `pool.tsx` de §7decies añadía siempre cantidad=1 sin proveedor), histórico de compras, solicitudes de cliente y selección múltiple en sugerencias de reposición. Esta pieza cierra los dos primeros puntos a la vez: auditando la web se descubrió que Historial **es** el sitio donde vive de verdad el alta manual con proveedor+cantidad (`afegirAlPool` en `web/app/admin/compras/historial/page.jsx`), no una pantalla de solo consulta separada del alta.

`app/(tabs)/compras/historial.tsx`: buscador (mismo debounce de siempre) → `GET /admin/historial-compres/resum` lista proveedores agrupados (combina un histórico congelado de CSV antiguo + las `Comanda` reales ya hechas, para que el buscador "aprenda" con el tiempo) → al expandir uno, `GET /admin/historial-compres?proveedor_id=` trae sus líneas → selección múltiple (mismo patrón ya usado en `solicituds/pool.tsx`) → "Afegir N al pool" con `proveedor_sugerido_id` ya puesto, cantidad editable por línea → mismo `addToPool` de siempre, ahora con el hueco de §7decies cerrado.

Gateado a vertical `records` en el propio backend (devuelve `[]`, nunca error) — la app comprueba `GET /config/public.vertical` y muestra un mensaje honesto ("solo disponible para discos") en vez de una lista vacía sin explicación, para las tiendas de otro vertical.

**`components/ComprasSubNav.tsx`** (nuevo): la fila de navegación Comandes/Sol·licituds/Historial se repetía a mano en cada pantalla — extraída antes de que creciera más (Particulars/Proveïdors siguientes).

**Verificado contra el backend real**: `historial-compres/resum` ya refleja la comanda de prueba creada en §7novies (proveedor DistroTest, 1 línea) sin ningún dato sembrado a propósito — confirma que "aprende" de las comandas reales tal como dice el docstring del backend. `tsc --noEmit` limpio, bundle Android sin fallos.

**Pendiente de esta ampliación, siguiente en la lista**: solicitudes de cliente (`PeticionCliente`, la pieza grande — adelanta el punto 5 del plan original de §7sexies porque está genuinamente acoplada a Sol·licituds) y selección múltiple en sugerencias de reposición (ajuste rápido sobre `pool.tsx`).

---

## 7duodecies. Peticions de client (2026-09-09)

Pieza más grande de la ampliación pedida por el usuario — adelanta el punto 5 del plan original (§7sexies), justificado porque está genuinamente acoplada a Sol·licituds, no es una pantalla aparte. Ciclo completo de `PeticionCliente` verificado leyendo `api/app/routers/erp/peticiones.py` antes de construir, no asumido del audit inicial: crear (con o sin disco catalogado) → catalogar si hacía falta → fijar precio → vincular a sol·licitud (entra en el pool con `origen=peticion_cliente`, que `pool.tsx` ya reconocía desde antes de existir esta pieza) → de ahí sigue el pipeline de Sol·licituds ya construido.

**Detalle importante encontrado leyendo el código**: con `channel="tienda"` (el único que crea la app — un cliente en el mostrador o al teléfono, no una petición web), fijar el precio salta directamente a `acceptada` sin esperar confirmación del cliente por email — el cliente ya lo aceptó de palabra. La app respeta esto: no hay paso de "esperar aceptación" en su flujo.

`app/(tabs)/compras/peticions/`, tres pantallas:

- `index.tsx` — lista con filtro Actives/Totes.
- `nova.tsx` — buscar cliente existente (`GET /admin/users/search`) o crear uno nuevo (`POST /admin/users`, solo email obligatorio) + disco vía `ReleasePicker` o texto libre ("no sé quin disc és exactament", `free_artist`/`free_title`) → `POST /admin/peticiones/tienda`.
- `[id].tsx` — acciones contextuales por estado: catalogar (si no tenía disco), fijar precio (si `pendent` con disco ya catalogado), vincular a sol·licitud con cantidad + proveedor sugerido opcional (si `acceptada`), cancelar (en cualquier estado activo).

**No hay `GET /peticiones/{id}`** en el backend (solo lista completa) — `lib/api.ts::fetchPeticionDetail` cae a buscar en `GET /admin/peticiones` si falla la ruta directa, documentado en el propio código para no parecer un despiste.

**Deliberadamente fuera de esta pieza**: `POST /peticiones/{id}/vincular-item` (vincular un ejemplar directamente sin pasar por una línea de sol·licitud) — el camino ya construido (vincular-solicitud → pool → resoldre-estoc, que ya reserva y avisa al cliente si la línea viene de una petición) cubre el mismo caso de uso sin necesitar una segunda vía.

**Verificado de punta a punta contra el backend real**: cliente nuevo → petición sobre un disco CON stock (rechazada correctamente: "ja té estoc disponible, es pot vendre directament" — confirma que el backend protege este caso) → petición sobre un disco sin stock → precio fijado (pasa a `acceptada` directo) → vinculada a sol·licitud → aparece en el pool marcada `peticion_cliente`. `tsc --noEmit` limpio, bundle Android sin fallos.

**Queda de la ampliación pedida**: selección múltiple en sugerencias de reposición (`pool.tsx`) — el único punto que faltaba.

---

## 7. Preguntas abiertas antes de escribir código

1. ¿Confirmas el orden de §5 (Admin primero, Tienda/Comunidad como piloto después)?
2. ~~§3.2 — mecanismo de entrega del refresh token a nativo~~ — **resuelto** (2026-09-09): endpoints `/auth/mobile/*` dedicados, ver §3.2.
3. §3.3 — ¿modelamos `tenant_apps` ya, o lo aparcamos hasta el piloto del punto 3 de §5 (gestión manual mientras tanto)?
4. ¿Arrancamos por un spike técnico (Expo app mínima contra la API real de un tenant, sin tocar el backend salvo lo estrictamente necesario para probar) antes de comprometernos al plan completo, o directamente con la Fase 1 (App de Admin) en firme?
