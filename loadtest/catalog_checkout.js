// Test de càrrega amb k6 (https://k6.io) per a Ultra-Local Records.
//
// Dos escenaris, amb risc molt diferent:
//
//   - "browse" (per defecte): només lectura (GET /catalog, GET /catalog/releases/{id}).
//     Segur contra producció: no toca estoc ni crea res.
//
//   - "checkout": afegeix un ítem al carret i fa POST /checkout/start, que
//     RESERVA de veritat un exemplar durant 20 min (veure
//     api/app/services/reservations.py). NO arriba a /checkout/confirm, així
//     que no es crea cap comanda, però mentre dura la reserva aquell disc
//     desapareix de la venda per a un client real. NOMÉS activar-lo contra
//     producció amb pocs VUs, fora d'hores, i sabent quins ítems queden
//     reservats (es poden alliberar manualment o esperar que caduqui als 20 min).
//
// Ús:
//   Local (segur, tot inclòs):
//     k6 run -e BASE_URL=http://localhost/api catalog_checkout.js
//
//   Producció, només lectura (recomanat per a la primera prova real):
//     k6 run -e BASE_URL=https://labotigaaquesta.com/api \
//            -e VUS=5 -e DURATION=1m catalog_checkout.js
//
//   Producció, amb checkout — fer-ho fora d'hores i amb pocs VUs:
//     k6 run -e BASE_URL=https://labotigaaquesta.com/api -e SCENARIO=checkout \
//            -e VUS=2 -e DURATION=30s catalog_checkout.js

import http from "k6/http";
import { check, sleep } from "k6";
import { Trend } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://localhost/api";
const SCENARIO = __ENV.SCENARIO || "browse"; // "browse" | "checkout"
const VUS = parseInt(__ENV.VUS || "10", 10);
const DURATION = __ENV.DURATION || "1m";

const reserveDuration = new Trend("checkout_start_duration");

export const options = {
  scenarios: {
    default: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "15s", target: VUS }, // ramp-up suau, no un cop sec
        { duration: DURATION, target: VUS },
        { duration: "10s", target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<800"],
  },
};

function pickAvailableItem() {
  const res = http.get(`${BASE_URL}/catalog?page_size=50`, { tags: { name: "catalog_list" } });
  check(res, { "catalog 200": (r) => r.status === 200 });
  if (res.status !== 200) return null;
  const body = res.json();
  const withStock = (body.results || []).filter((r) => (r.items || []).some((i) => i.status === "disponible"));
  if (withStock.length === 0) return null;
  const release = withStock[Math.floor(Math.random() * withStock.length)];
  const item = release.items.find((i) => i.status === "disponible");
  return { release, item };
}

function browseIteration() {
  // Llistat amb filtres variats, com faria un client remenant el catàleg.
  const pages = [
    `${BASE_URL}/catalog?page=${1 + Math.floor(Math.random() * 3)}&page_size=24`,
    `${BASE_URL}/catalog?rang=A-D`,
    `${BASE_URL}/catalog?formato=Vinilo`,
  ];
  const listRes = http.get(pages[Math.floor(Math.random() * pages.length)], { tags: { name: "catalog_list" } });
  check(listRes, { "catalog list 200": (r) => r.status === 200 });

  const body = listRes.status === 200 ? listRes.json() : null;
  const results = body && body.results ? body.results : [];
  if (results.length > 0) {
    const pick = results[Math.floor(Math.random() * results.length)];
    const detailRes = http.get(`${BASE_URL}/catalog/releases/${pick.id}`, { tags: { name: "release_detail" } });
    check(detailRes, { "release detail 200": (r) => r.status === 200 });
  }

  sleep(Math.random() * 2); // simula temps de lectura entre clics
}

function checkoutIteration() {
  const picked = pickAvailableItem();
  if (!picked) {
    // No hi ha estoc disponible ara mateix (p.ex. altres VUs ja ho han reservat tot).
    sleep(1);
    return;
  }

  const jar = http.cookieJar();

  const addRes = http.post(
    `${BASE_URL}/cart/items`,
    JSON.stringify({ item_id: picked.item.item_id }),
    { headers: { "Content-Type": "application/json" }, tags: { name: "cart_add" } }
  );
  check(addRes, { "cart add 201": (r) => r.status === 201 });
  if (addRes.status !== 201) return;

  const startRes = http.post(`${BASE_URL}/checkout/start`, null, { tags: { name: "checkout_start" } });
  reserveDuration.add(startRes.timings.duration);
  check(startRes, {
    "checkout start 200 o 409 (ja reservat per un altre VU)": (r) => r.status === 200 || r.status === 409,
  });

  // Deliberadament NO cridem /checkout/confirm: no volem crear comandes
  // reals. L'ítem quedarà "reservado" fins que caduqui (20 min) o
  // s'alliberi manualment.
  sleep(Math.random() * 2);
}

export default function () {
  if (SCENARIO === "checkout") {
    checkoutIteration();
  } else {
    browseIteration();
  }
}
