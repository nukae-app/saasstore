import type { ReactNode } from "react";
import { View, type StyleProp, type ViewStyle } from "react-native";

import { cardShadow } from "../../lib/theme";

/** Tarjeta "Soft Pro": esquinas redondeadas + sombra suave real (no
 * `shadow-*` de Tailwind — RN no la traduce de forma fiable en las dos
 * plataformas), ver `lib/theme.ts::cardShadow`. */
export function Card({
  children,
  className,
  style,
}: {
  children: ReactNode;
  className?: string;
  style?: StyleProp<ViewStyle>;
}) {
  return (
    <View
      className={`bg-card rounded-card border border-border p-4 ${className ?? ""}`}
      style={[cardShadow, style]}
    >
      {children}
    </View>
  );
}
