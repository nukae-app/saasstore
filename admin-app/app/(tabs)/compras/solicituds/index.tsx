import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, FlatList, Pressable, Text, View } from "react-native";

import { ComprasSubNav } from "../../../../components/ComprasSubNav";
import { Button } from "../../../../components/ui/Button";
import { Card } from "../../../../components/ui/Card";
import { StatusBadge } from "../../../../components/ui/StatusBadge";
import { fetchSolicitudes } from "../../../../lib/api";
import { useAuth } from "../../../../lib/auth";
import { colors } from "../../../../lib/theme";
import type { SolicitudCompra } from "../../../../lib/types";

const ESTADO_LABEL: Record<string, string> = {
  oberta: "Oberta",
  resolta: "Resolta",
  cancelada: "Cancel·lada",
};

function SolicitudRow({ solicitud, onPress }: { solicitud: SolicitudCompra; onPress: () => void }) {
  const pendents = solicitud.lineas.filter((l) => !l.resuelta).length;
  return (
    <Pressable onPress={onPress}>
      <Card className="mx-4 mb-3">
        <View className="flex-row justify-between items-start">
          <View className="flex-1 pr-2">
            <Text className="font-sansMedium text-foreground font-mono">{solicitud.numero}</Text>
            <Text className="text-mutedForeground font-sans text-xs mt-0.5">
              {solicitud.lineas.length} línies
              {pendents > 0 ? ` · ${pendents} pendents` : ""}
            </Text>
          </View>
          <StatusBadge status={solicitud.estado} label={ESTADO_LABEL[solicitud.estado] ?? solicitud.estado} />
        </View>
      </Card>
    </Pressable>
  );
}

export default function SolicitudsList() {
  const router = useRouter();
  const { tenantSlug, accessToken } = useAuth();
  const [filter, setFilter] = useState<string | undefined>("oberta");

  const { data, isLoading } = useQuery({
    queryKey: ["solicituds", tenantSlug, filter],
    queryFn: () => fetchSolicitudes(tenantSlug as string, accessToken as string, filter),
    enabled: !!tenantSlug && !!accessToken,
  });

  return (
    <View className="flex-1 bg-background">
      <View className="flex-row justify-between items-center px-4 pt-2 pb-3 border-b border-border">
        <Text className="text-xl font-sansBold text-foreground">Compres</Text>
        <Button className="min-h-0 py-2 px-3" onPress={() => router.push("/compras/solicituds/pool")}>
          Pool
        </Button>
      </View>

      <ComprasSubNav active="solicituds" />

      <View className="flex-row gap-2 px-4 py-3">
        {[
          { value: "oberta", label: "Obertes" },
          { value: "resolta", label: "Resoltes" },
          { value: undefined, label: "Totes" },
        ].map((f) => (
          <Pressable
            key={f.label}
            onPress={() => setFilter(f.value)}
            className={`rounded-badge px-3 py-1.5 border ${filter === f.value ? "bg-primary border-primary" : "bg-card border-border"}`}
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
        data={data?.results ?? []}
        keyExtractor={(s) => s.id}
        renderItem={({ item }) => (
          <SolicitudRow solicitud={item} onPress={() => router.push(`/compras/solicituds/${item.id}`)} />
        )}
        contentContainerClassName="pb-8"
        ListEmptyComponent={!isLoading ? <Text className="p-4 text-mutedForeground font-sans">Cap sol·licitud.</Text> : null}
      />
    </View>
  );
}
