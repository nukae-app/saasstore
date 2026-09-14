**Implementat (2026-09-14)**: models (`ConfiguracioBotiga.recc_actiu`/
`prorrata_pct_provisional`, `TipusIva.exempt`, `Despesa.destino_iva`/
`importacio_diferida`, `IvaCompensacioPendent`), `_calcula_303` amb RECC/
prorrata/importació diferida/compensació, `services/aeat_303_fitxer.py`
(codificador verificat camp a camp — longitud de les 3 pàgines contrastada
exactament amb el disseny oficial `DR303e21v200.xlsx`), endpoint
`POST /admin/aeat/303/{year}/{trimestre}/fitxer`, i tots els camps nous
exposats als schemas/endpoints existents (`/admin/despeses`,
`/admin/tipus-iva`, `/admin/configuracio`) — sense això la funcionalitat
seria inaccessible des del panell tot i estar ben calculada. Migració
`7a3aa78f0c30`. Tests a `test_aeat_303_fitxer.py` i `test_model_303.py`
(24+ tests, incloent longitud exacta de cada pàgina i configurabilitat via
API). Pendent: desplegar amb confirmació, i **provar el primer fitxer real
contra el validador de la Seu Electrònica abans de confiar-hi en
producció** — segueix sense verificar-se contra una presentació real.

# Fitxer AEAT Model 303 — disseny (2026-09-14)

Nascut del punt 1 de `docs/PLAN_COMPTABILITAT.md` ("exportació PDF/Excel dels
models AEAT"), que va créixer molt en discutir-ho: l'usuari vol el **fitxer
oficial importable a la Seu Electrònica** (no només PDF/Excel per copiar a
mà), i vol donar servei des del principi a règims especials encara que cap
tenant real els faci servir avui — decisió explícita de producte SaaS,
acceptant el risc de no poder-los validar contra un cas real fins que
aparegui un tenant que els necessiti. **Cap d'això no substitueix la
verificació amb una gestoria real abans de presentar cap fitxer a producció
— mateix criteri que VeriFactu.**

## Font: el disseny de registre oficial

AEAT el publica com a XLSX (`DR303e21v200.xlsx`, Ordre HAC/646/2021, vigent
des del període 07/2021 — no s'actualitza cada any si el format no canvia).
Format de text d'ample fix amb marcadors `<T303...>...</T303...>`, dividit
en 5 "pàgines" (una per bloc de casella). **La nostra numeració de casella
ja coincideix amb l'oficial** (01-46 = règim general, exactament les que ja
calcula `_calcula_303`) — redueix molt el risc de mapeig.

## Abast acordat

1. **Règim general** (ja el tenim calculat, casilles 01-46) — codificar-lo
   al format fix.
2. **RECC (criteri de caixa, art. 163 undecies LIVA)** — decisió d'usuari:
   construir-lo ja, encara que cap tenant real l'apliqui avui.
3. **Prorrata especial (art. 103.Dos.1º LIVA)** — mateix criteri.
4. **IVA a la importació diferit** — mateix criteri.
5. **Arrossegament de compensació de quotes entre trimestres** — gap
   funcional real (no només del fitxer), es tanca ara.
6. **Declaració complementària/rectificativa** — mateix criteri.

## 1. Bloc d'identificació (capçalera de la pàgina 1)

Camps obligatoris que avui NO calculem (són una declaració del propi
contribuent, no un càlcul): tipus de declaració (I/D/N/C/G/V/U/X), i ~14
indicadors Sí/No. **Es demanen a l'endpoint de generació, mai s'assumeixen**
— per defecte tots "No" excepte els que resultin del disseny acordat aquí
(RECC, prorrata). Foral/SII/concurs/règim simplificat/autoliquidació
conjunta: sempre "No", no es demanen (confirmat amb l'usuari que no apliquen
a cap vertical d'aquest SaaS avui).

## 2. RECC — disseny

**No és una casella nova, és un canvi de QUINA DATA es fa servir** per
decidir a quin trimestre pertany cada operació:

- Flag nou a nivell de tenant: `ConfiguracioBotiga.recc_actiu: bool`. És una
  elecció de tot el negoci davant Hisenda (art. 163 undecies), no es pot
  triar operació a operació.
- Quan actiu, `_calcula_303` filtra per **data de cobrament/pagament real**
  en lloc de data de meritació:
  - Vendes web: `Order.paid_at` (ja existeix).
  - Vendes externes: `VentaExterna.paid_at` (ja existeix, confirmat a
    `banc.py::conciliar_moviment`).
  - Despeses: `Despesa.payment_date` (ja existeix) — només despeses amb
    `payment_status=pagat` computen com a IVA deduïble; les pendents NO,
    encara que la factura sigui d'aquest trimestre.
  - **Regla dels 31/12 de l'any següent** (meritació forçosa si no s'ha
    cobrat/pagat abans): una venda/despesa d'any N encara no cobrada/pagada
    el 31/12/N+1 es dona per meritada igualment aquell dia — cal una
    consulta addicional que ho detecti (data d'emissió a l'any N, encara
    sense `paid_at`/`payment_date` a 31/12/N+1) i ho inclogui al trimestre
    4 de N+1.
- **Caselles informatives noves** (no alteren el resultat, són desglossat
  per a AEAT): `[62]`/`[63]` (repercutit RECC, base/quota) i `[74]`/`[75]`
  (suportat RECC, base/quota) — el mateix subconjunt de dades que ja s'ha
  fet servir per calcular 01-46, marcat com "operació RECC" perquè quan el
  flag és actiu, TOTES les operacions del tenant ho són.

## 3. Prorrata especial — disseny

El més obert de dissenyar dels tres. Requereix poder distingir, per primer
cop en aquest sistema, entre vendes **exemptes** i **gravades** — avui
`TipusIva` només té un percentatge, no un concepte d'exempció real (no és
el mateix un 0% gravat que una operació exempta: l'exempta NO dona dret a
deduir l'IVA suportat directament atribuïble).

Proposta:
- `TipusIva.exempt: bool` nou (per defecte `False`) — marca un tipus com
  "exempt d'IVA" en lloc de gravat a un percentatge.
- `Despesa.destino_iva`: enum nou (`activitat_gravada` | `activitat_exempta`
  | `comu`) — classifica cada despesa segons a quina activitat es destina.
  Per defecte `activitat_gravada` (comportament actual, sense canvis per a
  qui no fa servir prorrata).
- `ConfiguracioBotiga.prorrata_pct_provisional: Decimal | None` — el %
  provisional de l'any en curs (el definitiu es regularitza al 4T amb el %
  real de l'any, art. 105 LIVA) — **valor introduït a mà**, aquest sistema
  no calcula sol quin % li correspon (depèn del volum d'operacions exemptes
  vs gravades de l'exercici anterior).
- Impacte en el càlcul: l'IVA suportat de despeses `comu` es dedueix només
  al `prorrata_pct_provisional`% (en lloc del 100%); les `activitat_exempta`
  no es dedueixen gens; les `activitat_gravada` es dedueixen al 100% com
  ara. Al 4T, regularització de tot l'any amb el % definitiu (introduït a
  mà també).
- **Fora d'abast explícit, encara amb prorrata activada**: prorrata general
  (automàtica, sense elecció expressa) — només es construeix l'especial,
  que és la que cal triar expressament i la que té sentit per a un negoci
  petit amb activitat mixta puntual.

## 4. IVA a la importació diferit — disseny

No hi ha cap concepte d'"importació" avui (una compra a fora de la UE entra
com una `Despesa` normal). Proposta:
- Nou camp a `Despesa`: `importacio_diferida: bool` (per defecte `False`).
  Quan `True`, l'IVA d'aquesta despesa NO es tracta com a IVA suportat
  normal (472): es reconeix a la casella `[77]` (IVA a la importació
  liquidat per Duana pendent d'ingrés) en comptes de la `[28]/[29]`
  habituals — mateix import, casella diferent, perquè al règim de
  diferiment el meritament i la deducció es fan a la mateixa
  autoliquidació (neutre de tresoreria).
- No cal modelar el DUA (document duaner) sencer — n'hi ha prou amb el flag
  i reutilitzar els camps ja existents de `Despesa` (base, IVA).

## 5. Arrossegament de compensació de quotes — disseny

Nou model petit, independent del fitxer (soluciona un buit funcional real):

```python
class IvaCompensacioPendent(TenantScoped, Base):
    __tablename__ = "iva_compensacio_pendent"
    __table_args__ = (UniqueConstraint("tenant_id", "fiscal_year", "trimestre"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, index=True)
    trimestre: Mapped[int] = mapped_column(Integer)
    import_pendent: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # casella [87] d'aquest trimestre
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- Casella `[110]` d'un trimestre = `import_pendent` del registre del
  trimestre anterior (0 si no n'hi ha).
- Quan es genera el fitxer amb `tipo_declaracion="C"` (sol·licitud de
  compensació) i el resultat surt negatiu, es desa un registre nou amb
  `[87] = [110] - [78]` per al trimestre següent.
- No es recalcula mai sol: només es crea/actualitza en generar el fitxer
  del trimestre corresponent — evita duplicar lògica de negoci fora d'aquí.

## 6. Declaració complementària — disseny

Sense modelar res nou: dos camps opcionals a l'endpoint de generació
(`es_complementaria: bool`, `numero_justificante_anterior: str | None`) que
omplen directament les posicions 408/409 del disseny oficial. El "número de
justificant" l'assigna AEAT en presentar la declaració original — com
aquest sistema no presenta telemàticament, sempre serà un valor introduït a
mà per l'admin (igual que `cuota_integra_exercici_anterior` al Model 202).

## Fora d'abast, explícit

- Prorrata general (automàtica) — només l'especial.
- Modelar el DUA sencer — només el flag a `Despesa`.
- Qualsevol cosa de tributació foral, SII, concurs de creditors, règim
  simplificat, autoliquidació conjunta — descartat perquè no aplica a cap
  vertical d'aquest SaaS avui (confirmat amb l'usuari).
- Presentació telemàtica real — només es genera el fitxer, l'admin el puja
  a la Seu Electrònica.

## Com seguir

Mateix protocol: aquest document ja és la proposta de model. Un cop
aprovat, es migra tot junt (són canvis petits i independents entre ells:
`ConfiguracioBotiga` +2 camps, `TipusIva` +1 camp, `Despesa` +2 camps, 1
taula nova) i després es construeix el codificador del fitxer + endpoint.
**Provar el primer fitxer real contra el validador de la Seu Electrònica
abans de confiar-hi en producció** — cap d'aquest disseny s'ha pogut
verificar contra una presentació real.
