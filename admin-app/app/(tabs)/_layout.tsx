import MaterialCommunityIcons from "@expo/vector-icons/MaterialCommunityIcons";
import { Redirect, Tabs } from "expo-router";

import { useAuth } from "../../lib/auth";
import { colors } from "../../lib/theme";

export default function TabsLayout() {
  const { status } = useAuth();

  if (status !== "signedIn") {
    return <Redirect href="/login" />;
  }

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.mutedForeground,
        tabBarStyle: { backgroundColor: colors.card, borderTopColor: colors.border },
        tabBarLabelStyle: { fontFamily: "FiraSans_500Medium", fontSize: 12 },
      }}
    >
      <Tabs.Screen
        name="orders"
        options={{
          title: "Pedidos",
          tabBarIcon: ({ color, size }) => <MaterialCommunityIcons name="package-variant" color={color} size={size} />,
        }}
      />
      <Tabs.Screen
        name="tpv"
        options={{
          title: "TPV",
          tabBarIcon: ({ color, size }) => (
            <MaterialCommunityIcons name="point-of-sale" color={color} size={size} />
          ),
        }}
      />
      <Tabs.Screen
        name="compras"
        options={{
          title: "Compres",
          tabBarIcon: ({ color, size }) => <MaterialCommunityIcons name="truck-delivery" color={color} size={size} />,
        }}
      />
    </Tabs>
  );
}
