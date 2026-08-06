// Único punto de acceso a la API. En SSR usa la red interna de docker;
// en el navegador, el path /api que enruta Caddy.
const BASE =
  typeof window === "undefined"
    ? process.env.API_INTERNAL_URL || "http://localhost:8000"
    : "/api";

export async function api(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}
