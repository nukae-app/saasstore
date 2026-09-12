# Mejoras al módulo de Comptabilitat [ARCHIVADO]

**Este documento está archivado — su lista de "Pendiente" quedó obsoleta.**
Los puntos 3, 4 y 5 de abajo (punteado, flujo de caja proyectado, cierre de
ejercicio) se construyeron en sesiones posteriores y ya están en producción
(commit `2ab1863`, "Millora el mòdul de Comptabilitat: punteig, marges, flux
de caixa i tancament d'exercici"). El seguimiento de lo que falta en
contabilidad ahora vive en `docs/PLAN_COMPTABILITAT.md`, escrito el
2026-09-12 tras verificar el código real (no fiarse de este documento).

Se conserva el resto de este archivo como registro histórico de la sesión
original (2026-09-04) — los "Hallazgos de la investigación" de abajo siguen
siendo ciertos y no hace falta repetirlos.

## Estado actual (qué está hecho en esta sesión)

- **Albarans se generan automáticamente al marcar un pedido como "enviado"**
  (antes había que ir a `/admin/albarans` y elegirlo a mano de un
  desplegable, desconectado del flujo real). Ver `services/albarans.py`
  (`crear_albara_per_order`, idempotente), hook en
  `routers/admin/orders.py::update_order_status`. El detalle del pedido en
  `/admin/vendes-web` muestra "Descargar albarán" en cuanto existe uno.
  Desplegado a prod (commit `d2c2e59`).

## Hallazgos de la investigación (para no repetir el análisis)

Antes de proponer nada se verificó el código real de los tres puntos que
planteó el usuario — dos de ellos resultaron ser malentendidos de la UI, no
bugs:

1. **Pla de comptes SÍ está vinculado automáticamente.** Cada venta (web y
   TPV) y cada gasto se contabiliza solo, vía `services/comptabilitat_posting.py`
   (`post_venda`, `post_despesa_alta`, `post_despesa_pagament`,
   `post_actiu_alta`, `post_amortitzacio`, `post_caixa_diaria`) — llamado
   desde `services/orders.py` (checkout web) y `routers/erp/ventas_externas.py`
   (TPV/venta externa). Las cuentas se siembran automáticamente por
   jurisdicción/forma legal (`services/comptabilitat_seed.py`) y **no son
   editables a mano a propósito** — así el plan de cuentas no se desvía del
   estándar. Confirmado: no hay ningún endpoint POST/PATCH/DELETE sobre
   `AccountingAccount`, solo `GET /admin/comptes-comptables`.
2. **La sensación de "vacío" es real, pero el arreglo es barato.** La
   pantalla `/admin/pla-comptes` (98 líneas) es una lista plana sin ningún
   enlace a los movimientos de cada cuenta. Pero **el backend YA tiene** el
   libro mayor por cuenta: `GET /admin/llibre-major/{year}?compte={codigo}`
   (`routers/comptabilitat/llibres.py::llibre_major`), consumido ya por la
   pestaña "Major" de `/admin/llibres` (`MajorTab`, que hoy solo permite
   elegir la cuenta de un desplegable, seleccionando la primera por
   defecto). **No hace falta modelo ni endpoint nuevo** — solo:
   - Que `/admin/llibres` lea un query param `?compte=X&tab=major` para
     preseleccionar la cuenta al entrar (`MajorTab` ya tiene el `useState`
     de `compte`, solo falta inicializarlo desde la URL).
   - Que cada fila de `/admin/pla-comptes` enlace a
     `/admin/llibres?tab=major&compte={code}&year={añoActual}`.
3. **Márgenes (`MargeConfig`) vive en Configuración, no en Comptabilitat.**
   Confirmado: `web/app/admin/configuracio` es donde está la pantalla hoy,
   mezclado con tramos de envío y formatos de peso. El modelo
   (`api/app/models/configuracio.py::MargeConfig`) y el router
   (`api/app/routers/configuracio.py`) no tienen ninguna dependencia de
   contabilidad — mover es solo cuestión de mover la pantalla/entrada de
   menú a la sección Comptabilitat del admin (`web/app/admin/layout.jsx`),
   sin tocar backend.

## Pendiente, por prioridad (coste creciente) [ESTADO A 2026-09-12]

1. **Pla de comptes: enlazar cada cuenta a su libro mayor.** Cambio de
   frontend puro (ver hallazgo 2 arriba). El más barato de los tres puntos
   originales del usuario, y probablemente el que más resuelve la
   sensación de "esto está muerto". *Sin verificar si se llegó a hacer —
   revisar `/admin/pla-comptes` antes de repetir el análisis.*
2. **Mover Márgenes de Configuración a Comptabilitat.** Cambio de
   frontend puro (ver hallazgo 3): mover la pantalla/entrada de menú, sin
   tocar modelo ni endpoints. *Sin verificar — revisar `web/app/admin/configuracio`
   y `web/app/admin/marges` antes de repetir el análisis.*
3. ~~**Punteado de asientos**~~ **HECHO.** `JournalLine.punteat` +
   checkbox en `/admin/llibres` (pestaña Major).
4. ~~**Flujo de caja proyectado**~~ **HECHO.** `GET /admin/flux-caixa-projectat`,
   ver `routers/comptabilitat/flux_caixa.py`.
5. ~~**Cierre de ejercicio formal**~~ **HECHO.** `POST /admin/periodes/{year}/tancar-exercici`,
   ver `routers/comptabilitat/tancament.py`.

Para lo que sigue realmente pendiente en contabilidad (exportación de
modelos AEAT, Modelo 347, VeriFactu), ver `docs/PLAN_COMPTABILITAT.md`.

## Prompts para continuar

Pega el que toque (o, con Claude Code, descríbelo: ya tiene este archivo
como contexto).

### Prompt — Pla de comptes: enlazar al libro mayor

```
Lee docs/MEJORAS_COMPTABILITAT.md, punto 1 de "Pendiente". Quiero que cada
fila de /admin/pla-comptes enlace directamente a su libro mayor en
/admin/llibres (pestaña "Major"). No hace falta backend nuevo — el
endpoint GET /admin/llibre-major/{year}?compte=X ya existe. Haz que
/admin/llibres lea compte y tab de la URL para preseleccionarlos al entrar.
Pruébalo en vivo en el navegador antes de darlo por bueno.
```

### Prompt — Mover Márgenes a Comptabilitat

```
Lee docs/MEJORAS_COMPTABILITAT.md, punto 2 de "Pendiente". Mueve la
pantalla de Márgenes (hoy en Configuración) a la sección Comptabilitat del
menú admin. Es un cambio de frontend puro (ruta + entrada de menú), no
toques el backend. Pruébalo en vivo antes de darlo por bueno.
```

(Los prompts de punteado, flujo de caja proyectado y cierre de ejercicio se
retiraron de aquí: esos tres bloques ya están construidos — ver arriba.
Para lo que sigue pendiente en contabilidad, usa los prompts de
`docs/PLAN_COMPTABILITAT.md`.)
