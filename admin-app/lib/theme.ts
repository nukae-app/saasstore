import { Platform } from "react-native";

// Reexporta theme.tokens.js (fuente única, ver ese archivo) tipado para
// usarlo en código de la app — colores como clases de NativeWind
// (`bg-primary`, `text-accent`...) casi siempre; este módulo es para lo
// que Tailwind no cubre bien en nativo: sombras reales y el mapeo de
// estado→color semántico.
// eslint-disable-next-line @typescript-eslint/no-var-requires
const tokens = require("../theme.tokens.js") as {
  colors: Record<string, string>;
  radius: Record<string, number>;
  fontFamily: Record<string, string>;
};

export const colors = tokens.colors;
export const radius = tokens.radius;
export const fontFamily = tokens.fontFamily;

/** Sombra suave ("Soft Pro") — RN no interpreta `shadow-*` de Tailwind de
 * forma fiable en las dos plataformas a la vez, así que las tarjetas la
 * aplican como `style`, no como className. */
export const cardShadow = Platform.select({
  ios: {
    shadowColor: colors.foreground,
    shadowOpacity: 0.08,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
  },
  android: { elevation: 3 },
  default: {},
});

const STATUS_COLOR: Record<string, "accent" | "destructive" | "warning" | "muted"> = {
  pagado: "accent",
  pagat: "accent",
  enviado: "accent",
  entregado: "accent",
  cancelado: "destructive",
  cancelat: "destructive",
  pendiente: "warning",
  pendent: "warning",
  pendiente_pago: "warning",
};

/** A qué token de color semántico corresponde un `Order.status`/similar —
 * un vocabulario cerrado, no texto libre (mismo criterio que ya usa el
 * backend para `catalog_provider`/`product_archetype`), con `muted` como
 * fallback neutro para cualquier valor no mapeado explícitamente. */
export function statusColorToken(status: string): "accent" | "destructive" | "warning" | "muted" {
  return STATUS_COLOR[status.toLowerCase()] ?? "muted";
}
