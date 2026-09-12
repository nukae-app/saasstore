# Plan de Comptabilitat — estat verificat i pròxims passos

Document que substitueix, per a tot el que és contabilidad, la llista de
pendents de `docs/MEJORAS_COMPTABILITAT.md` (ara marcat com a arxivat) i les
seccions B1/B2/B3/B5 de `docs/PLAN_PARIDAD_HOLDED.md` (que segueix vigent per
a la resta de blocs: B4 inventari, B6 SEPA, B7 CRM, B8 OCR, B9 SII/IRPF).

Nascut d'una revisió feta en sessió del 2026-09-12 ("faltan modelos de AEAT,
faltan exportaciones..."), en què **es va llegir el codi real abans de
proposar res** (mateix protocol de sempre en aquest projecte) i es va
descobrir que els dos documents anteriors estaven bastant desactualitzats:
diverses coses marcades com "pendent" ja estaven fetes. Aquest document fixa
l'estat real, verificat línia a línia, per no repetir l'error.

## Estat actual verificat (2026-09-12)

Tot això **ja existeix i funciona**, amb codi a `api/app/routers/comptabilitat/`,
`api/app/routers/documents/` i pantalles a `web/app/admin/`:

- **Comptabilitat base**: pla de comptes (sembrat automàtic per
  jurisdicció/forma legal), partida doble, llibre diari, llibre major,
  balanç de situació, compte de PyG. Contabilitzat automàticament des de
  vendes web, TPV, despeses, actius i amortitzacions — no editable a mà a
  propòsit.
- **Punteig d'assentaments**: `JournalLine.punteat/punteat_at/punteat_by`,
  amb checkbox a `/admin/llibres` (pestanya Major). Fet a
  `2ab1863` (2026, "Millora el mòdul de Comptabilitat").
- **Tancament d'exercici formal**: `POST /admin/periodes/{year}/tancar-exercici`
  genera l'assentament de regularització (compte 129) i bloqueja els 12
  períodes de l'any (`routers/comptabilitat/tancament.py`). Substitueix la
  línia sintètica de balanç que hi havia abans.
- **Flux de caixa projectat**: `GET /admin/flux-caixa-projectat`, combina
  `Despesa.due_date` pendents + estacionalitat (mitjana del mateix mes
  natural en anys anteriors). `routers/comptabilitat/flux_caixa.py`.
- **Tresoreria avançada (Bloc B3 complet)**: import d'extractes N43/CSV,
  regles de conciliació guardades (`ReglaConciliacio`), aplicació automàtica
  en importar, suggeriments de `Despesa` per import+data en conciliar a mà.
  `routers/comptabilitat/banc.py`, `services/banc_conciliacio.py`.
- **Models fiscals AEAT** (`routers/comptabilitat/aeat.py`,
  `schemas/aeat.py`) — **només caselles per copiar a mà**, mai presentació
  telemàtica, amb `fora_abast` explícit a cada schema i avís segons
  `ConfiguracioBotiga.legal_form`:
  - IVA: **303** (trimestral), **390** (resum anual).
  - Retencions IRPF a proveïdors: **111**/**115** (trimestral),
    **190**/**180** (resum anual).
  - Autònoms: **130** (pagament fraccionat IRPF, estimació directa).
  - Societats: **200** (Impost de Societats, estimació de suport),
    **202** (pagament fraccionat, modalitat art. 40.2 LIS).
  - Tot exposat a `/admin/models-fiscals` (frontend).
- **Documents comercials (Bloc B1)**: pressupostos (`Pressupost`, amb
  conversió a `Order`), albarans (autogenerats en marcar un pedido
  "enviat", ver `services/albarans.py`), numeració correlativa atòmica
  compartida (`DocumentCounter`).
- **Factura de venda base (Bloc B2, sense VeriFactu)**: `Factura` amb
  numeració legal sense buits, des de zero o des d'una venda ja
  registrada (web/TPV), PDF, anul·lació sense reutilitzar número.
  **Deliberadament sense** encadenat de hashes, QR ni enviament a
  Hisenda — ver docstring de `models/documents.py`.
- **Exportacions existents**: CSV del llibre diari
  (`GET /admin/llibre-diari/{year}/export`), Excel de la caixa diària
  mensual, exportació experimental d'assentaments a Holded via API
  (`routers/comptabilitat/holded.py` — marcada "experimental", esquema de
  payload no verificat oficialment, ús manual).

## Gaps reals identificats (per prioritat)

### 1. Exportació PDF/Excel dels models AEAT i del Balanç/PyG 🟢 barat, alt valor

Avui **cap** dels endpoints `/admin/aeat/*`, `/admin/balanc-situacio/{year}/{mes}`
ni `/admin/compte-resultats/{year}/{mes}` genera res descarregable: només es
veuen en pantalla a `/admin/models-fiscals` i `/admin/llibres`. L'usuari ha de
copiar els números a mà a la seu electrònica o a un correu per a la gestoria.

- Reutilitza el motor de PDF que ja existeix per a factures/albarans/
  pressupostos (`services/documents_pdf.py`) — no cal triar llibreria nova.
- Un PDF/Excel per model AEAT amb les caselles tal com surten avui en
  pantalla, més capçalera amb NIF/raó social del tenant i el `fora_abast`
  ja existent com a nota al peu (no inventar-se res nou: és el mateix càlcul,
  només en un altre format).
- Balanç de situació i Compte de PyG: mateix tractament, format imprimible
  per arxivar o enviar a la gestoria.
- No requereix modelar res nou ni migració — és una capa de presentació
  sobre dades que ja es calculen correctament.

### 2. Modelo 347 (operacions amb tercers >3.005,06€/any) 🟢 baix risc

No existeix cap codi per aquest model (verificat per grep). Encaixa amb el
mateix patró que 303/111/115: agregació per proveïdor/client amb NIF,
desglossat trimestral, "casella calculator" sense presentació telemàtica.

- Dades ja disponibles: `Proveedor.nif` (costat compres, via `Despesa`),
  `Factura.client_nif` (costat vendes, però només factures emeses amb NIF
  informat — a diferència dels 111/115 no totes les vendes en tindran).
  Cal decidir com tractar vendes sense NIF de client (la majoria, en un
  negoci B2C) — probablement queden fora del 347 per definició legal
  (només afecta operacions amb un mateix tercer que superen el llindar
  anual, típicament rellevant per a proveïdors, rarament per a clients
  particulars d'una botiga).
- Abans de construir: proposar el model de sortida (mateix esperit que
  `Model303Out`/`ModelRetencioOut`) i discutir-lo — no calen taules noves,
  només un nou endpoint de lectura agregada + el seu export PDF (punt 1).

### 3. VeriFactu — completar la factura de venda (Bloc B2) 🔴 risc legal alt

Segueix aparcat des que es va construir la capa base de `Factura`. Bloquejant
abans de dissenyar res (igual que ja deia `PLAN_PARIDAD_HOLDED.md`):

- **Confirmar amb una gestoria real** el calendari d'aplicació del
  Reglament VeriFactu (RD 1007/2023) segons la forma jurídica de cada
  tenant (SL vs Autònom tenen dates diferents) — no assumir-ho des del
  codi.
- **Decidir build vs. buy** explícitament amb el usuari: integrar un motor
  de facturació electrònica certificat VeriFactu via API (menys risc legal,
  cost recurrent) vs. implementar l'encadenat de hashes/QR/registre
  immutable nosaltres mateixos (sense cost recurrent, tot el risc legal i
  de manteniment és nostre).
- Un cop decidit: reutilitza el motor de PDF i el patró de numeració atòmica
  ja existents a `Factura`/`DocumentCounter`.

### La resta del gap amb Holded

Segueix documentat, sense canvis, a `docs/PLAN_PARIDAD_HOLDED.md`: B4
(inventari — alarmes de stock, multi-almacén), B6 (remeses SEPA), B7 (CRM
lleuger), B8 (OCR de despeses), B9 (SII/models IRPF de nòmines/TicketBAI).
Cap d'ells és estrictament "comptabilitat" en el sentit d'aquest document.

## Com seguir des d'aquí

Mateix protocol de sempre en aquest projecte: **proposar el model/disseny →
discutir-ho amb l'usuari → aprovar → migrar (si cal) → tests → desplegar a
dev amb confirmació → desplegar a producció amb confirmació.**

### Prompt — Exportació PDF/Excel dels models AEAT i Balanç/PyG

```
Lee docs/PLAN_COMPTABILITAT.md, punto 1 de "Gaps reales". Quiero exportación
PDF (o Excel donde tenga más sentido) de los modelos AEAT ya existentes
(303/390/111/115/190/180/130/200/202) y de Balance de situación / Cuenta de
PyG. Reutiliza services/documents_pdf.py, no modeles nada nuevo — son los
mismos cálculos ya expuestos en /admin/models-fiscals y /admin/llibres, solo
en formato descargable. Propón el diseño de plantilla antes de codear.
```

### Prompt — Modelo 347

```
Lee docs/PLAN_COMPTABILITAT.md, punto 2 de "Gaps reales". Quiero modelar el
Modelo 347 (operaciones con terceros >3.005,06€/año) siguiendo el mismo
patrón que aeat.py (casillas para copiar a mano, nunca presentación
telemática). Antes de escribir código, propón el esquema de salida y cómo
tratar clientes sin NIF informado (la mayoría en un negocio B2C) — discútelo
conmigo.
```

### Prompt — VeriFactu

```
Lee docs/PLAN_COMPTABILITAT.md, punto 3 de "Gaps reales", y
docs/PLAN_PARIDAD_HOLDED.md bloque B2. Antes de tocar código: ayúdame a
preparar las preguntas para la gestoría sobre el calendario real de
VeriFactu (RD 1007/2023) según forma jurídica, y resume las opciones
build vs. buy (proveedores de facturación electrónica certificados en
España) con sus tradeoffs de coste/riesgo para que decida.
```
