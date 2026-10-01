import { useQuery } from "@tanstack/react-query";
import { Redirect, useRouter } from "expo-router";
import { ActivityIndicator, FlatList, Pressable, RefreshControl, Text, View } from "react-native";

import { Card } from "../../../components/ui/Card";
import { Screen } from "../../../components/ui/Screen";
import { StatusBadge } from "../../../components/ui/StatusBadge";
import { fetchOrders } from "../../../lib/api";
import { useAuth } from "../../../lib/auth";
import { colors } from "../../../lib/theme";
import type { OrderSummary } from "../../../lib/types";

function OrderRow({ order, onPress }: { order: OrderSummary; onPress: () => void }) {
  return (
    <Pressable onPress={onPress}>
      <Card className="mx-4 mb-3 flex-row justify-between items-center">
        <View className="flex-1 pr-3">
          <Text className="font-sansMedium text-foreground">{order.email}</Text>
          <Text className="text-mutedForeground font-sans text-sm">
            {new Date(order.created_at).toLocaleString()}
          </Text>
        </View>
        <View className="items-end gap-1.5">
          <Text className="font-monoSemibold text-foreground text-base">{order.total} €</Text>
          <StatusBadge status={order.status} label={order.status} />
        </View>
      </Card>
    </Pressable>
  );
}

export default function Orders() {
  const router = useRouter();
  const { status, tenantSlug, accessToken, signOut } = useAuth();

  const { data, isLoading, isError, refetch, isRefetching } = useQuery({
    queryKey: ["orders", tenantSlug],
    queryFn: () => fetchOrders(tenantSlug as string, accessToken as string),
    enabled: status === "signedIn" && !!tenantSlug && !!accessToken,
  });

  if (status !== "signedIn") {
    return <Redirect href="/login" />;
  }

  async function onSignOut() {
    await signOut();
    router.replace("/login");
  }

  return (
    <Screen>
      <View className="flex-row justify-between items-center px-4 pb-3 border-b border-border">
        <View>
          <Text className="text-xl font-sansBold text-foreground">Pedidos</Text>
          <Text className="text-mutedForeground font-mono text-sm">{tenantSlug}</Text>
        </View>
        <Pressable onPress={onSignOut} hitSlop={8}>
          <Text className="text-destructive font-sansMedium">Tancar sessió</Text>
        </Pressable>
      </View>

      {isLoading && (
        <View className="py-10 items-center">
          <ActivityIndicator color={colors.primary} />
        </View>
      )}
      {isError && (
        <Text className="p-4 text-destructive font-sans">No s&apos;han pogut carregar els pedidos.</Text>
      )}

      <FlatList
        data={data ?? []}
        keyExtractor={(order) => order.id}
        renderItem={({ item }) => <OrderRow order={item} onPress={() => router.push(`/orders/${item.id}`)} />}
        contentContainerClassName="pt-4 pb-8"
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={colors.primary} />}
        ListEmptyComponent={
          !isLoading ? <Text className="p-4 text-mutedForeground font-sans">Sense pedidos.</Text> : null
        }
      />
    </Screen>
  );
}
