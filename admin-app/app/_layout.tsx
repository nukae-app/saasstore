import "../global.css";

// Imports directos al fichero de cada peso, no al índice del paquete: el
// índice de `@expo-google-fonts/*` reexporta las 9 variantes de la
// familia entera — importar de ahí hace que Metro empaquete los .ttf de
// TODOS los pesos (~6MB de más), aunque `useFonts` solo use 4. Con la
// ruta directa, cada import es exactamente un asset.
import FiraCode_400Regular from "@expo-google-fonts/fira-code/400Regular/FiraCode_400Regular.ttf";
import FiraCode_500Medium from "@expo-google-fonts/fira-code/500Medium/FiraCode_500Medium.ttf";
import FiraCode_600SemiBold from "@expo-google-fonts/fira-code/600SemiBold/FiraCode_600SemiBold.ttf";
import FiraSans_400Regular from "@expo-google-fonts/fira-sans/400Regular/FiraSans_400Regular.ttf";
import FiraSans_500Medium from "@expo-google-fonts/fira-sans/500Medium/FiraSans_500Medium.ttf";
import FiraSans_600SemiBold from "@expo-google-fonts/fira-sans/600SemiBold/FiraSans_600SemiBold.ttf";
import FiraSans_700Bold from "@expo-google-fonts/fira-sans/700Bold/FiraSans_700Bold.ttf";
import { useFonts } from "expo-font";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { ActivityIndicator, View } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { AuthProvider } from "../lib/auth";
import { colors } from "../lib/theme";

const queryClient = new QueryClient();

export default function RootLayout() {
  const [fontsLoaded] = useFonts({
    FiraSans_400Regular,
    FiraSans_500Medium,
    FiraSans_600SemiBold,
    FiraSans_700Bold,
    FiraCode_400Regular,
    FiraCode_500Medium,
    FiraCode_600SemiBold,
  });

  if (!fontsLoaded) {
    return (
      <View className="flex-1 items-center justify-center bg-background">
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }

  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <StatusBar style="dark" />
          <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.background } }} />
        </AuthProvider>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}
