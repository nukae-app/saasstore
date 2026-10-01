import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, Text, View } from "react-native";

import { BarcodeScanButton } from "../../../components/ui/BarcodeScanButton";
import { Button } from "../../../components/ui/Button";
import { Card } from "../../../components/ui/Card";
import { Input } from "../../../components/ui/Input";
import { Screen } from "../../../components/ui/Screen";
import { StatusBadge } from "../../../components/ui/StatusBadge";
import {
  ApiError,
  cancelarComanda,
  fetchComandaDetail,
  marcarComandaEnviada,
  recibirComanda,
} from "../../../lib/api";
import { useAuth } from "../../../lib/auth";
import { colors } from "../../../lib/theme";
import type { RecepcionItemPayload } from "../../../lib/types";

const STATUS_LABEL: Record<string, string> = {
  esborrany: "Esborrany",
  enviada: "Enviada",
  rebuda_parcial: "Rebuda parcial",
  rebuda: "Rebuda",
  cancelada: "Cancel·lada",
};

interface ReceiveDraft {
  comandaLineaId: string;
  title: string;
  ean: string | null;
  quantityToReceive: number;
  maxQuantity: number;
  price: string;
  condition: "nou" | "segona_ma";
  estadoDisco: string;
  estadoFunda: string;
}

export default function ComandaDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { tenantSlug, accessToken } = useAuth();

  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [receiving, setReceiving] = useState(false);
  const [drafts, setDrafts] = useState<ReceiveDraft[]>([]);
  const [scanFeedback, setScanFeedback] = useState<string | null>(null);

  const { data: comanda, isLoading } = useQuery({
    queryKey: ["comanda", tenantSlug, id],
    queryFn: () => fetchComandaDetail(tenantSlug as string, accessToken as string, id as string),
    enabled: !!tenantSlug && !!accessToken && !!id,
  });

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["comanda", tenantSlug, id] });
    queryClient.invalidateQueries({ queryKey: ["comandas", tenantSlug] });
  }

  function startReceiving() {
    if (!comanda) return;
    setDrafts(
      comanda.lineas
        .filter((l) => l.quantity - l.received_quantity > 0)
        .map((l) => ({
          comandaLineaId: l.id,
          title: l.artista ? `${l.artista} — ${l.titulo}` : l.titulo,
          ean: l.ean,
          quantityToReceive: 0,
          maxQuantity: l.quantity - l.received_quantity,
          price: l.estimated_unit_price ?? "",
          condition: "nou",
          estadoDisco: "",
          estadoFunda: "",
        })),
    );
    setReceiving(true);
  }

  function onScanEan(code: string) {
    setDrafts((prev) => {
      const idx = prev.findIndex((d) => d.ean === code && d.quantityToReceive < d.maxQuantity);
      if (idx === -1) {
        setScanFeedback("Cap línia pendent amb aquest EAN");
        setTimeout(() => setScanFeedback(null), 2000);
        return prev;
      }
      setScanFeedback(null);
      return prev.map((d, i) => (i === idx ? { ...d, quantityToReceive: d.quantityToReceive + 1 } : d));
    });
  }

  function changeDraftQuantity(lineaId: string, delta: number) {
    setDrafts((prev) =>
      prev.map((d) =>
        d.comandaLineaId === lineaId
          ? { ...d, quantityToReceive: Math.min(d.maxQuantity, Math.max(0, d.quantityToReceive + delta)) }
          : d,
      ),
    );
  }

  function updateDraft(lineaId: string, patch: Partial<ReceiveDraft>) {
    setDrafts((prev) => prev.map((d) => (d.comandaLineaId === lineaId ? { ...d, ...patch } : d)));
  }

  async function runAction(name: string, action: () => Promise<unknown>) {
    setError(null);
    setBusyAction(name);
    try {
      await action();
      invalidate();
    } catch (e) {
      setError(e instanceof ApiError ? `${e.status}: ${e.message}` : "No s'ha pogut completar l'acció");
    } finally {
      setBusyAction(null);
    }
  }

  function onMarcarEnviada() {
    runAction("enviada", () => marcarComandaEnviada(tenantSlug as string, accessToken as string, id as string));
  }

  function onCancelar() {
    Alert.alert("Cancel·lar comanda?", "Aquesta acció no es pot desfer.", [
      { text: "No", style: "cancel" },
      {
        text: "Sí, cancel·lar",
        style: "destructive",
        onPress: () => runAction("cancelada", () => cancelarComanda(tenantSlug as string, accessToken as string, id as string)),
      },
    ]);
  }

  async function onConfirmarRecepcio() {
    const items: RecepcionItemPayload[] = drafts
      .filter((d) => d.quantityToReceive > 0)
      .map((d) => ({
        comanda_linea_id: d.comandaLineaId,
        price: d.price || "0",
        condition: d.condition,
        quantity: d.condition === "nou" ? d.quantityToReceive : 1,
        ...(d.condition === "segona_ma" ? { estado_disco: d.estadoDisco || undefined, estado_funda: d.estadoFunda || undefined } : {}),
      }));
    if (items.length === 0) return;
    await runAction("recepcio", async () => {
      await recibirComanda(tenantSlug as string, accessToken as string, id as string, {
        date: new Date().toISOString(),
        items,
      });
      setReceiving(false);
      setDrafts([]);
    });
  }

  if (isLoading || !comanda) {
    return (
      <Screen>
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator color={colors.primary} />
        </View>
      </Screen>
    );
  }

  const canMarcarEnviada = comanda.status === "esborrany";
  const canRebre = comanda.status === "enviada" || comanda.status === "rebuda_parcial";
  const canCancelar = comanda.status !== "rebuda" && comanda.status !== "cancelada";
  const queuedTotal = drafts.reduce((s, d) => s + d.quantityToReceive, 0);

  if (receiving) {
    return (
      <Screen>
        <View className="flex-row justify-between items-center px-4 pb-3 border-b border-border">
          <Button variant="outline" className="min-h-0 py-2 px-3" onPress={() => setReceiving(false)}>
            Cancel·lar
          </Button>
          <Text className="text-foreground font-sansBold">Rebre mercaderia</Text>
          <BarcodeScanButton onScan={onScanEan} />
        </View>

        {scanFeedback && (
          <Text className="text-warning font-sansMedium text-center py-1">{scanFeedback}</Text>
        )}

        <ScrollView contentContainerClassName="p-4 gap-3 pb-10" keyboardShouldPersistTaps="handled">
          {drafts.map((d) => (
            <Card key={d.comandaLineaId} className="gap-2">
              <Text className="text-foreground font-sansMedium">{d.title}</Text>
              <View className="flex-row items-center justify-between">
                <View className="flex-row items-center gap-3">
                  <Pressable
                    onPress={() => changeDraftQuantity(d.comandaLineaId, -1)}
                    hitSlop={8}
                    className="w-8 h-8 items-center justify-center rounded-button bg-muted"
                  >
                    <Text className="text-foreground font-sansBold">−</Text>
                  </Pressable>
                  <Text className="font-sansMedium text-foreground w-16 text-center">
                    {d.quantityToReceive} / {d.maxQuantity}
                  </Text>
                  <Pressable
                    onPress={() => changeDraftQuantity(d.comandaLineaId, 1)}
                    hitSlop={8}
                    className="w-8 h-8 items-center justify-center rounded-button bg-muted"
                  >
                    <Text className="text-foreground font-sansBold">+</Text>
                  </Pressable>
                </View>
                <Input
                  className="w-24 text-right"
                  placeholder="Preu"
                  keyboardType="decimal-pad"
                  value={d.price}
                  onChangeText={(v) => updateDraft(d.comandaLineaId, { price: v })}
                />
              </View>
              {d.quantityToReceive > 0 && (
                <>
                  <View className="flex-row gap-2">
                    {(["nou", "segona_ma"] as const).map((c) => (
                      <Pressable
                        key={c}
                        onPress={() => updateDraft(d.comandaLineaId, { condition: c })}
                        className={`rounded-badge px-3 py-1.5 border ${
                          d.condition === c ? "bg-primary border-primary" : "bg-card border-border"
                        }`}
                      >
                        <Text className={`font-sansMedium text-xs ${d.condition === c ? "text-primary-foreground" : "text-foreground"}`}>
                          {c === "nou" ? "Nou" : "2a mà"}
                        </Text>
                      </Pressable>
                    ))}
                  </View>
                  {d.condition === "segona_ma" && (
                    <View className="flex-row gap-2">
                      <Input
                        className="flex-1"
                        placeholder="Estat disc"
                        value={d.estadoDisco}
                        onChangeText={(v) => updateDraft(d.comandaLineaId, { estadoDisco: v })}
                      />
                      <Input
                        className="flex-1"
                        placeholder="Estat funda"
                        value={d.estadoFunda}
                        onChangeText={(v) => updateDraft(d.comandaLineaId, { estadoFunda: v })}
                      />
                    </View>
                  )}
                </>
              )}
            </Card>
          ))}

          <Button disabled={queuedTotal === 0} loading={busyAction === "recepcio"} onPress={onConfirmarRecepcio}>
            Confirmar recepció ({queuedTotal})
          </Button>

          {error && <Text className="text-destructive font-sans">{error}</Text>}
        </ScrollView>
      </Screen>
    );
  }

  return (
    <Screen>
      <View className="flex-row justify-between items-center px-4 pb-3 border-b border-border">
        <Button variant="outline" className="min-h-0 py-2 px-3" onPress={() => router.back()}>
          ← Enrere
        </Button>
        <StatusBadge status={comanda.status} label={STATUS_LABEL[comanda.status] ?? comanda.status} />
      </View>

      <ScrollView contentContainerClassName="p-4 gap-3 pb-10">
        <Card>
          <Text className="text-xs uppercase tracking-wide text-mutedForeground font-sansSemibold mb-1">
            Proveïdor
          </Text>
          <Text className="text-foreground font-sansMedium">{comanda.proveedor_nombre}</Text>
          <Text className="text-mutedForeground font-mono text-xs mt-1">
            {comanda.order_number ?? comanda.id.slice(0, 8)} · {new Date(comanda.date).toLocaleDateString()}
          </Text>
          {comanda.notes && <Text className="text-foreground font-sans mt-2">{comanda.notes}</Text>}
        </Card>

        <Card>
          <Text className="text-xs uppercase tracking-wide text-mutedForeground font-sansSemibold mb-2">Línies</Text>
          {comanda.lineas.map((l) => (
            <View key={l.id} className="flex-row justify-between py-1.5">
              <Text className="flex-1 text-foreground font-sans pr-2">
                {l.artista ? `${l.artista} — ${l.titulo}` : l.titulo}
              </Text>
              <Text className="text-mutedForeground font-mono text-sm">
                {l.received_quantity}/{l.quantity}
              </Text>
            </View>
          ))}
        </Card>

        {canRebre && <Button onPress={startReceiving}>Rebre mercaderia</Button>}
        {canMarcarEnviada && (
          <Button variant="secondary" loading={busyAction === "enviada"} onPress={onMarcarEnviada}>
            Marcar com a enviada
          </Button>
        )}
        {canCancelar && (
          <Button variant="destructive" loading={busyAction === "cancelada"} onPress={onCancelar}>
            Cancel·lar comanda
          </Button>
        )}

        {error && <Text className="text-destructive font-sans">{error}</Text>}
      </ScrollView>
    </Screen>
  );
}
