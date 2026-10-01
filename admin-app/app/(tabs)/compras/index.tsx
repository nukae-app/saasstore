import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, FlatList, Pressable, RefreshControl, Text, View } from "react-native";

import { ComprasSubNav } from "../../../components/ComprasSubNav";
import { Button } from "../../../components/ui/Button";
import { Card } from "../../../components/ui/Card";
import { StatusBadge } from "../../../components/ui/StatusBadge";
import { fetchComandas } from "../../../lib/api";
import { useAuth } from "../../../lib/auth";
import { colors } from "../../../lib/theme";
import type { Comanda } from "../../../lib/types";

const STATUS_LABEL: Record<string, string> = {
  esborrany: "Esborrany",
  enviada: "Enviada",
  rebuda_parcial: "Rebuda parcial",
  rebuda: "Rebuda",
  cancelada: "Cancel·lada",
};

const FILTERS: { value: string | undefined; label: string }[] = [
  { value: undefined, label: "Actives" },
  { value: "rebuda", label: "Rebudes" },
  { value: "cancelada", label: "Cancel·lades" },
];

function ComandaRow({ comanda, onPress }: { comanda: Comanda; onPress: () => void }) {
  const pendents = comanda.lineas.reduce((s, l) => s + (l.quantity - l.received_quantity), 0);
  return (
    <Pressable onPress={onPress}>
      <Card className="mx-4 mb-3">
        <View className="flex-row justify-between items-start">
          <View className="flex-1 pr-2">
            <Text className="font-sansMedium text-foreground">{comanda.proveedor_nombre}</Text>
            <Text className="text-mutedForeground font-mono text-xs mt-0.5">
              {comanda.order_number ?? comanda.id.slice(0, 8)}
            </Text>
          </View>
          <StatusBadge status={comanda.status} label={STATUS_LABEL[comanda.status] ?? comanda.status} />
        </View>
        {pendents > 0 && comanda.status !== "cancelada" && (
          <Text className="text-warning font-sans text-xs mt-2">{pendents} unitats pendents de rebre</Text>
        )}
      </Card>
    </Pressable>
  );
}

export default function ComandesList() {
  const router = useRouter();
  const { tenantSlug, accessToken } = useAuth();
  const [filter, setFilter] = useState<string | undefined>(undefined);

  // "Actives" no es un status del backend: se filtran las canceladas fuera
  // en cliente para no tener que pedir tres veces (esborrany+enviada+
  // rebuda_parcial+rebuda) — el backend solo filtra por un único status.
  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ["comandas", tenantSlug, filter],
    queryFn: () => fetchComandas(tenantSlug as string, accessToken as string, filter),
    enabled: !!tenantSlug && !!accessToken,
  });

  const comandas = (data ?? []).filter((c) => (filter ? true : c.status !== "cancelada"));

  return (
    <View className="flex-1 bg-background">
      <View className="flex-row justify-between items-center px-4 pt-2 pb-3 border-b border-border">
        <Text className="text-xl font-sansBold text-foreground">Compres</Text>
        <Button className="min-h-0 py-2 px-3" onPress={() => router.push("/compras/nova")}>
          + Nova
        </Button>
      </View>

      <ComprasSubNav active="comandes" />

      <View className="flex-row gap-2 px-4 py-3">
        {FILTERS.map((f) => (
          <Pressable
            key={f.label}
            onPress={() => setFilter(f.value)}
            className={`rounded-badge px-3 py-1.5 border ${
              filter === f.value ? "bg-primary border-primary" : "bg-card border-border"
            }`}
          >
            <Text className={`font-sansMedium text-sm ${filter === f.value ? "text-primary-foreground" : "text-foreground"}`}>
              {f.label}
            </Text>
          </Pressable>
        ))}
      </View>

      {isLoading && (
        <View className="py-10 items-center">
          <ActivityIndicator color={colors.primary} />
        </View>
      )}

      <FlatList
        data={comandas}
        keyExtractor={(c) => c.id}
        renderItem={({ item }) => <ComandaRow comanda={item} onPress={() => router.push(`/compras/${item.id}`)} />}
        contentContainerClassName="pb-8"
        refreshControl={<RefreshControl refreshing={isFetching && !isLoading} onRefresh={refetch} tintColor={colors.primary} />}
        ListEmptyComponent={!isLoading ? <Text className="p-4 text-mutedForeground font-sans">Cap comanda.</Text> : null}
      />
    </View>
  );
}
