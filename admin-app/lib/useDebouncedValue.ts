import { useEffect, useState } from "react";

/** Reutilizable en cualquier buscador de la app (TPV hoy, Catálogo/Compras
 * después) — no atado a ningún endpoint concreto. */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}
