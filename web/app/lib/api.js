// Único punto de acceso a la API. En SSR usa la red interna de docker;
// en el navegador, el path /api que enruta Caddy.
const BASE =
  typeof window === "undefined"
    ? process.env.API_INTERNAL_URL || "http://localhost:8000"
    : "/api";

export async function api(path, options = {}) {
  // En SSR, `BASE` apunta directo al contenedor `api` (sin pasar por
  // Caddy) — el Host que llegaría por defecto sería el del propio
  // contenedor ("api:8000"), no el dominio del tenant que está pidiendo
  // la página. El backend resuelve el tenant exactamente por ese header
  // (get_db, por Host) así que sin reenviarlo a mano cualquier fetch SSR
  // llegaba sin tenant válido — bug real, no solo de marca (ver plan).
  // No se puede fijar `Host` a mano (undici/Node lo gestiona la propia
  // conexión y lo ignora) — se manda en `X-Forwarded-Host` en su lugar,
  // que `get_db` ya prefiere sobre `Host` (api/app/database.py). Seguro:
  // el tráfico real de navegador pasa por Caddy, que sobreescribe este
  // header con el Host real antes de reenviarlo — no es falsificable
  // desde fuera, solo este contenedor lo controla de verdad.
  let hostHeader = {};
  if (typeof window === "undefined") {
    const { headers } = await import("next/headers");
    const incomingHost = (await headers()).get("host");
    if (incomingHost) hostHeader = { "X-Forwarded-Host": incomingHost };
  }
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...hostHeader, ...(options.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text();
    const error = new Error(`API ${res.status}: ${body}`);
    error.status = res.status;
    throw error;
  }
  return res.json();
}
