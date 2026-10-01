import type { ReactNode } from "react";
import { Text, TextInput, View, type TextInputProps } from "react-native";

import { colors } from "../../lib/theme";

export function Input({ className, ...props }: TextInputProps & { className?: string }) {
  return (
    <TextInput
      // `className` va DESPUÉS en el string (no en JSX): si un caller pasa
      // el suyo, se añade a las clases base en vez de sustituirlas — un
      // spread de `props` con `className` propio tras el className base
      // lo habría reemplazado entero (bug real, encontrado al usarlo en
      // app/(tabs)/tpv.tsx con `className="w-24 text-right"`).
      className={`border border-border rounded-button px-3 py-2.5 text-base font-sans text-foreground bg-card min-h-[44px] ${className ?? ""}`}
      placeholderTextColor={colors.mutedForeground}
      {...props}
    />
  );
}

/** Envoltorio label + input — el patrón que repiten todos los formularios
 * de la app (login hoy, altas de catálogo/compras después). */
export function FormField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <View className="gap-1.5">
      <Text className="text-sm font-sansMedium text-foreground">{label}</Text>
      {children}
    </View>
  );
}
