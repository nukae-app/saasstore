/**
 * Fuente única de los tokens de diseño ("Soft Pro", ver
 * docs/ARQUITECTURA_APPS_NATIVAS.md) — identidad propia de la app de
 * admin, deliberadamente independiente del MD3/teal del admin web y de la
 * marca cálida de la tienda online.
 *
 * En CommonJS (no TS) a propósito: `tailwind.config.js` lo necesita vía
 * `require()` síncrono en tiempo de build (Node, no Metro) — un `.ts` no
 * es requireable ahí sin transpilar aparte. `lib/theme.ts` reexporta esto
 * mismo, tipado, para usarlo desde código de la app (sombras nativas,
 * mapeo de colores de estado, etc.). Cambiar un color: solo aquí.
 */
module.exports = {
  colors: {
    background: "#F8FAFC",
    foreground: "#0F172A",
    card: "#FFFFFF",
    cardForeground: "#0F172A",
    primary: "#1E3A5F",
    primaryForeground: "#FFFFFF",
    accent: "#059669",
    accentForeground: "#FFFFFF",
    muted: "#F1F5F9",
    mutedForeground: "#64748B",
    border: "#E4E7EB",
    destructive: "#DC2626",
    destructiveForeground: "#FFFFFF",
    warning: "#D97706",
    warningForeground: "#FFFFFF",
    ring: "#1E3A5F",
  },
  radius: {
    card: 16,
    button: 12,
    badge: 999,
  },
  fontFamily: {
    sans: "FiraSans_400Regular",
    sansMedium: "FiraSans_500Medium",
    sansSemibold: "FiraSans_600SemiBold",
    sansBold: "FiraSans_700Bold",
    mono: "FiraCode_400Regular",
    monoMedium: "FiraCode_500Medium",
    monoSemibold: "FiraCode_600SemiBold",
  },
};
