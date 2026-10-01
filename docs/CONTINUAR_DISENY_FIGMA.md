# Continuar: editor visual del storefront + importación de Figma

Punto de entrada rápido para retomar esto en una sesión nueva. El detalle completo (modelo de datos, decisiones tomadas y por qué, bitácora sesión a sesión con los hallazgos reales de cada pieza) vive en `docs/ARQUITECTURA_DISENY_FIGMA.md` — este fichero es solo el resumen para orientarse en minutos, no sustituye leer el otro.

## Estado a 2026-09-28

- **Fase 0** (spike de mecánica de editor): **cerrada**. Se probó Craft.js en vivo (canvas, panel de propiedades, nodos protegidos del lado cliente, undo/redo, anidación, breakpoints responsive) y se decidió vendorizarlo. El código del spike ya se borró — la Fase 1 construyó la versión real.
- **Fase 1** (modelo de árbol + renderer SSR + routing multi-página + nodos protegidos): **cerrada del todo, las cuatro piezas probadas en vivo** contra el stack de dev real (tenant `escaparate`), incluida la validación de publicación (422 si faltan nodos de `requires_nodes`).
- **Fase 2** (editor visual real): **construida y confirmada en el navegador real por el usuario**. `admin/editor-pagines` (listado + editor: canvas, toolbox de 4 tipos con drag&clic, panel de props por tipo incluido estilo — fons/color/padding/vora —, undo/redo, selector de breakpoints, reordenar nodos existentes arrastrando, modal SEO, desar esborrany/publicar contra `Page` real). Un bug real (click-to-add usaba `actions.add` en vez de `actions.addNodeTree`) se encontró y corrigió antes de que el usuario lo probara, vía comprobación headless con React/Craft.js reales (la extensión de Claude in Chrome no cargaba `localhost:8080` en esta sesión, no relacionado con el código).
- **Pendiente, decisión sin tomar**: si merece la pena invertir en tests automatizados de UI (Playwright u otro) en vez de depender de pruebas manuales/headless cada vez.
- **Fase 3** (OAuth Figma + import de tokens de color/tipografía): **construida y desplegada, pero sin probar en vivo** — el usuario eligió seguir sin credenciales reales de Figma.
- **Fase 4** (import estructural frames→árbol): **construida y desplegada el mismo día, mismo bloqueo que la Fase 3**. Frames con auto-layout → `Stack`, `TEXT` → `TextNode`, fills de imagen → `ImageNode` (exportadas siempre como PNG, nunca SVG — no hay sanitizador de SVG todavía). Un frame sin auto-layout se omite ENTERO con aviso, nunca una heurística. Celery descarga las imágenes y las guarda en `/uploads`. 16 tests en `test_figma.py` (8+8), incluida la tarea de Celery completa llamada directamente contra un fichero de ejemplo simulado.
- Falta, para dar Fase 3 y 4 por cerradas de verdad: que el usuario registre una app OAuth en el developer portal de Figma y se pruebe el ciclo completo contra la API real.
- **Fuera de fases (2026-09-28)**: el usuario probó el editor y notó que no se podía editar el home ni el catálogo, y luego pidió más control de diseño. Cuatro piezas nuevas:
  1. Home (`/`) y catálogo (`/cataleg`) ahora comprueban primero si existe una `Page` publicada con ese slug exacto (`home`/`cataleg`) — si no, siguen con su implementación de siempre (coexistencia, sin migración/retirada de `HomeBlock` ni sustitución destructiva de `/cataleg`). `cataleg` ya no está en `RESERVED_PAGE_SLUGS`.
  2. Nodo `CatalogBrowse` que envuelve el catálogo real (filtros/graella/paginació) para incrustarlo en cualquier página — verificado en vivo con una página de prueba real.
  3. `/admin/editor-pagines` distingue "Pàgines del sistema" (Home, Catàleg — botón "Dissenyar" directo) de "Pàgines pròpies".
  4. Editor con más control de diseño: tipografía, imagen de fondo, alineación/distribución en secciones, nodos `Button`/`Spacer`.
  - **Todo esto sin probar a mano en el navegador todavía** — solo verificado por compilación/tests/curl.
- **Módulos prediseñados — construidos**: `HomeBlockNode` (nodo puente único, reutiliza los componentes React reales de `BLOCK_COMPONENTS` tal cual, cero reimplementación visual) cubre los 6 bloques que usa hoy `escaparate` (hero/carousel/spotify_recommendations/curator_selection/genre_grid/about_strip), con formulario de propiedades donde el bloque tiene props configurables (hero/carousel/curator_selection). Además, "Dissenyar" el Home ahora lee el `/admin/home-blocks` real y arranca el editor con el contenido que ya está publicado, no un lienzo vacío.
- **Bug real encontrado por el usuario al probarlo, ya arreglado**: el canvas de Home salió vacío la primera vez — un `try/catch` mudo en el frontend se tragaba el error si `/admin/home-blocks` fallaba (probable sesión inválida en ese momento) y creaba la página igualmente, vacía, sin avisar. Ya no atrapa el error en silencio (se ve un mensaje real) y hay un botón de recuperación manual si vuelve a pasar. El `Page(slug="home")` que se quedó vacío se rellenó directamente. **Pendiente**: revisar si el mismo patrón de "atrapar error en silencio" existe en otros flujos de esta sesión (p. ej. `admin/figma/page.jsx`).
- **Previsualización real del borrador (2026-09-29)**: con el Home ya lleno de bloques, el usuario notó que en el canvas del editor solo se ven cajas grises ("Bloc: Hero"), no el diseño real — esperado por diseño (regla de oro, nunca datos en vivo en el canvas), pero no aceptable para él. No se puede resolver dentro del propio Craft.js (los bloques reales son Server Components async, no se pueden montar en un árbol cliente). Solución: ruta nueva `web/app/[locale]/preview-pagina/[slug]/page.jsx` que renderiza `draft_tree` con el mismo `TreeRenderer` real del sitio público — mismo aspecto exacto. Vive fuera de `/admin/` (evita el chrome/guardia de sesión del panel) y se autentica con el access token pasado por query param desde el botón "Previsualitzar" nuevo del editor — pragmático, documentado como tal, no un mecanismo de token nuevo. `preview-pagina` añadido a los slugs reservados. Verificado con `curl` en los 3 casos (sin token/token inválido/token válido) — el usuario todavía no lo ha probado él mismo.
- **Pendiente, explícitamente parado**: ficha de producto (`/disc/[id]`) — es una plantilla con datos en vivo por disco (precio, stock, carrito), no una página única; mismo nivel de riesgo que los nodos protegidos de checkout, se aborda aparte con el mismo cuidado. Explorador de ficheros Figma — bloqueado por una limitación real de la API de Figma (no hay endpoint para listar todos los ficheros sin un team ID).
- **Fase 5** (migración/retirada real de `HomeBlock` y `Pagina`): sigue sin empezar — lo de arriba es coexistencia, no migración.
- **Todo el trabajo de las Fases 0-4 está sin commitear.** Nunca se commitea sin que el usuario lo pida explícitamente — no se ha pedido. Comprueba `git status` antes de asumir nada sobre qué hay en el historial de git; los ficheros existen en disco y están desplegados en los contenedores de dev (incluidos `worker`/`beat`), pero no hay commit.

## Qué existe ya (ficheros tocados, ninguno commiteado)

Backend:
- `api/app/models/storefront.py` — modelo `Page` (nuevo, junto a `HomeBlock` que no se ha tocado), incluye `requires_nodes` (JSON)
- `api/app/models/figma_import.py` — `FigmaConnection`, `FigmaImportStatus`, `FigmaImportJob` (nuevo)
- `api/app/tenant_secrets.py` — `figma_access_token`/`figma_refresh_token` añadidos a `TenantSecrets`
- `api/alembic/versions/f3f9efa93dd9_*.py` — migración de las 3 tablas nuevas, **ya aplicada en la BD de dev**
- `api/alembic/versions/a6a451afd252_*.py` — migración de `pages.requires_nodes`, **ya aplicada en la BD de dev**
- `api/app/routers/pages.py` (nuevo) — CRUD admin de `Page` + publish con validación de nodos protegidos + lectura pública
- `api/app/schemas/storefront.py` — `PageOut`/`PagePublicOut`/`PageCreateIn`/`PageUpdateIn`, `RESERVED_PAGE_SLUGS`, `PROTECTED_NODE_TYPES`
- `api/tests/test_pages.py` (nuevo) — 16 tests, todos en verde

Frontend:
- `web/components/store/pageTree/` (nuevo, todo el renderer SSR: `TreeRenderer.jsx`, `registry.js`, nodos `Stack`/`TextNode`/`ImageNode`/`ProductGrid`, `breakpoints.js`, `responsiveStyle.js`, `locale.js`) — **todavía sin nodos `checkout_form`/`cart_summary`/`payment_widget`**, ver más abajo
- `web/app/[locale]/[pagina]/page.jsx` → renombrado a `web/app/[locale]/[slug]/page.jsx` — ahora consulta `Page` primero y cae a `Pagina` (sistema legado) si no hay match
- `web/components/admin/pageEditor/` (nuevo, Fase 2, con `@craftjs/core`: `craftTransform.js`, `nodeTypes.js`, `BreakpointContext.jsx`, `StyleFields.jsx`, `nodes/{Stack,TextNode,ImageNode,ProductGrid}.jsx` craft-aware, `Toolbox.jsx`, `SettingsPanel.jsx`, `HistoryBar.jsx`)
- `web/app/admin/editor-pagines/` (nuevo, Fase 2) — listado/alta de `Page` y el editor real por `[slug]` (canvas, estilo, SEO, desar esborrany/publicar). Nav añadido en `admin/layout.jsx`.
- `api/app/routers/figma.py` + `api/app/services/figma.py` + `api/app/schemas/figma.py` (nuevo, Fase 3+4) — OAuth (connect-init/connect/callback/status/disconnect) + import de estilos + import estructural (frames/import-jobs/apply). `api/tests/test_figma.py` (nuevo, 16 tests). `config.py`/`.env.example` con `FIGMA_CLIENT_ID`/`FIGMA_CLIENT_SECRET` (vacíos, sin credenciales reales todavía).
- `api/app/tasks/figma_import.py` (nuevo, Fase 4) — tarea Celery que mapea el árbol y descarga las imágenes a `/uploads`. Registrada en `celery_app.py`.
- `api/alembic/versions/f60f71b05e91_*.py` — migración de `figma_import_jobs.figma_node_id`, **ya aplicada en la BD de dev**.
- `web/app/admin/figma/page.jsx` (Fase 3+4) — conectar/desconectar, buscar estilos y aplicarlos al tema, buscar frames e importarlos como página. Nav añadido en `admin/layout.jsx`.
- `web/app/[locale]/page.jsx` (home) y `web/app/[locale]/cataleg/page.jsx` — comprueban `Page(slug="home"/"cataleg")` antes de su implementación de siempre. `web/components/store/pageTree/nodes/CatalogBrowse.jsx` (nuevo) + `CatalogFilters.jsx` (movido a `components/store/`, gana prop `basePath`) + `MobileFilterSheet.jsx` (gana prop `basePath`) + `TreeRenderer.jsx` (propaga `searchParams`/`basePath`). Lado editor: `CatalogBrowse.jsx` en `pageEditor/nodes/`, registrado en `nodeTypes.js`/`resolver.js`/`Toolbox.jsx`. `RESERVED_PAGE_SLUGS`/`RESERVED_SLUGS` ya no incluyen `cataleg`.
- `web/app/admin/editor-pagines/page.jsx` reorganizado: sección "Pàgines del sistema" (Home/Catàleg) + "Pàgines pròpies"; "Dissenyar" el Home construye el `draft_tree` a partir del `/admin/home-blocks` real. `pageEditor/StyleFields.jsx` gana tipografía + imatge de fons; `pageEditor/nodes/Stack.jsx` gana `align`/`justify`; nodos nuevos `Button.jsx`/`Spacer.jsx`/`HomeBlockNode.jsx` (en `pageTree/nodes/` y `pageEditor/nodes/`, registrados en ambos registries + `Toolbox.jsx` reorganizado en grupos "Elements"/"Blocs (llegat)"). `responsiveStyle.js` gana handlers `align`/`justify`/`height`. `collectLiveData.js` gana `treeHasHomeBlockNode`.

## Lo que sigue sin hacer dentro del concepto "checkout editable" (§3d)

El mecanismo de nodos protegidos (vocabulario + `requires_nodes` + validación 422 al publicar) ya está construido y probado, pero eso es solo la mitad backend. Todavía falta, y es deliberadamente el punto de mayor riesgo del documento (§6):
- Construir los componentes React `checkout_form`/`cart_summary`/`payment_widget` de verdad en `pageTree/nodes/`.
- Decidir cómo migrar `web/app/[locale]/checkout`/`carret` (hoy páginas Next.js hardcoded) a instancias reales de `Page`.
- La protección en el editor visual (no poder borrar el nodo en el canvas) — no aplica todavía porque no hay editor real en producción (eso es Fase 2).

No es parte de "cerrar la Fase 1" — se retoma junto a o después de la Fase 2.

## Prompt para pegar en una sesión nueva

```
Lee docs/ARQUITECTURA_DISENY_FIGMA.md y docs/CONTINUAR_DISENY_FIGMA.md para
el contexto completo del editor visual del storefront + import de Figma
(Fases 1 y 2 cerradas y confirmadas en vivo; Fases 3 y 4 construidas y
desplegadas pero SIN probar de verdad contra Figma real; home/catálogo ya
coexisten con el editor nuevo; el editor ganó tipografía/alineación/imagen
de fondo/botón/separador, un puente HomeBlockNode que reutiliza los 6
bloques viejos reales del tenant, y una ruta de previsualización real
(preview-pagina) que muestra el borrador con el aspecto exacto de la web
pública — dos bugs reales encontrados y arreglados por el camino (home
vacío por un try/catch mudo) — TODO VERIFICADO SOLO EN SERVIDOR
(curl/headless), el usuario todavía NO lo ha probado en el navegador,
incluido el botón "Previsualitzar" nuevo — sin commitear). Quiero [probar
en el navegador todo el bloque de páginas predefinidas + gestor de bloques
+ previsualización / abordar la ficha de producto (plantilla con datos en
vivo, mismo cuidado que checkout) / probar el flujo de Figma en vivo,
ahora que ya tengo las credenciales / empezar la Fase 5, migración real de
HomeBlock/Pagina] — confírmame antes de tocar código si hace falta
reconstruir algún contenedor de dev o tocar la BD, igual que en las
sesiones anteriores.
```
