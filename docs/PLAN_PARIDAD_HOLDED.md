# Plan de paridad funcional con Holded

Documento de trabajo (no arquitectura) para cerrar, de forma priorizada, la
distancia funcional con Holded (`holded.com/es/funcionalidades`) detectada en
una comparación explícita hecha en sesión (ver conversación de 2026-09-02).
Complementa — no sustituye — la sección "Estado actual (qué FALTA)" de
`CLAUDE.md`: aquella lista viene de necesidades internas del negocio
(pasarela de pago, migración del blog, envíos...); esta viene de comparar
feature a feature contra un ERP/facturación de referencia del mercado.

Pensado para que una sesión nueva, sin memoria de la conversación original,
pueda retomar cualquier bloque leyendo solo su sección. Cada bloque sigue el
protocolo ya establecido en este proyecto: **proponer el modelo de datos,
discutirlo con el usuario, y no migrar/tocar dev hasta que se apruebe.**
Este documento fija el *orden* y el *alcance*, no cierra el diseño de cada
bloque — eso se hace al empezarlo, como se hizo con Fases 1-5 de
Comptabilitat.

## Restricciones que aplican a todos los bloques

- **Coste**: VPS de 10-20€/mes (ver `CLAUDE.md`). Cualquier bloque que
  dependa de un servicio de pago de terceros (agregador bancario PSD2, OCR,
  motor de facturación electrónica) debe decirlo explícitamente como
  decisión de negocio, no solo técnica — no se contrata nada sin que el
  usuario lo apruebe.
- **Riesgo legal/fiscal**: todo lo que toque presentación telemática a
  Hacienda (SII, modelos IRPF, Modelo 200, TicketBAI) o facturación con
  numeración legal (VeriFactu) requiere validación con una gestoría real
  antes de darlo por bueno — no es algo que se pueda verificar solo con
  tests. Se marca como 🔴 en la tabla de bloques.
- **Build vs. buy**: para todo lo que sea un producto entero en sí mismo en
  el mercado (nóminas, agregación bancaria PSD2, OCR de tickets, motor de
  e-invoicing certificado), la opción por defecto a evaluar primero es
  integrar un proveedor especializado vía API, no reconstruirlo. Construir
  de cero se reserva para lo que es específico del dominio de este negocio
  (como ya se hizo con doble partida y activos).
- Sigue vigente la norma general del proyecto: nunca migrar Alembic ni
  reconstruir contenedores contra dev sin confirmación explícita — hay
  tenants reales.

## Qué NO se incluye aquí

Ya cubierto (ver comparación original, no se repite): cuadro de cuentas,
libro diario, balance, PyG, amortización de activos, bloqueo de períodos,
gastos, pedidos de compra/venta, TPV mostrador, roles de usuario.

Explícitamente fuera de alcance por ahora, con motivo:

- **RR.HH. / Nóminas**: es un producto entero (cálculo de IRPF por tramos,
  cotizaciones SS, convenios, TA2/TC1...). Construirlo mal es un riesgo
  legal directo para el cliente. Si algún tenant lo necesita de verdad, la
  vía es integrar un proveedor de nóminas vía API (ej. tipo A3nom/Payflow),
  no construirlo. No entra en este plan salvo que el usuario decida
  explícitamente lo contrario.
- **Proyectos (Kanban/Gantt/rentabilidad de proyecto)**: genérico de SaaS de
  gestión, no encaja con los verticales actuales (discos, floristería). Se
  deja como idea para si en el futuro se incorpora un vertical de tipo
  "servicios/agencia" que lo necesite — no se planifica ahora.

Todo lo demás de la comparación original sí entra, repartido en los bloques
de abajo.

## Vista general de bloques

| Bloque | Qué cubre | Prioridad | Riesgo | Depende de |
|---|---|---|---|---|
| B1 — Documentos comerciales no fiscales | Presupuestos, albaranes, formalizar factura de compra en PDF | Alta | 🟢 Bajo | — |
| B2 — Facturación de venta propia | Factura de venta numerada, plantillas, envío | Alta | 🔴 Alto (VeriFactu) | B1 (motor de PDF/numeración) |
| B3 — Tesorería avanzada | Conciliación con reglas/sugerencias, flujo de caja proyectado | Media | 🟡 Medio (build vs. buy en sync bancaria) | — |
| B4 — Inventario | Alarmas de stock, multi-almacén, listas de precio | Media | 🟢 Bajo | — |
| B5 — Cierre contable formal | Cuentas anuales, punteado de asientos, Modelo 200 | Media | 🔴 Alto (Modelo 200) | — |
| B6 — Remesas y domiciliaciones SEPA | Generación de fichero SEPA (pain.008), gestión de recibos | Baja | 🟡 Medio | B1/B2 |
| B7 — CRM ligero | Pipeline de oportunidades, actividades, notas, tags | Media | 🟢 Bajo | — |
| B8 — OCR de gastos | Autocompletar Despesa desde foto/PDF de ticket | Baja | 🟡 Medio (coste API) | B1 |
| B9 — Cumplimiento telemático | SII, modelos IRPF, TicketBAI | Muy baja | 🔴 Muy alto | B2 |

La prioridad refleja impacto percibido para un cliente que viene de Holded
vs. esfuerzo, **no** un orden de ejecución obligatorio — eso se decide al
final de este documento.

---

## B1 — Documentos comerciales no fiscales

**Por qué primero**: es la base técnica (generación de PDF, numeración
correlativa, plantilla) que reutilizarán B2 y B6, y no tiene riesgo legal
porque ni presupuestos ni albaranes son documentos fiscales — no hay
numeración legal que proteger ni Hacienda de por medio.

Alcance:
- **Presupuestos** (`Pressupost`): entidad nueva, línea de producto/servicio
  con precio, estado (`esborrany`/`enviat`/`acceptat`/`rebutjat`), fecha de
  validez. Un presupuesto aceptado puede convertirse en pedido/venta
  (reutilizar el patrón ya existente de `Comanda`/`Order`, no reinventar).
- **Albaranes** (`Albara`): documento de entrega ligado a un pedido —
  reutiliza líneas de `Comanda`/`Order` existentes, añade solo lo que falta
  (fecha de entrega, firma/confirmación de recepción si aplica).
- **Formalizar factura de compra**: `Despesa` ya tiene casi todos los
  campos; falta solo exportar/generar un PDF de la despesa+proveedor con
  formato reconocible, no cambia el modelo de datos.
- **Motor de PDF reutilizable**: una sola pieza de infraestructura (motor de
  plantillas + generación PDF) que sirva para presupuesto, albarán y,
  después, factura — evita construir tres veces lo mismo. Elegir librería
  Python (ej. WeasyPrint sobre HTML/CSS, coherente con que ya se genera HTML
  en el resto del proyecto) es una decisión a tomar al empezar el bloque.

Qué NO decide este bloque: numeración legal de facturas ni nada de
VeriFactu — eso es B2.

## B2 — Facturación de venta propia

**El gap más visible de todos** frente a Holded: hoy no se emite ningún
documento fiscal de venta, solo se registra la venta internamente
(`Order`/`VentaExterna`).

🔴 **Antes de diseñar nada**: confirmar con una gestoría real el estado y
plazos de aplicación del Reglamento VeriFactu (RD 1007/2023) para el
régimen de este negocio (SL vs. Autónomo tienen calendarios distintos), y
decidir explícitamente **build vs. buy**:
- *Buy*: integrar un motor de facturación electrónica certificado
  VeriFactu vía API (hay varios proveedores en España) y que Ultra-Local
  Records solo construya la UI encima. Menor riesgo legal, coste recurrente
  por proveedor.
- *Build*: implementar el encadenado de hashes, huella, QR y registro
  inmutable de facturación nosotros mismos. Cero coste recurrente, pero todo
  el riesgo legal y de mantenimiento (la normativa puede cambiar) es
  nuestro.

Esta decisión bloquea el diseño del modelo de datos — no tiene sentido
proponer un esquema de `Factura` hasta saberlo. Cuando se decida:
- Reutiliza el motor de PDF/plantillas de B1.
- Numeración correlativa: mismo patrón atómico que `JournalEntryCounter`
  (UPDATE condicionado, nunca SELECT+UPDATE — es la misma clase de problema
  de concurrencia que ya resolvimos en `services/reservations.py` y en
  contabilidad).
- Snapshot de la factura en el momento de emisión (mismo principio que
  `order_items.precio` — una factura emitida no cambia aunque cambie el
  catálogo).
- Envío de factura con acuse: reutilizar `services/emailer.py`.

## B3 — Tesorería avanzada

- **Conciliación con reglas**: reglas guardadas tipo "todo movimiento con
  concepto que contenga X → conciliar automáticamente con proveedor Y" —
  extensión del `ConciliarModal` actual, no requiere modelo nuevo grande,
  solo una tabla de reglas y aplicarlas al importar.
- **Sugerencias automáticas**: al conciliar, proponer la `Despesa` más
  probable por importe+fecha cercana antes de que el usuario busque en el
  desplegable — mejora de UX/backend sobre lo que ya existe, no bloque
  nuevo de datos.
- **Flujo de caja proyectado**: a diferencia de la caja diaria (histórica),
  esto es proyección a futuro combinando `Despesa.due_date` pendientes +
  estacionalidad de ventas. Es el ítem más abierto de diseño del bloque —
  discutir el modelo de proyección antes de construir nada.
- **Sync bancaria automática (PSD2)**: 🟡 decisión build vs. buy explícita.
  Integrar un agregador (Bankinter/GoCardless Bank Account Data, Tink,
  Nordigen...) tiene coste recurrente y hay que confirmarlo con el usuario
  contra el presupuesto de 10-20€/mes — probablemente no compensa mientras
  el import manual N43/CSV cubra el caso de uso real. Recomendación por
  defecto: no hacerlo salvo que el usuario lo pida explícitamente después
  de ver el coste.

## B4 — Inventario

- **Alarmas de stock**: umbral mínimo por `Item` (nou) que dispare una
  notificación/badge en el admin — extensión pequeña sobre el modelo
  existente, no requiere tabla nueva.
- **Multi-almacén**: solo tiene sentido si algún tenant real gestiona más
  de una ubicación física. Confirmar con el usuario si aplica a algún
  tenant actual antes de diseñar — si no, se deja documentado pero no se
  construye todavía (coste de modelar mal algo sin caso de uso real es
  alto: tocaría `Item`, `StockHold`, checkout, TPV).
- **Listas de precio** (por canal o por cliente): posible pero de bajo
  valor evidente para el negocio actual — revisar prioridad real con el
  usuario antes de meterlo en un sprint concreto.

## B5 — Cierre contable formal

- **Cuentas anuales / cierre de ejercicio**: hoy el balance interino usa una
  línea sintética "129* Resultat de l'exercici (provisional)" porque no
  existe un cierre real. Este bloque formaliza el asiento de cierre y
  apertura de ejercicio (regularización de resultados, cierre de cuentas de
  gasto/ingreso contra 129, apertura del ejercicio siguiente) — encaja de
  forma natural con `PeriodeComptable`, que ya modela el bloqueo de
  períodos.
- **Punteado de asientos**: flag `checked`/`punteat` en `JournalLine` +
  vista de conciliación manual — cambio de modelo pequeño.
- **Modelo 200 (Impuesto de Sociedades)**: 🔴 alto riesgo legal, cálculo
  fiscal no trivial (ajustes extracontables, tipos reducidos, deducciones).
  Mismo criterio que B2: sin gestoría de por medio no se construye a
  ciegas. Candidato fuerte a quedarse como informe de apoyo (como el
  Modelo 303 actual: "casillas", sin presentación telemática) en lugar de
  presentación oficial.

## B6 — Remesas y domiciliaciones SEPA

Generación de fichero SEPA (formato pain.008) para dominiciar cobros a
clientes o pagos a proveedores en bloque. Valor real solo si el negocio
domicilia pagos periódicos (p. ej. cuotas del Club del disc vía SEPA en vez
de tarjeta) — repasar con el usuario si ese es el caso antes de priorizarlo;
si el Club del disc sigue cobrando por Stripe/Redsys, este bloque pierde
gran parte de su valor y baja de prioridad.

## B7 — CRM ligero

Encaja bien con la vocación de "comunidad" del proyecto (blog + agenda +
Club del disc ya existentes). Alcance mínimo razonable:
- Reutilizar `User`/`Address`/`PeticionCliente` como base de "contacto".
- Tabla nueva de **oportunidades** (ej. "quiere una copia rara, avisar
  cuando llegue" — de hecho `PeticionCliente` ya es casi esto) con estado
  tipo pipeline simple.
- **Notas y actividades** sobre un contacto — tabla nueva simple.
- Nada de "embudo de ventas" complejo tipo Holded B2B — nuestro negocio es
  B2C de tienda, un pipeline elaborado no aporta.

## B8 — OCR de gastos

Autocompletar `Despesa` (proveedor, importe, fecha, IVA) a partir de una
foto/PDF de ticket. 🟡 Build vs. buy: hay APIs de OCR de recibos
especializadas (Mindee, Veryfi...) con coste por documento — evaluar
volumen real de despesas/mes del negocio antes de decidir si compensa
frente a introducir el gasto a mano (hoy toma ~30 segundos por `Despesa`).
Depende de B1 solo en el sentido de que reutiliza el formulario de
`Despesa` ya existente — no depende técnicamente, solo tiene más sentido
después de tener facturación de compra formalizada en PDF.

## B9 — Cumplimiento telemático (SII, IRPF, TicketBAI)

Ya identificados y aparcados explícitamente en sesiones anteriores como
"legalmente más arriesgado". Se mantienen aquí solo para que la lista de
gaps quede completa, con prioridad mínima:
- **SII** (Suministro Inmediato de Información): solo obligatorio a partir
  de cierto volumen de facturación — probablemente no aplica a este
  negocio nunca. No priorizar sin confirmar que aplica.
- **Modelos IRPF** (111/115/123/130/180/190): relevantes solo si el negocio
  tiene retenciones a terceros (alquiler, profesionales) — alcance a
  confirmar con gestoría, no con el código.
- **TicketBAI**: específico de País Vasco/Navarra — no aplica salvo que el
  negocio opere allí.

---

## Cómo seguir desde aquí

Este documento fija el mapa; no implica que se ejecuten los 9 bloques.
Antes de tocar código en el primer bloque:

1. Confirmar con el usuario el **orden real** de ejecución (la tabla de
   arriba es una propuesta de prioridad, no una cola fija).
2. Para B2, B3 (sync PSD2), B5 (Modelo 200), B6, B8 y B9: resolver primero
   la pregunta de negocio marcada en su sección (gestoría, coste de
   servicio de terceros, aplicabilidad real al tenant) — son bloqueantes
   de diseño, no de implementación.
3. Al empezar un bloque, seguir el mismo patrón que las Fases 1-5 de
   Comptabilitat: proponer modelo de datos → discutir → aprobar →
   migración → tests → deploy a dev con confirmación → deploy a prod con
   confirmación.
