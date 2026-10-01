import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";

import { ReleasePicker } from "../../../components/ReleasePicker";
import { Button } from "../../../components/ui/Button";
import { Card } from "../../../components/ui/Card";
import { FormField, Input } from "../../../components/ui/Input";
import { Screen } from "../../../components/ui/Screen";
import { ApiError, createComanda, fetchProveedores } from "../../../lib/api";
import { useAuth } from "../../../lib/auth";
import type { ComandaLineaInPayload, ReleaseRef } from "../../../lib/types";

interface LineDraft {
  release: ReleaseRef;
  quantity: number;
  estimatedUnitPrice: string;
}

export default function NovaComanda() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { tenantSlug, accessToken } = useAuth();

  const { data: proveedores } = useQuery({
    queryKey: ["proveedores", tenantSlug],
    queryFn: () => fetchProveedores(tenantSlug as string, accessToken as string),
    enabled: !!tenantSlug && !!accessToken,
  });

  const [proveedorId, setProveedorId] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<LineDraft[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function addLine(release: ReleaseRef) {
    setLines((prev) => {
      const existing = prev.find((l) => l.release.id === release.id);
      if (existing) {
        return prev.map((l) => (l.release.id === release.id ? { ...l, quantity: l.quantity + 1 } : l));
      }
      return [...prev, { release, quantity: 1, estimatedUnitPrice: "" }];
    });
  }

  function changeQuantity(releaseId: string, delta: number) {
    setLines((prev) =>
      prev
        .map((l) => (l.release.id === releaseId ? { ...l, quantity: Math.max(0, l.quantity + delta) } : l))
        .filter((l) => l.quantity > 0),
    );
  }

  function changePrice(releaseId: string, value: string) {
    setLines((prev) => prev.map((l) => (l.release.id === releaseId ? { ...l, estimatedUnitPrice: value } : l)));
  }

  function removeLine(releaseId: string) {
    setLines((prev) => prev.filter((l) => l.release.id !== releaseId));
  }

  async function onCreate() {
    if (!proveedorId || lines.length === 0) return;
    setError(null);
    setBusy(true);
    try {
      const lineas: ComandaLineaInPayload[] = lines.map((l) => ({
        release_id: l.release.id,
        quantity: l.quantity,
        ...(l.estimatedUnitPrice ? { estimated_unit_price: l.estimatedUnitPrice } : {}),
      }));
      const comanda = await createComanda(tenantSlug as string, accessToken as string, {
        proveedor_id: proveedorId,
        date: new Date().toISOString(),
        notes: notes.trim() || undefined,
        lineas,
      });
      queryClient.invalidateQueries({ queryKey: ["comandas", tenantSlug] });
      router.replace(`/compras/${comanda.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? `${e.status}: ${e.message}` : "No s'ha pogut crear la comanda");
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
        <Text className="text-lg font-sansBold text-foreground ml-3">Nova comanda</Text>
      </View>

      <ScrollView contentContainerClassName="p-4 gap-3 pb-10" keyboardShouldPersistTaps="handled">
        <FormField label="Proveïdor">
          <View className="flex-row flex-wrap gap-2">
            {(proveedores ?? []).map((p) => (
              <Pressable
                key={p.id}
                onPress={() => setProveedorId(p.id)}
                className={`rounded-badge px-3 py-2 border ${
                  proveedorId === p.id ? "bg-primary border-primary" : "bg-card border-border"
                }`}
              >
                <Text className={`font-sansMedium text-sm ${proveedorId === p.id ? "text-primary-foreground" : "text-foreground"}`}>
                  {p.name}
                </Text>
              </Pressable>
            ))}
          </View>
        </FormField>

        <FormField label="Notes (opcional)">
          <Input value={notes} onChangeText={setNotes} />
        </FormField>

        <Text className="text-xs uppercase tracking-wide text-mutedForeground font-sansSemibold mt-2">Línies</Text>

        {lines.map((line) => (
          <Card key={line.release.id} className="gap-2">
            <View className="flex-row justify-between items-start">
              <Text className="flex-1 text-foreground font-sans pr-2">
                {line.release.artista ? `${line.release.artista} — ${line.release.title}` : line.release.title}
              </Text>
              <Pressable onPress={() => removeLine(line.release.id)} hitSlop={8}>
                <Text className="text-destructive font-sansMedium">Treure</Text>
              </Pressable>
            </View>
            <View className="flex-row items-center justify-between">
              <View className="flex-row items-center gap-3">
                <Pressable
                  onPress={() => changeQuantity(line.release.id, -1)}
                  hitSlop={8}
                  className="w-8 h-8 items-center justify-center rounded-button bg-muted"
                >
                  <Text className="text-foreground font-sansBold">−</Text>
                </Pressable>
                <Text className="font-sansMedium text-foreground w-6 text-center">{line.quantity}</Text>
                <Pressable
                  onPress={() => changeQuantity(line.release.id, 1)}
                  hitSlop={8}
                  className="w-8 h-8 items-center justify-center rounded-button bg-muted"
                >
                  <Text className="text-foreground font-sansBold">+</Text>
                </Pressable>
              </View>
              <Input
                className="w-28 text-right"
                placeholder="Preu unitat"
                keyboardType="decimal-pad"
                value={line.estimatedUnitPrice}
                onChangeText={(v) => changePrice(line.release.id, v)}
              />
            </View>
          </Card>
        ))}

        <Button variant="secondary" onPress={() => setPickerOpen(true)}>
          + Afegir disc
        </Button>

        <Button
          className="mt-2"
          disabled={!proveedorId || lines.length === 0}
          loading={busy}
          onPress={onCreate}
        >
          Crear comanda
        </Button>

        {error && <Text className="text-destructive font-sans">{error}</Text>}
      </ScrollView>

      <ReleasePicker visible={pickerOpen} onClose={() => setPickerOpen(false)} onSelect={addLine} />
    </Screen>
  );
}
