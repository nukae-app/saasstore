import { Text, View } from "react-native";

import { statusColorToken } from "../../lib/theme";

const BG = {
  accent: "bg-accent/15",
  destructive: "bg-destructive/15",
  warning: "bg-warning/15",
  muted: "bg-muted",
} as const;

const TEXT = {
  accent: "text-accent",
  destructive: "text-destructive",
  warning: "text-warning",
  muted: "text-mutedForeground",
} as const;

/** Traduce un `status` de negocio (pedido, venta...) a un token semántico
 * cerrado (`lib/theme.ts::statusColorToken`) — nunca color a ojo por
 * pantalla, y nunca solo color como única señal (siempre va con el texto
 * del propio estado, ver `color-not-only`). */
export function StatusBadge({ status, label }: { status: string; label: string }) {
  const token = statusColorToken(status);
  return (
    <View className={`rounded-badge px-2.5 py-1 ${BG[token]}`}>
      <Text className={`text-xs font-sansSemibold uppercase tracking-wide ${TEXT[token]}`}>{label}</Text>
    </View>
  );
}
