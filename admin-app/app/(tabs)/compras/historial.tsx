import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";

import { ComprasSubNav } from "../../../components/ComprasSubNav";
import { Button } from "../../../components/ui/Button";
import { Card } from "../../../components/ui/Card";
import { Input } from "../../../components/ui/Input";
import { Screen } from "../../../components/ui/Screen";
import {
  ApiError,
  addToPool,
  fetchConfigPublic,
  fetchHistorialLineas,
  fetchHistorialResum,
} from "../../../lib/api";
import { useAuth } from "../../../lib/auth";
import { colors } from "../../../lib/theme";
import { useDebouncedValue } from "../../../lib/useDebouncedValue";
import type { HistorialCompraLinea } from "../../../lib/types";

export default function Historial() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { tenantSlug, accessToken } = useAuth();

  const [query, setQuery] = useState("");
  const debouncedQuery = useDebouncedValue(query, 300);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [selection, setSelection] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: config } = useQuery({
    queryKey: ["config-public", tenantSlug],
    queryFn: () => fetchConfigPublic(tenantSlug as string, accessToken as string),
    enabled: !!tenantSlug && !!accessToken,
    staleTime: 5 * 60 * 1000,
  });
  const isRecordsVertical = config?.vertical === "records";

  const { data: resum, isLoading } = useQuery({
    queryKey: ["historial-resum", tenantSlug, debouncedQuery],
    queryFn: () => fetchHistorialResum(tenantSlug as string, accessToken as string, debouncedQuery || undefined),
    enabled: !!tenantSlug && !!accessToken && isRecordsVertical,
  });

  const { data: lineas, isFetching: lineasFetching } = useQuery({
    queryKey: ["historial-lineas", tenantSlug, expandedId, debouncedQuery],
    queryFn: () =>
      fetchHistorialLineas(tenantSlug as string, accessToken as string, {
        proveedor_id: expandedId as string,
        q: debouncedQuery || undefined,
      }),
    enabled: !!tenantSlug && !!accessToken && !!expandedId,
  });

  function toggleExpand(proveedorId: string) {
    setSelection({});
    setError(null);
    setExpandedId((prev) => (prev === proveedorId ? null : proveedorId));
  }

  function toggleLine(linea: HistorialCompraLinea) {
    setSelection((prev) => {
      const next = { ...prev };
      if (linea.id in next) delete next[linea.id];
      else next[linea.id] = String(linea.quantity);
      return next;
    });
  }

  async function onAddSelected(proveedorId: string) {
    const chosen = (lineas ?? []).filter((l) => l.id in selection);
    if (chosen.length === 0) return;
    setError(null);
    setBusy(true);
    try {
      await addToPool(
        tenantSlug as string,
        accessToken as string,
        "manual",
        chosen.map((l) => ({
          release_id: l.release_id ?? undefined,
          artist: l.release_id ? undefined : l.artist ?? undefined,
          title: l.release_id ? undefined : l.title ?? undefined,
          label: l.release_id ? undefined : l.label ?? undefined,
          format: l.release_id ? undefined : l.format ?? undefined,
          quantity: Number(selection[l.id]) || l.quantity,
          proveedor_sugerido_id: proveedorId,
        })),
      );
      queryClient.invalidateQueries({ queryKey: ["pool", tenantSlug] });
      setSelection({});
      router.push("/compras/solicituds/pool");
    } catch (e) {
      setError(e instanceof ApiError ? `${e.status}: ${e.message}` : "No s'ha pogut afegir al pool");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen>
      <View className="px-4 pt-2 pb-3 border-b border-border">
        <Text className="text-xl font-sansBold text-foreground">Compres</Text>
      </View>

      <ComprasSubNav active="historial" />

      {!isRecordsVertical && config ? (
        <View className="flex-1 items-center justify-center p-6">
          <Text className="text-mutedForeground font-sans text-center">
            L&apos;historial de compres només està disponible per a botigues de discos.
          </Text>
        </View>
      ) : (
        <ScrollView contentContainerClassName="p-4 gap-3 pb-10" keyboardShouldPersistTaps="handled">
          <Input
            placeholder="Artista, títol, segell..."
            value={query}
            onChangeText={setQuery}
            autoCapitalize="none"
          />

          {isLoading && (
            <View className="py-6 items-center">
              <ActivityIndicator color={colors.primary} />
            </View>
          )}

          {(resum ?? []).map((prov) => (
            <View key={prov.proveedor_id}>
              <Pressable onPress={() => toggleExpand(prov.proveedor_id)}>
                <Card className="flex-row justify-between items-center">
                  <Text className="font-sansMedium text-foreground">{prov.proveedor_nombre}</Text>
                  <Text className="text-mutedForeground font-sans text-xs">
                    {prov.count} línies · última {new Date(prov.ultima_compra).toLocaleDateString()}
                  </Text>
                </Card>
              </Pressable>

              {expandedId === prov.proveedor_id && (
                <View className="gap-2 mt-2 ml-3">
                  {lineasFetching && (
                    <View className="py-4 items-center">
                      <ActivityIndicator color={colors.primary} />
                    </View>
                  )}
                  {(lineas ?? []).map((linea) => {
                    const isSelected = linea.id in selection;
                    return (
                      <Pressable key={linea.id} onPress={() => toggleLine(linea)}>
                        <Card className={`flex-row items-center gap-3 ${isSelected ? "border-primary" : ""}`}>
                          <View
                            className={`w-6 h-6 rounded-button border items-center justify-center ${
                              isSelected ? "bg-primary border-primary" : "border-border"
                            }`}
                          >
                            {isSelected && <Text className="text-primary-foreground font-sansBold text-xs">✓</Text>}
                          </View>
                          <View className="flex-1">
                            <Text className="font-sans text-foreground">
                              {linea.artist ? `${linea.artist} — ${linea.title}` : linea.title}
                            </Text>
                            <Text className="text-mutedForeground font-sans text-xs">
                              {new Date(linea.date).toLocaleDateString()} · {linea.quantity} unitat
                              {linea.quantity > 1 ? "s" : ""}
                              {linea.cost_price ? ` · ${linea.cost_price} €` : ""}
                            </Text>
                          </View>
                        </Card>
                      </Pressable>
                    );
                  })}
                  {Object.keys(selection).length > 0 && (
                    <Button loading={busy} onPress={() => onAddSelected(prov.proveedor_id)}>
                      Afegir {Object.keys(selection).length} al pool
                    </Button>
                  )}
                </View>
              )}
            </View>
          ))}

          {!isLoading && (resum ?? []).length === 0 && (
            <Text className="text-mutedForeground font-sans">Cap resultat.</Text>
          )}

          {error && <Text className="text-destructive font-sans">{error}</Text>}
        </ScrollView>
      )}
    </Screen>
  );
}
