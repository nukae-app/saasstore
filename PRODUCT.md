# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Three distinct primary users, in three different surfaces of the same platform:

- **Shop end-customers.** People browsing and buying from a tenant's public storefront (today: vinyl records at Ultra-Local Records, a real Poblenou/Barcelona shop; tomorrow: other niche goods like flowers). Catalan-primary, Spanish-secondary, mostly local/regional. They also read the tenant's blog and agenda — the storefront is half shop, half community, not a generic marketplace.
- **Tenant operators/admins.** The people running an individual shop day to day (currently Ultra-Local Records' two operators) through the admin/back-office panel: catalog and stock, purchases, in-store POS (TPV), accounting (comptabilitat, marges, flux de caixa, IVA), suppliers, orders. For them the platform is effectively their whole business's operating system, not just a webshop admin.
- **Platform superadmin.** Whoever manages the SaaS itself: onboarding tenants, defining verticals, billing plans (via Revolut), platform-wide admins, and audit — across all tenants and verticals at once.

## Product Purpose

Gives independent, niche local retail shops an online storefront with a community layer (blog/agenda), plus a real back-office/ERP (stock, purchases, point-of-sale, accounting) — delivered as a multi-tenant SaaS so the same platform can be sold to other shops beyond the flagship one. Success for a shop is a working online sales channel plus a back office it can actually run the business on; success for the platform is onboarding additional tenants and verticals without forking the codebase per shop type.

## Positioning

Not a generic e-commerce/webshop builder: the platform is built "vertical-first" around how real niche shops actually operate, not around a lowest-common-denominator product model. The flagship vertical (records) models stock the way a real record shop needs to — unique secondhand copies with individual grading vs. aggregated identical new stock, Discogs used only to enrich/seed a listing rather than as the catalog of record — and ships with genuine back-office depth (accounting, margins, cash flow) rather than a bolted-on afterthought. New verticals (floristry today, more later) extend a shared Core (auth, cart, checkout, orders, payments, purchasing, POS, accounting, CMS) instead of duplicating it, so the platform can credibly serve very different shop types without becoming generic.

## Operating Context

- Each tenant runs a physical shop plus this online storefront; the flagship tenant also lists on Discogs and needs its web and Discogs stock to stay in sync.
- In-store point-of-sale (TPV) sales and Discogs sales both have to reconcile against the same stock as web sales.
- Tenant admins work inside a back office that includes real accounting modules (comptabilitat, marges, flux de caixa, IVA, proveïdors/compres), not just order management.
- The platform superadmin operates a separate control plane (tenants, verticals, plans/billing, platform admins, audit log) with no visual identity of its own yet.
- UI language is Catalan (primary) and Spanish (secondary) for shop-facing and tenant-admin surfaces; the underlying data model is being migrated to English-canonical names as part of an in-progress Core/Vertical architecture refactor (`docs/ARQUITECTURA_CORE_VERTICAL.md`) — this is a backend/data convention, not a UI language change.

## Capabilities and Constraints

- **Vertical-specific stock modeling is load-bearing, not incidental.** Secondhand items are unique physical copies (their own grading, quantity always 1, never resold twice); new items are aggregated stock (one row = N identical units, weighted-average cost on reorder). This distinction must survive any refactor.
- **Atomic stock reservation is a hard constraint.** Reservations use conditional `UPDATE` statements (never SELECT-then-UPDATE) to avoid race conditions during checkout; this is one of the most delicate, well-tested parts of the system.
- **Orders are immutable snapshots.** Historical order line prices and shipping addresses never change even if the catalog or address book changes later.
- **Auth is passwordless** (Google OIDC + magic link), with guest checkout supported (orders can exist without a user account, for GDPR-safe anonymization while retaining legally-required invoice history).
- **Core/Vertical architecture is mid-refactor, not finished.** Today's code has "vinyl as the base, floristry as an add-on" rather than a symmetric Core+Vertical split; the target design (per the architecture doc) is a genuine shared Core with each vertical (records, floristry, future ones) extending it via 1:1 tables. Design work on admin/back-office surfaces should anticipate this split rather than deepen today's vinyl-as-default asymmetry.
- **Undecided:** how many verticals beyond records and floristry are planned near-term. The API is still titled "Ultra-Local Records API" internally, a name that predates the SaaS pivot — harmless (not user-facing), but a sign the pivot isn't fully reflected everywhere in the codebase.

## Brand Commitments

- **Platform brand: "NukaeStore."** Confirmed by a real, already-built marketing site at `/nukaestore` ("la plataforma para tiendas de barrio con carácter") — this is the platform's own product identity, separate from any tenant. Corrects an earlier assumption in this file that no platform-level brand existed yet.
- "Ultra-Local Records" name and logo (`web/public/ultralocal-logo-tiquet.png`) are confirmed for the flagship records tenant's storefront — a tenant identity, distinct from the NukaeStore platform brand above.
- No confirmed brand identity yet for the floristry vertical's flagship tenant (if any exists yet beyond a data model).

## Evidence on Hand

- Real catalog data: the flagship tenant's initial catalog was imported from a Google Sheet that is itself a Discogs export.
- Real logo asset for Ultra-Local Records (see above); no equivalent asset exists yet for other tenants/verticals.
- Real billing infrastructure exists (superadmin Plans screen: name, price, currency, billing period, Revolut plan/variation IDs) — this is functioning SaaS billing, not a mockup.
- No customer testimonials, case studies, or press exist; do not fabricate any for this product.

## Product Principles

1. Model each vertical the way that business actually works (grading vs. aggregated stock, unique flower batches, etc.) — never flatten to a generic "product with quantity" shortcut for the sake of uniformity.
2. Core is shared; verticals extend it. A feature that any niche shop would need (auth, cart, checkout, accounting, POS) belongs in Core; anything vertical-specific extends it without leaking into shared tables/screens.
3. The tenant admin is an operator's real workday, not just order management — back-office/accounting surfaces need the same craft as the storefront, because tenants run their whole business through them.
4. The storefront is half shop, half community — retain the blog/agenda spirit per tenant rather than defaulting to a generic e-commerce template look.
5. Data truth over time is non-negotiable: snapshots, atomic reservations, and historical accuracy are constraints design must never route around (e.g. never imply a recalculated historical price/total in the UI).
