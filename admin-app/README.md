# admin-app

App nativa de administración (Expo + TypeScript + Expo Router + NativeWind).
Diseño y decisiones: `../docs/ARQUITECTURA_APPS_NATIVAS.md` (ver §7quater
para el login).

Este es el **spike de auth** (§5 del documento): login por contraseña o
por magic link contra la API real (sin escribir el nombre de la tienda —
se resuelve solo, por email/token), sesión persistida en el dispositivo,
y una lista de Pedidos autenticada. Todavía no las otras 3 pantallas del
MVP (TPV, Compra particular, Catálogo).

## Arrancar

Con el backend corriendo (`docker compose up --build` en la raíz del repo):

```
npm install
npm run android   # o: npm start, y pulsar "a"
```

Por defecto la app apunta a `http://10.0.2.2:8080/api` (alias fijo del
emulador de Android hacia `localhost` de la máquina host — así llega al
mismo docker compose que usa `web/`). Para un dispositivo físico en la
misma red, copia `.env.example` a `.env` y pon la IP de LAN de tu máquina.

## Probar el login

En la pantalla de login solo hace falta el **email** — nunca el nombre de
la tienda, la API lo averigua sola:

- **Contrasenya** (pestaña por defecto, igual que la web): si el usuario
  ya tiene contraseña puesta (vía `/auth/register` o `/auth/set-password`
  en web), entra directo. Si el mismo email+contraseña es admin en más de
  una tienda a la vez, la app te pregunta cuál antes de entrar.
- **Enllaç per email**: en dev no hay SMTP configurado, así que el email
  no llega a ningún lado real — el contenido se imprime en los logs del
  contenedor `api` (`docker compose logs -f api`). Busca la línea con
  `token=` y pégalo en el segundo campo. Si el email es admin en más de
  una tienda, llegan varios emails (uno por tienda) en vez de un selector.

## Qué reutiliza del backend

Todo en `api/app/routers/auth_mobile.py` — endpoints dedicados a nativo,
en paralelo a `/auth/*` (web), nunca una rama condicional sobre los
mismos (ver por qué en el docstring del propio archivo):

- `POST /auth/mobile/magic-link` / `/magic-link/verify` — solo piden
  email/token, sin `X-Tenant-Slug`: el tenant se resuelve buscando en qué
  tienda(s) es admin ese email, o por el propio token (único a nivel
  global).
- `POST /auth/mobile/login` — usuario/contraseña, misma idea, con
  desambiguación de tienda si hace falta (`status: "choose_tenant"`).
- `POST /auth/mobile/refresh`, `/auth/mobile/logout` — estos sí necesitan
  `X-Tenant-Slug` (`lib/api.ts`), pero ya lo tiene la app sola (se lo dio
  el servidor en el login, no lo escribe el usuario).
- `GET /admin/orders`.

## Pendiente (fuera de este spike, a propósito)

- Login con Google nativo (`expo-auth-session`, PKCE).
- Universal Links para que el magic link abra la app directamente (hoy se
  copia el token a mano) — depende de tener bundle id/dominio asociado.
- Las otras 3 pantallas del MVP y la identidad visual propia (pendiente,
  no se hereda del admin web ni de ninguna tienda).
