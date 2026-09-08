# Admin panel — design brief for Stitch

## What this is

A multi-tenant SaaS platform for independent local shops (records today at Ultra-Local Records in Poblenou/Barcelona, floristry as a second vertical, more planned). Each tenant gets a public storefront *and* a real back-office/ERP — this brief is about the **back-office/admin panel**, not the storefront.

## Stack

- **Next.js 16** (App Router), **React 19**
- **Tailwind CSS v4**, CSS-first theme (tokens declared in `@theme`/`:root` inside `web/app/globals.css` — there is no `tailwind.config.js`)
- Component layer: shadcn/ui-style primitives (Radix UI + `class-variance-authority`) in `web/components/ui/` — Button, Card, Table, Badge, Dialog, Select, Tabs, Sheet, etc.
- Icons: `lucide-react`
- i18n: `next-intl`, Catalan primary / Spanish secondary

## What the admin panel is (Operate mode)

Internal back-office for the 1-2 people running a shop day to day — their actual workday tool, used for hours at a time, not a marketing surface. Scanability, consistency, and native dashboard conventions outrank decorative expression, but it still needs craft: per this project's product principles, "back-office/accounting surfaces need the same craft as the storefront, because tenants run their whole business through them." It must also generalize across verticals — nav labels already adapt per tenant (e.g. "Discos" vs "Productes"), so avoid baking vinyl-specific imagery into shared admin chrome.

## Screens that exist today (~30 routes under `/admin`)

- **Dashboard** — overview/home
- **Catàleg** — catalog/stock (`catalogo`), tags (`etiquetes`), offers (`ofertes`), coupons (`cupons`), web sales (`vendes-web`)
- **ERP / operations** — point of sale (`tpv`), purchase requests (`peticions`), subscriptions/record club (`subscripcions`), delivery notes (`albarans`), Discogs sync (`discogs-sync`)
- **Compres** — supplier purchases (`compras`), suppliers (`proveidors`)
- **Comptabilitat (accounting)** — chart of accounts (`pla-comptes`), bank (`banc`), expenses (`despeses`), VAT (`iva`), margins (`marges`), cash flow (`flux-caixa`), P&L/result (`resultat`), assets (`actius`), budgets (`pressupostos`), ledgers (`llibres`)
- **CMS** — blog, agenda (events), pages (`pagines`), site design (`disseny-web`), newsletter
- **Platform** — users (`usuaris`), settings (`configuracio`)

The accounting group in particular is table-heavy and needs real density.

## Current visual system (storefront — admin does *not* follow this yet)

- **Palette:** near-black primary (`#171717`) on warm cream background (`#faf9f6`), white cards, soft neutral grays (`#f2f2f2` bg / `#757575` muted text), red (`#ef4444`) reserved for destructive actions and sale pricing, amber for club/maintenance banners.
- **Typography:** Bodoni Moda (serif, display/headlines) + Hanken Grotesk (sans, body/UI) + Space Mono (labels, eyebrows, receipt/ticket printouts).
- **Shape:** large radii (16–32px on cards, fully pill-shaped buttons and inputs), soft diffuse shadows (never hard-edged), thin 1px dividers instead of heavy borders.
- **Signature motifs:** a literal vinyl-record SVG placeholder, a spinning "now playing" badge, grayscale→color image hover treatment.

## Current admin state — the gap

Admin screens already reuse the same shadcn/ui primitives and the same CSS token layer (colors, radius) as the storefront, but apply none of the brand voice above: no serif, no mono for data, a generic icon-sidebar dashboard that could belong to any SaaS template.

## What to ask Stitch for

A design direction for the admin panel that:

1. Reuses the existing token layer (colors, radius, shadow variables already defined in `globals.css`) as its base, rather than introducing a competing palette.
2. Introduces enough of the brand voice — maybe serif for section headers, mono for figures/data — that it stops reading as an anonymous admin template, without compromising density.
3. Prioritizes information density and scanability for the accounting/table-heavy screens over decorative expression.
4. Stays vertical-agnostic in shared admin chrome (no record/vinyl-specific imagery baked into navigation, headers, etc. — that belongs on the storefront only).
