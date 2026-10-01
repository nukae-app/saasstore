import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";

import { ReleasePicker } from "../../../../components/ReleasePicker";
import { Button } from "../../../../components/ui/Button";
import { Card } from "../../../../components/ui/Card";
import { Screen } from "../../../../components/ui/Screen";
import {
  ApiError,
  addToPool,
  fetchPool,
  fetchRefillSugerencias,
  generarSolicitud,
} from "../../../../lib/api";
import { useAuth } from "../../../../lib/auth";
import { colors } from "../../../../lib/theme";
import type { ReleaseRef } from "../../../../lib/types";

const TENDENCIA_LABEL: Record<string, string> = { accelerant: "↑ Accelerant", frenant: "↓ Frenant", estable: "→ Estable" };

export default function Pool() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { tenantSlug, accessToken } = useAuth();

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: pool, isLoading } = useQuery({
    queryKey: ["pool", tenantSlug],
    queryFn: () => fetchPool(tenantSlug as string, accessToken as string, "pendent"),
    enabled: !!tenantSlug && !!accessToken,
  });

  const { data: sugerencias } = useQuery({
    queryKey: ["refill-sugerencias", tenantSlug],
    queryFn: () => fetchRefillSugerencias(tenantSlug as string, accessToken as string),
    enabled: !!tenantSlug && !!accessToken && suggestionsOpen,
  });

  function invalidatePool() {
    queryClient.invalidateQueries({ queryKey: ["pool", tenantSlug] });
  }

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function onAddManual(release: ReleaseRef) {
    setError(null);
    try {
      await addToPool(tenantSlug as string, accessToken as string, "manual", [{ release_id: release.id, quantity: 1 }]);
      invalidatePool();
    } catch (e) {
      setError(e instanceof ApiError ? `${e.status}: ${e.message}` : "No s'ha pogut afegir al pool");
    }
  }

  async function onAddSuggestion(s: {
    release_id: string;
    cantidad_sugerida: number;
    proveedor_sugerido_id: string | null;
  }) {
    setError(null);
    try {
      await addToPool(tenantSlug as string, accessToken as string, "refill_stock", [
        {
          release_id: s.release_id,
          quantity: s.cantidad_sugerida,
          ...(s.proveedor_sugerido_id ? { proveedor_sugerido_id: s.proveedor_sugerido_id } : {}),
        },
      ]);
      invalidatePool();
    } catch (e) {
      setError(e instanceof ApiError ? `${e.status}: ${e.message}` : "No s'ha pogut afegir al pool");
    }
  }

  async function onGenerar() {
    if (selected.size === 0) return;
    setError(null);
    setBusy(true);
    try {
      const solicitud = await generarSolicitud(tenantSlug as string, accessToken as string, Array.from(selected));
      setSelected(new Set());
      invalidatePool();
      router.push(`/compras/solicituds/${solicitud.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? `${e.status}: ${e.message}` : "No s'ha pogut crear la sol·licitud");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen>
      <View className="flex-row items-center px-4 pb-3 border-b border-border">
        <Button variant="outline" className="min-h-0 py-2 px-3" onPress={() => router.back()}>
          ← Enrere
        </Button>
        <Text className="text-lg font-sansBold text-foreground ml-3">Pool</Text>
      </View>

      <ScrollView contentContainerClassName="p-4 gap-3 pb-10">
        <Pressable onPress={() => setSuggestionsOpen((v) => !v)}>
          <Text className="text-primary font-sansMedium">
            {suggestionsOpen ? "− Amagar suggeriments de reposició" : "+ Veure suggeriments de reposició"}
          </Text>
        </Pressable>

        {suggestionsOpen &&
          (sugerencias ?? []).map((s) => (
            <Card key={s.release_id} className="gap-1">
              <Text className="font-sansMedium text-foreground">
                {s.artista} — {s.titulo}
              </Text>
              <Text className="text-mutedForeground font-sans text-xs">
                Estoc: {s.stock_actual} · {TENDENCIA_LABEL[s.tendencia]} · {s.dies_estoc.toFixed(0)} dies
                {s.proveedor_sugerido_nombre ? ` · ${s.proveedor_sugerido_nombre}` : ""}
              </Text>
              <Button variant="secondary" className="mt-1" onPress={() => onAddSuggestion(s)}>
                + Afegir {s.cantidad_sugerida} al pool
              </Button>
            </Card>
          ))}

        <Text className="text-xs uppercase tracking-wide text-mutedForeground font-sansSemibold mt-2">
          Pool ({pool?.results.length ?? 0})
        </Text>

        {isLoading && (
          <View className="py-6 items-center">
            <ActivityIndicator color={colors.primary} />
          </View>
        )}

        {(pool?.results ?? []).map((linea) => {
          const isSelected = selected.has(linea.id);
          const title = linea.title ?? "—";
          return (
            <Pressable key={linea.id} onPress={() => toggleSelect(linea.id)}>
              <Card className={`flex-row items-center gap-3 ${isSelected ? "border-primary" : ""}`}>
                <View
                  className={`w-6 h-6 rounded-button border items-center justify-center ${
                    isSelected ? "bg-primary border-primary" : "border-border"
                  }`}
                >
                  {isSelected && <Text className="text-primary-foreground font-sansBold text-xs">✓</Text>}
                </View>
                <View className="flex-1">
                  <Text className="font-sansMedium text-foreground">{linea.artist ? `${linea.artist} — ${title}` : title}</Text>
                  <Text className="text-mutedForeground font-sans text-xs">
                    {linea.quantity} unitat{linea.quantity > 1 ? "s" : ""}
                    {linea.proveedor_sugerido_nombre ? ` · ${linea.proveedor_sugerido_nombre}` : ""}
                    {linea.origen === "peticion_cliente" ? " · Petició de client" : ""}
                  </Text>
                </View>
              </Card>
            </Pressable>
          );
        })}

        {!isLoading && (pool?.results.length ?? 0) === 0 && (
          <Text className="text-mutedForeground font-sans">Pool buit.</Text>
        )}

        <Button variant="secondary" onPress={() => setPickerOpen(true)}>
          + Afegir disc
        </Button>

        {selected.size > 0 && (
          <Button loading={busy} onPress={onGenerar}>
            Crear sol·licitud ({selected.size})
          </Button>
        )}

        {error && <Text className="text-destructive font-sans">{error}</Text>}
      </ScrollView>

      <ReleasePicker visible={pickerOpen} onClose={() => setPickerOpen(false)} onSelect={onAddManual} />
    </Screen>
  );
}
