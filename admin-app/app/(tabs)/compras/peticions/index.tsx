import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, FlatList, Pressable, Text, View } from "react-native";

import { ComprasSubNav } from "../../../../components/ComprasSubNav";
import { Button } from "../../../../components/ui/Button";
import { Card } from "../../../../components/ui/Card";
import { StatusBadge } from "../../../../components/ui/StatusBadge";
import { fetchPeticiones } from "../../../../lib/api";
import { useAuth } from "../../../../lib/auth";
import { colors } from "../../../../lib/theme";
import type { PeticionCliente } from "../../../../lib/types";

const ESTADO_LABEL: Record<string, string> = {
  pendent: "Pendent",
  pendent_acceptacio: "Esperant client",
  acceptada: "Acceptada",
  rebutjada: "Rebutjada",
  en_tramit: "En tràmit",
  reservada: "Reservada",
  recollida: "Recollida",
  caducada: "Caducada",
  cancelada: "Cancel·lada",
};

const TANCADES = new Set(["recollida", "cancelada", "rebutjada", "caducada"]);

function PeticionRow({ peticion, onPress }: { peticion: PeticionCliente; onPress: () => void }) {
  const disco = peticion.artista ? `${peticion.artista} — ${peticion.titulo}` : peticion.titulo ?? "Disc sense catalogar";
  return (
    <Pressable onPress={onPress}>
      <Card className="mx-4 mb-3">
        <View className="flex-row justify-between items-start">
          <View className="flex-1 pr-2">
            <Text className="font-sansMedium text-foreground">{peticion.user_nombre ?? peticion.user_email}</Text>
            <Text className="text-mutedForeground font-sans text-xs mt-0.5">{disco}</Text>
          </View>
          <StatusBadge status={peticion.status} label={ESTADO_LABEL[peticion.status] ?? peticion.status} />
        </View>
      </Card>
    </Pressable>
  );
}

export default function PeticionsList() {
  const router = useRouter();
  const { tenantSlug, accessToken } = useAuth();
  const [showTancades, setShowTancades] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["peticions", tenantSlug],
    queryFn: () => fetchPeticiones(tenantSlug as string, accessToken as string),
    enabled: !!tenantSlug && !!accessToken,
  });

  const peticions = (data ?? []).filter((p) => (showTancades ? true : !TANCADES.has(p.status)));

  return (
    <View className="flex-1 bg-background">
      <View className="flex-row justify-between items-center px-4 pt-2 pb-3 border-b border-border">
        <Text className="text-xl font-sansBold text-foreground">Compres</Text>
        <Button className="min-h-0 py-2 px-3" onPress={() => router.push("/compras/peticions/nova")}>
          + Nova
        </Button>
      </View>

      <ComprasSubNav active="peticions" />

      <View className="flex-row gap-2 px-4 py-3">
        {[
          { value: false, label: "Actives" },
          { value: true, label: "Totes" },
        ].map((f) => (
          <Pressable
            key={f.label}
            onPress={() => setShowTancades(f.value)}
            className={`rounded-badge px-3 py-1.5 border ${showTancades === f.value ? "bg-primary border-primary" : "bg-card border-border"}`}
          >
            <Text className={`font-sansMedium text-sm ${showTancades === f.value ? "text-primary-foreground" : "text-foreground"}`}>
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
        data={peticions}
        keyExtractor={(p) => p.id}
        renderItem={({ item }) => (
          <PeticionRow peticion={item} onPress={() => router.push(`/compras/peticions/${item.id}`)} />
        )}
        contentContainerClassName="pb-8"
        ListEmptyComponent={!isLoading ? <Text className="p-4 text-mutedForeground font-sans">Cap petició.</Text> : null}
      />
    </View>
  );
}
