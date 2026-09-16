**Estat: pendent d'implementar (aparcat 2026-09-16).** Ningú ha tocat encara
cap fitxer d'aquest pla — és investigació + disseny, llest per començar en
una altra sessió. Origen: l'usuari va detectar que el text que s'escriu als
blocs del constructor del home (títols, subtítols...) només existeix en un
idioma, tot i que la botiga és multi-idioma (`/ca`, `/es`, `/en`, ver
`web/i18n/routing.js` i el `[locale]` de l'App Router).

## El problema, confirmat

- `HomeBlock.props` (`api/app/models/storefront.py`) és un `JSON` pla — un
  bloc "hero" guarda `{"title": "Discos nous...", ...}`, un string simple,
  no un objecte per idioma. Es renderitza igual a `/ca`, `/es` i `/en`.
- Els botons **CAT / ESP / ENG** de dalt del panell d'admin
  (`web/app/admin/layout.jsx`) **no tenen res a veure amb això** — són
  l'idioma de la interfície del propi panell (backed per `Translation` a
  `api/app/models/cms.py` + `/api/i18n/{lang}`), no del contingut de cara al
  client. Fàcil de confondre'ls amb un selector de traducció; no ho és.
- El blog (`Post`, mateix fitxer) ja té un patró diferent: `Post.language`
  és un camp senzill per post — per tenir el mateix article en català i en
  castellà cal **crear dos posts separats** (mateix contingut, dues files),
  no hi ha traduccions vinculades del mateix post.
- Les pàgines estàtiques (`Pagina.content`/`Pagina.name`, termes,
  privacitat, pàgines de text lliure) tenen exactament el mateix problema
  que els blocs: un sol text per a tots els idiomes.

## Solució proposada (acordada amb l'usuari, disseny únicament)

En comptes de `title: "text"`, guardar un objecte per idioma:

```json
{ "title": { "ca": "Discos nous...", "es": "Discos nuevos...", "en": "" } }
```

- **Català com a fallback**: si falta la traducció a `es`/`en`, es mostra el
  valor de `ca` (mateix criteri que `next-intl` ja fa servir per als
  missatges de la interfície — no inventem un mecanisme nou).
- El contingut que ja existeix avui (strings plans) es migra com a
  `{"ca": valor_actual}` — assumeix que tot el que hi ha escrit fins ara és
  en català, que és l'idioma principal segons `CLAUDE.md`.
- Aplica igual a `HomeBlock.props`, `Pagina.content`/`Pagina.name`, i
  qualsevol altre camp de text lliure que s'afegeixi en un futur — un sol
  patró, no un mecanisme diferent per cada taula.

## Decisions de l'usuari encara pendents de confirmar

Es van preguntar i **no es van arribar a respondre** (conversa aparcada
aquí) — cal aclarir-les abans de començar a picar codi:

1. **Abast**: començar només pels blocs que el tenant real fa servir avui
   (`hero` + `carousel`, els únics actius al home de labotigaaquesta), o fer
   els 10 tipus de bloc de cop (`hero`, `carousel`, `text`, `testimonials`,
   `gallery`, `faq`, `banner`, `brand_strip`, `feature_grid`, `video`)?
   Recomanació: Hero + Carrusel primer — menys risc, el patró queda
   verificat i és trivial replicar-lo a la resta quan calgui.
2. **Pàgines estàtiques**: incloure `Pagina.content`/`Pagina.name` en
   aquesta mateixa ronda, o deixar-ho per a una altra (mateix problema, però
   és una taula diferent, no un bloc)?

## Superfície de canvi (si s'aborda Hero + Carousel, l'abast recomanat)

Cap d'aquests fitxers s'ha tocat encara:

**Backend**
- `api/app/blocks/registry.py` — `HeroProps`/`CarouselProps`: els camps de
  text (`title`, `subtitle`, `eyebrow`, `cta_label`, `heading`...) passen de
  `str` a un tipus que accepti `dict[str, str] | str` (acceptar encara
  `str` sol per no trencar la compatibilitat cap enrere amb dades existents
  fins que es migrin) o forçar sempre `dict` amb una migració de dades.
- Migració Alembic que recorri `home_blocks` i embolcalli els strings
  existents a `{"ca": valor}` per als camps afectats.
- Cal decidir on es resol el fallback ca→valor mostrat: al backend (l'API
  ja retorna el text resolt segons `?locale=`) o al frontend (l'API retorna
  l'objecte sencer i `page.jsx` tria l'idioma). Recomanació: **frontend** —
  `[locale]/page.jsx` ja sap el locale actual via next-intl, i així l'admin
  (`disseny-web`) pot seguir rebent l'objecte sencer per editar-lo.

**Admin (`web/app/admin/disseny-web`)**
- `HeroPropsForm.jsx`, `CarouselPropsForm.jsx` — cada camp de text necessita
  un selector d'idioma (mateix esperit que el CAT/ESP/ENG de l'admin, però
  aplicat al *valor del camp*, no a la interfície) — probablement 3 tabs
  petits per sobre de cada input, no 3 formularis sencers duplicats.
- El missatge de previsualització en directe (`PreviewBridge.jsx`,
  `sendPreview`) ja aplica canvis de text per `data-field` — cal que sàpiga
  quin idioma s'està previsualitzant.

**Frontend públic**
- `web/app/[locale]/page.jsx::resolveBlockProps` — en comptes de passar
  `block.props` tal qual, resoldre cada camp de text a l'idioma actual amb
  fallback a `ca`.
- `HomeHero.jsx`, `CarouselBlock.jsx` — si la resolució es fa a
  `resolveBlockProps`, aquests components no haurien de canviar (seguirien
  rebent un string ja resolt).

## Per no oblidar en represendre

- No tocar res del que ja està fet i desplegat del tema "Recordstore"
  (veure la resta de commits d'aquesta sessió) — és ortogonal, no té
  relació amb aquest pla.
- Seguir el mateix criteri de `CLAUDE.md`: no tocar el backend sense
  avisar primer, i `pytest` en verd abans de donar per bo cap canvi de
  backend.
