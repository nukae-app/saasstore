import type { ReactNode } from "react";
import { ActivityIndicator, Pressable, Text } from "react-native";

import { colors } from "../../lib/theme";

type Variant = "primary" | "secondary" | "destructive" | "outline";

const BG: Record<Variant, string> = {
  primary: "bg-primary",
  secondary: "bg-muted",
  destructive: "bg-destructive",
  outline: "bg-transparent border border-border",
};

const TEXT: Record<Variant, string> = {
  primary: "text-primary-foreground",
  secondary: "text-foreground",
  destructive: "text-destructive-foreground",
  outline: "text-foreground",
};

const SPINNER_COLOR: Record<Variant, string> = {
  primary: colors.primaryForeground,
  secondary: colors.foreground,
  destructive: colors.destructiveForeground,
  outline: colors.foreground,
};

export function Button({
  children,
  onPress,
  variant = "primary",
  disabled,
  loading,
  className,
}: {
  children: ReactNode;
  onPress?: () => void;
  variant?: Variant;
  disabled?: boolean;
  loading?: boolean;
  className?: string;
}) {
  const isDisabled = disabled || loading;
  return (
    <Pressable
      className={`rounded-button py-3 px-4 min-h-[44px] items-center justify-center ${BG[variant]} ${
        isDisabled ? "opacity-50" : ""
      } ${className ?? ""}`}
      onPress={onPress}
      disabled={isDisabled}
    >
      {loading ? (
        <ActivityIndicator color={SPINNER_COLOR[variant]} />
      ) : (
        <Text className={`font-sansSemibold text-base ${TEXT[variant]}`}>{children}</Text>
      )}
    </Pressable>
  );
}
