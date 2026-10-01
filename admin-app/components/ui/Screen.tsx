import type { ReactNode } from "react";
import { View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

/** Fondo + respeto de safe area (notch/status bar) consistente en toda la
 * app — nunca `pt-16` a ojo, siempre el inset real del dispositivo. */
export function Screen({ children, className }: { children: ReactNode; className?: string }) {
  const insets = useSafeAreaInsets();
  return (
    <View className={`flex-1 bg-background ${className ?? ""}`} style={{ paddingTop: insets.top }}>
      {children}
    </View>
  );
}
