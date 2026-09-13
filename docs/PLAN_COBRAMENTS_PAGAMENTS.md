# Plan de Cobraments i Pagaments — lligar tot el flux contra Comptabilitat

Documento de trabajo nacido de una sesión (2026-09-12) en la que se investigó
cómo ligar el flujo completo de cobros (web, TPV, Club del disc) y pagos
(proveedores) contra Comptabilitat, partiendo de la conciliación bancaria ya
existente (ver `docs/PLAN_COMPTABILITAT.md`). Mismo protocolo del proyecto:
**proponer → discutir → aprobar → migrar → tests → desplegar con
confirmación.** Nada de lo que hay aquí está migrado ni codeado todavía.

## Estado verificado antes de proponer nada

- **Redsys ya está integrado a fondo, por tenant** (`services/redsys.py`,
  `tenant_secrets.py`): checkout web (`routers/checkout.py`) y cobro
  recurrente del Club del disc vía COF/MIT (`CobramentSubscripcio`). Esto
  corrige `CLAUDE.md`, que da la pasarela de pago como pendiente — no lo
  está, solo con Redsys (no Stripe).
- **El pago con Redsys abre el 430 (`post_venda`) pero nunca lo cierra
  solo** — el propio código lo dice en un comentario de
  `services/orders.py`: *"es cobra de veritat... quan es concilia el
  moviment bancari... o el PSP ho confirma"* — la segunda parte está descrita
  pero no implementada.
- **Las cuotas del Club del disc no generan NINGÚN asiento contable** — ni
  `post_venda` ni nada de `comptabilitat_posting` se llama desde ese flujo.
  Es el agujero más urgente de los encontrados.
- **El TPV de mostrador no tiene datáfono integrado**: `payment_method=tarjeta`
  en `VentaExterna` es una anotación manual del admin, sin webhook de ningún
  banco. No hay señal en tiempo real para ese canal — sigue dependiendo de
  caja diaria / conciliación bancaria, como hoy.
- **Sin abstracción multi-PSP**: `Payment.provider` es un `string` que
  siempre vale `"redsys"`; toda la lógica de firma/webhook está escrita
  directamente contra Redsys. Sin un segundo proveedor real (confirmado con
  el usuario: no hay caso concreto todavía), no se construye una interfaz
  genérica a ciegas — solo se evita acoplar lo nuevo más de lo necesario
  a "redsys" en concreto (indexar por tenant+canal, no por proveedor).
- **No existe ninguna cuenta 626 "Serveis bancaris i similars"** en el plan
  de cuentas sembrado (`comptabilitat_seed.py`) — hace falta para modelar
  comisiones de tarjeta.
- **Datos ya disponibles para remesas de pago a proveedores**:
  `Proveedor.supplier_iban`/`payment_method`/`payment_days`/`payment_day_of_month`,
  `Despesa.due_date`/`total`/`payment_status`, `CompteBancari.iban`,
  `ConfiguracioBotiga.fiscal_name`/`nif`. Falta solo el generador de fichero.

## Decisión tomada: integración bancaria — solo N43/CSV manual

Se investigó a fondo la agregación bancaria automática (PSD2) para
sustituir la subida manual de extracto. **Conclusión: inviable por ahora,
se descarta** (no solo por coste — hay una barrera regulatoria de fondo):

- El "gratis" histórico (GoCardless Bank Account Data, antes Nordigen) **cerró
  altas nuevas en julio de 2025**. El resto de agregadores serios (Tink,
  Plaid, TrueLayer, Salt Edge) son precio a medida, con un suelo realista de
  150-500 GBP/mes en producción — muy por encima del presupuesto de la
  plataforma.
- **Conectar directamente al HUB PSD2 de Redsys (o al de cualquier banco) no
  es una alternativa barata**: requiere que la propia empresa esté
  **autorizada como AISP ante Banco de España** — Reglamento Delegado (UE)
  2018/389, art. 34: el certificado eIDAS (QWAC/QSealC) con el que te
  identificas ante el banco lleva incrustado tu número de autorización
  oficial; sin autorización no hay certificado, y sin certificado el banco
  rechaza la conexión a nivel de protocolo. La autorización exige registro
  ante Banco de España, seguro de responsabilidad civil profesional
  (importe según fórmula de directrices EBA) e idoneidad de administradores
  — un proceso de entidad financiera supervisada, desproporcionado para
  este negocio. Esto es justo lo que venden agregadores como
  Enable Banking/Tink: alquilar su licencia ya obtenida.
- **Decisión**: se mantiene el import manual de extracto (N43/CSV,
  `/admin/banc`) como única vía de entrada de movimientos bancarios. Ya
  cumple el objetivo real ("tener los movimientos en la app para conciliar
  ventas y pagos") — no falta nada ahí. Si en el futuro compensara
  automatizarlo, revisar de nuevo Enable Banking/`open-banking.io` (verificar
  precio real, no de memoria) — no reabrir la vía directa a Redsys/bancos.
- Mejora barata pendiente, sin PSD2 de por medio: aviso en `/admin/banc` si
  no se ha importado ningún extracto en X días, para que la conciliación no
  se quede atrasada por olvido.

## Diseño propuesto para lo que sí se construye

**Puntos 1-3 implementados (2026-09-12)**: cuenta 626, `ComissioPagament`
(modelo + CRUD en `/admin/comissions-pagament`), `calcula_comissio` +
`post_cobrament_conciliacio`/`post_caixa_diaria` con el reparto 572/626, el
cierre automático en `redsys_notify`, y la exclusión de los pedidos Redsys
de `get_vendes_reals`. Migración `c4adc39ce147`. Tests en
`test_comptabilitat_posting.py` y `test_tienda.py`. Pendiente: desplegar
contra dev con confirmación, y el punto 4 (Club del disc).

### 1. Nueva cuenta 626 "Serveis bancaris i similars"

Añadir a `seed_pgc_es()` para tenants nuevos + **migración de datos que la
inserte en los tenants ya existentes** (primera migración de este tipo en
el proyecto — insertar solo si no existe ya, por tenant).

### 2. Modelo de comisión de tarjeta, configurable por canal y por tenant

Tabla nueva, p. ej. `ComissioPagament`: `canal` (`web_targeta`,
`mostrador_targeta`, `club_targeta`...), `mode` (`deduccio` |
`cobrament_apart`), `pct`, `fixed_fee`. Soporta los dos modelos de
liquidación bancaria a la vez, cada canal con el suyo:

- **`deduccio` (neto)**: al cerrar el 430, se parte en tres líneas en vez de
  dos:
  ```
  572 (Bancs)            total − comisión
  626 (Serveis bancaris)  comisión
      430 (Clients)                 total
  ```
- **`cobrament_apart` (bruto + factura aparte)**: el cierre no cambia
  (572=total/430=total); la comisión se registra como una `Despesa`
  periódica normal, categoría nueva "comissions_bancàries" → 626. Encaja
  directo con el motor de `ReglaConciliacio` que ya existe (concepto fijo
  tipo "COMISIONES REDSYS" en el extracto → conciliación automática, sin
  construir nada nuevo ahí).

### 3. Cierre automático del 430 al confirmar Redsys (solo canal web)

En `redsys_notify`, al autorizar el pago, cerrar el 430 recién abierto
aplicando el modo de comisión configurado para `web_targeta` — mismo
`source_type`/`source_id` que hoy para poder desligarlo (`unpost_source`)
si hay un reembolso.

**Dependencia obligatoria a resolver a la vez**: `caixa_diaria.py::get_vendes_reals`
agrega hoy los pedidos `payment_method=redsys` en la columna "tarjeta" de
la caja diaria, asumiendo que su 430 sigue abierto. Si se cierra
automático, esos pedidos **tienen que salir de esa agregación** — si no,
riesgo de cerrar el mismo 430 dos veces. El TPV de mostrador (sin señal
real) se queda dependiendo de caja diaria, tal cual hoy.

### 4. Contabilizar el Club del disc — CORREGIDO Y RESUELTO (2026-09-12)

**El diagnóstico original de este documento era incorrecto.** El Club del
disc SÍ contabilizaba la venta ya: `confirmar_cobrament`
(`services/subscripcions.py`) crea un `Order`/`OrderItem` real con IVA
correcto por artículo y llama a `finalize_payment` — el mismo
`post_venda` (700, no 705) que cualquier venta web. El grep original solo
buscó `post_venda` por su nombre y no vio que se llega ahí vía
`finalize_payment`. **No se ha añadido IVA a `CobramentSubscripcio` ni un
`JournalSourceType` nuevo — no hacían falta.**

Lo que sí eran gaps reales, todos arreglados:

1. **El cron de facturación mensual no estaba activado**
   (`facturar-subscripcions-pendents` ausente de `celery_app.py::beat_schedule`,
   pese a que `tasks/subscripcions.py` ya era multi-tenant-correcto desde
   hace tiempo — comentario obsoleto). Reactivado, diario a las 6:00.
2. **El webhook de alta (`subscripcions_public.py::redsys_notify_alta`)
   verificaba la firma con la clave global** en vez de la del tenant, y
   usaba `get_db` en vez de `get_db_unscoped` — mismo arreglo de 3 pasos
   que ya tenía `checkout.py::redsys_notify` (extraer `Ds_Order` sin
   verificar → buscar `CobramentSubscripcio` sin scope → resolver tenant →
   verificar con SU clave).
3. **Regresión propia detectada a tiempo**: al excluir antes los pedidos
   `payment_method=redsys` de `get_vendes_reals` (punto 3), los pedidos de
   fulfillment del Club (que también llevan `payment_method="redsys"`)
   se quedaron sin ninguna vía de cierre — antes al menos los sugería mal
   caja diaria. Arreglado añadiendo el mismo cierre automático (con
   comisión `club_targeta`) al final de `confirmar_cobrament`, justo
   después de `finalize_payment` — el cobro Redsys ya estaba autorizado de
   antes (posiblemente días), así que no hay nada que esperar.

**Explícitamente descartado por decisión del usuario**: modelar el cobro
anticipado (cuenta 438) para el hueco entre "se cobra la tarjeta" y "se
confirma el envío" — hoy ese dinero no genera ningún apunte mientras tanto.
Es una decisión de modelo nueva, más grande, para otra sesión si hace falta.

**Implementado (2026-09-13)**: modelos (`RemesaPagament`/`RemesaPagamentLinia`,
`en_remesa`, `CompteBancari.bic`, `MovimentBancari.remesa_pagament_id`),
generador `services/sepa_pain001.py` (con transliteración al charset SEPA),
endpoints en `routers/comptabilitat/remeses_pagament.py` (elegibles, generar,
listar, detalle, descargar XML, anular), y la extensión de
`conciliar_moviment` para cerrar toda una remesa de golpe. Migración
`8e3e6b825f8c`. Tests en `test_sepa_pain001.py` y `test_remeses_pagament.py`.
Pendiente: desplegar con confirmación.

## Remesas de pago a proveedores (SEPA pain.001) — diseño acordado 2026-09-12

No confundir con el B6 de `PLAN_PARIDAD_HOLDED.md` (domiciliaciones
pain.008, para COBRAR cuotas) — esto es pain.001.001.03, transferencia, para
PAGAR a proveedores.

**Límite de alcance explícito**: esto genera el fichero, nunca lo envía al
banco. Iniciar el pago automáticamente sería un servicio PISP (Payment
Initiation Service Provider) — misma pared regulatoria que el AISP
descartado arriba (certificado eIDAS + autorización de Banco de España),
pero para mover dinero en vez de solo leerlo. El admin siempre descarga el
XML y lo sube él mismo al portal de su banco.

### Modelo

**`RemesaPagament`**: `compte_bancari_id` (cuenta propia emisora),
`fiscal_year`/`number` (numeración atómica vía `DocumentCounter`, mismo
criterio que `Factura`/`Pressupost`/`Albara` — decisión del usuario, aunque
no sea un documento fiscal, por consistencia), `data_execucio_solicitada`,
`status` (`generada` | `anullada`), totales denormalizados, y **el XML
generado guardado tal cual** (inmutable una vez creada — para corregir algo
se anula esta remesa y se genera una nueva, igual que una `Factura`).

**`RemesaPagamentLinia`**: `despesa_id`, `import` (snapshot — **el NETO,
`Despesa.total - Despesa.retencio_import`**, el mismo criterio que ya usa
`rank_despesa_candidates`: lo que de verdad sale hacia el proveedor si hay
retención de IRPF practicada, no el total de la factura), `end_to_end_id`
(identificador de la transacción SEPA, para poder casar la respuesta del
banco línea a línea si el banco la da así).

**Nuevo estado en `Despesa.payment_status`**: `en_remesa`, entre `pendent`
y `pagat` — evita que una despesa ya incluida en una remesa enviada se
cuele en otra remesa nueva mientras se espera al banco.

### Conciliación — soporta los dos modelos de liquidación a la vez

Confirmado con el usuario: no se puede asumir cuál usa cada banco, así que
se soportan ambos sin elegir uno:

- **Banco que liquida línea a línea** (un movimiento por proveedor pagado):
  cero cambios — la conciliación de hoy (`conciliar_moviment`, 1
  `MovimentBancari` ↔ 1 `Despesa`) ya lo resuelve, cada línea concilia
  normal y dispara `post_despesa_pagament` como cualquier pago suelto.
- **Banco que liquida en bloque** (un único cargo por el total de la
  remesa): `MovimentBancari` gana un campo opcional más de conciliación,
  `remesa_pagament_id` (junto a los ya existentes `despesa_id`/`order_id`/
  `venta_externa_id` — "un sol d'aquests quan conciliat" sigue aplicando,
  ahora con una cuarta opción exclusiva). Al conciliar contra una remesa,
  se recorren todas sus `RemesaPagamentLinia` con `Despesa` no pagada
  todavía y se llama `post_despesa_pagament` una vez por cada una (varias
  líneas de asiento por un solo movimiento bancario — no hay problema en
  eso, ya pasa hoy que un movimiento puede acabar generando varias cosas).

### Flujo

1. Admin filtra `Despesa` con `payment_status` `pendent`/`vencut` y
   `payment_method=transferencia` con `Proveedor.supplier_iban` informado
   (sin IBAN no puede ir en una remesa SEPA).
2. Selecciona cuáles incluir, la `CompteBancari` emisora y la fecha de
   ejecución solicitada.
3. Se genera `RemesaPagament` + líneas (importe neto), se numeran los
   `end_to_end_id`, se construye el XML pain.001.001.03 (cabecera con
   `ConfiguracioBotiga.fiscal_name`/`nif` como `InitgPty`/`Dbtr`,
   `CompteBancari.iban` como `DbtrAcct` — el BIC ya no es obligatorio para
   transferencias SEPA en la UE desde 2016, solo IBAN), y cada `Despesa`
   incluida pasa a `en_remesa`.
4. Admin descarga el XML y lo sube al portal de su banco (fuera de este
   sistema).
5. El cierre real (cuándo se marca `pagat` de verdad) pasa por la
   conciliación bancaria de siempre cuando el banco ejecuta el pago — no se
   inventa un botón de "confirmar remesa" aparte: es el mismo mecanismo que
   ya existe para cualquier pago, con la única adición del punto anterior
   (conciliar contra una remesa entera cuando el banco liquida en bloque).

## Prompts para continuar

### Prompt — Comisiones bancarias + cierre automático Redsys

```
Lee docs/PLAN_COBRAMENTS_PAGAMENTS.md, puntos 1-3 de "Diseño propuesto".
Quiero modelar la cuenta 626, la tabla de comisión configurable por canal
(deducció/cobrament_apart) y el cierre automático del 430 al confirmar
Redsys en el checkout web — incluyendo sacar esos pedidos de
get_vendes_reals para no cerrar el 430 dos veces. Propón el modelo/migración
exactos y discútelo conmigo antes de escribir nada.
```

(El punto 4, Club del disc, ya está resuelto — ver arriba. No hace falta
ningún prompt de continuación para esto.)

### Prompt — Remesas de pago a proveedores (SEPA pain.001)

```
Lee docs/PLAN_COBRAMENTS_PAGAMENTS.md, sección "Remesas de pago a
proveedores (SEPA pain.001) — diseño acordado". El diseño (RemesaPagament/
RemesaPagamentLinia, estado en_remesa, conciliación línea a línea o en
bloque contra toda la remesa) ya está discutido y aprobado. Escribe los
modelos SQLAlchemy + migración Alembic, el generador del XML
pain.001.001.03, los endpoints (generar remesa, listar, descargar XML,
anular) y la extensión de conciliar_moviment para aceptar
remesa_pagament_id. NO despliegues contra dev sin confirmación. Tests
incluidos.
```
