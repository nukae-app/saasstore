import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Alert, Modal, Pressable, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { ReleasePicker } from "../../../../components/ReleasePicker";
import { Button } from "../../../../components/ui/Button";
import { Card } from "../../../../components/ui/Card";
import { Input } from "../../../../components/ui/Input";
import { Screen } from "../../../../components/ui/Screen";
import { StatusBadge } from "../../../../components/ui/StatusBadge";
import {
  ApiError,
  cancelarSolicitud,
  fetchProveedores,
  fetchReleaseDetail,
  fetchSolicitudDetail,
  resolverLineaDesdeEstoc,
  resolverSolicitud,
} from "../../../../lib/api";
import { useAuth } from "../../../../lib/auth";
import { colors } from "../../../../lib/theme";
import type { ReleaseRef, SolicitudCompraLinea } from "../../../../lib/types";

const ESTADO_LABEL: Record<string, string> = { oberta: "Oberta", resolta: "Resolta", cancelada: "Cancel·lada" };

interface ResolveLine {
  linea: SolicitudCompraLinea;
  include: boolean;
  releaseId: string | null;
  releaseLabel: string;
  quantity: string;
  price: string;
}

function EstocPickerModal({
  releaseId,
  onClose,
  onPick,
}: {
  releaseId: string | null;
  onClose: () => void;
  onPick: (itemId: string) => void;
}) {
  const insets = useSafeAreaInsets();
  const { tenantSlug, accessToken } = useAuth();
  const { data: release, isLoading } = useQuery({
    queryKey: ["release-detail", tenantSlug, releaseId],
    queryFn: () => fetchReleaseDetail(tenantSlug as string, accessToken as string, releaseId as string),
    enabled: !!releaseId && !!tenantSlug && !!accessToken,
  });

  return (
    <Modal visible={releaseId !== null} animationType="slide" onRequestClose={onClose}>
      <View className="flex-1 bg-background" style={{ paddingTop: insets.top }}>
        <View className="flex-row justify-between items-center px-4 pb-3 border-b border-border">
          <Text className="text-lg font-sansBold text-foreground">Tria l&apos;exemplar</Text>
          <Pressable onPress={onClose} hitSlop={8}>
            <Text className="text-primary font-sansMedium">Tancar</Text>
          </Pressable>
        </View>
        <ScrollView contentContainerClassName="p-4 gap-2">
          {isLoading && (
            <View className="py-6 items-center">
              <ActivityIndicator color={colors.primary} />
            </View>
          )}
          {release?.items
            .filter((i) => i.status === "disponible")
            .map((item) => (
              <Pressable key={item.id} onPress={() => onPick(item.id)}>
                <Card className="flex-row justify-between items-center">
                  <View>
                    <StatusBadge status={item.condition} label={item.condition === "nou" ? "Nou" : "2a mà"} />
                    {item.estado_disco && (
                      <Text className="text-mutedForeground font-sans text-xs mt-1">{item.estado_disco}</Text>
                    )}
                  </View>
                  <Text className="font-monoSemibold text-foreground">{item.price} €</Text>
                </Card>
              </Pressable>
            ))}
          {!isLoading && release && release.items.filter((i) => i.status === "disponible").length === 0 && (
            <Text className="text-mutedForeground font-sans">Cap exemplar disponible d&apos;aquest disc.</Text>
          )}
        </ScrollView>
      </View>
    </Modal>
  );
}

export default function SolicitudDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { tenantSlug, accessToken } = useAuth();

  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [estocFor, setEstocFor] = useState<{ lineaId: string; releaseId: string } | null>(null);

  const [resolving, setResolving] = useState(false);
  const [resolveLines, setResolveLines] = useState<ResolveLine[]>([]);
  const [proveedorId, setProveedorId] = useState<string | null>(null);
  const [pickerForLinea, setPickerForLinea] = useState<string | null>(null);

  const { data: solicitud, isLoading } = useQuery({
    queryKey: ["solicitud", tenantSlug, id],
    queryFn: () => fetchSolicitudDetail(tenantSlug as string, accessToken as string, id as string),
    enabled: !!tenantSlug && !!accessToken && !!id,
  });

  const { data: proveedores } = useQuery({
    queryKey: ["proveedores", tenantSlug],
    queryFn: () => fetchProveedores(tenantSlug as string, accessToken as string),
    enabled: resolving && !!tenantSlug && !!accessToken,
  });

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["solicitud", tenantSlug, id] });
    queryClient.invalidateQueries({ queryKey: ["solicituds", tenantSlug] });
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

  function onCancelar() {
    Alert.alert("Cancel·lar sol·licitud?", "Aquesta acció no es pot desfer.", [
      { text: "No", style: "cancel" },
      {
        text: "Sí, cancel·lar",
        style: "destructive",
        onPress: () => runAction("cancelada", () => cancelarSolicitud(tenantSlug as string, accessToken as string, id as string)),
      },
    ]);
  }

  async function onResoldreDesdeEstoc(lineaId: string, itemId: string) {
    setEstocFor(null);
    await runAction(`estoc-${lineaId}`, () =>
      resolverLineaDesdeEstoc(tenantSlug as string, accessToken as string, lineaId, itemId),
    );
  }

  function startResolving() {
    if (!solicitud) return;
    const pendents = solicitud.lineas.filter((l) => !l.resuelta);
    setResolveLines(
      pendents.map((l) => ({
        linea: l,
        include: true,
        releaseId: l.release_id,
        releaseLabel: l.release_id ? (l.artist ? `${l.artist} — ${l.title}` : l.title ?? "") : "Sense triar disc",
        quantity: String(l.quantity),
        price: "",
      })),
    );
    const suggested = pendents.find((l) => l.proveedor_sugerido_id)?.proveedor_sugerido_id ?? null;
    setProveedorId(suggested);
    setResolving(true);
  }

  function assignRelease(lineaId: string, release: ReleaseRef) {
    setResolveLines((prev) =>
      prev.map((rl) =>
        rl.linea.id === lineaId
          ? { ...rl, releaseId: release.id, releaseLabel: release.artista ? `${release.artista} — ${release.title}` : release.title }
          : rl,
      ),
    );
  }

  async function onConfirmResolver() {
    const included = resolveLines.filter((rl) => rl.include);
    if (!proveedorId || included.length === 0 || included.some((rl) => !rl.releaseId)) return;
    await runAction("resolver", async () => {
      const comanda = await resolverSolicitud(tenantSlug as string, accessToken as string, {
        proveedor_id: proveedorId,
        date: new Date().toISOString(),
        lineas: included.map((rl) => ({
          solicitud_linea_id: rl.linea.id,
          quantity: Number(rl.quantity) || rl.linea.quantity,
          ...(rl.price ? { estimated_unit_price: rl.price } : {}),
          ...(rl.releaseId !== rl.linea.release_id ? { release_id: rl.releaseId as string } : {}),
        })),
      });
      setResolving(false);
      router.replace(`/compras/${comanda.id}`);
    });
  }

  if (isLoading || !solicitud) {
    return (
      <Screen>
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator color={colors.primary} />
        </View>
      </Screen>
    );
  }

  if (resolving) {
    return (
      <Screen>
        <View className="flex-row items-center px-4 pb-3 border-b border-border">
          <Button variant="outline" className="min-h-0 py-2 px-3" onPress={() => setResolving(false)}>
            Cancel·lar
          </Button>
          <Text className="text-lg font-sansBold text-foreground ml-3">Resoldre a comanda</Text>
        </View>
        <ScrollView contentContainerClassName="p-4 gap-3 pb-10" keyboardShouldPersistTaps="handled">
          <Text className="text-xs uppercase tracking-wide text-mutedForeground font-sansSemibold">Proveïdor</Text>
          <View className="flex-row flex-wrap gap-2">
            {(proveedores ?? []).map((p) => (
              <Pressable
                key={p.id}
                onPress={() => setProveedorId(p.id)}
                className={`rounded-badge px-3 py-2 border ${proveedorId === p.id ? "bg-primary border-primary" : "bg-card border-border"}`}
              >
                <Text className={`font-sansMedium text-sm ${proveedorId === p.id ? "text-primary-foreground" : "text-foreground"}`}>
                  {p.name}
                </Text>
              </Pressable>
            ))}
          </View>

          {resolveLines.map((rl) => (
            <Card key={rl.linea.id} className="gap-2">
              <View className="flex-row justify-between items-start">
                <Pressable
                  className="flex-1 pr-2"
                  onPress={() =>
                    setResolveLines((prev) =>
                      prev.map((x) => (x.linea.id === rl.linea.id ? { ...x, include: !x.include } : x)),
                    )
                  }
                >
                  <Text className={`font-sans ${rl.include ? "text-foreground" : "text-mutedForeground"}`}>
                    {rl.include ? "☑" : "☐"} {rl.releaseLabel}
                  </Text>
                </Pressable>
                {!rl.releaseId && (
                  <Pressable onPress={() => setPickerForLinea(rl.linea.id)}>
                    <Text className="text-primary font-sansMedium text-sm">Triar disc</Text>
                  </Pressable>
                )}
              </View>
              {rl.include && (
                <View className="flex-row gap-2">
                  <Input
                    className="flex-1"
                    placeholder="Quantitat"
                    keyboardType="number-pad"
                    value={rl.quantity}
                    onChangeText={(v) =>
                      setResolveLines((prev) => prev.map((x) => (x.linea.id === rl.linea.id ? { ...x, quantity: v } : x)))
                    }
                  />
                  <Input
                    className="flex-1"
                    placeholder="Preu unitat"
                    keyboardType="decimal-pad"
                    value={rl.price}
                    onChangeText={(v) =>
                      setResolveLines((prev) => prev.map((x) => (x.linea.id === rl.linea.id ? { ...x, price: v } : x)))
                    }
                  />
                </View>
              )}
            </Card>
          ))}

          <Button
            disabled={
              !proveedorId ||
              resolveLines.every((rl) => !rl.include) ||
              resolveLines.some((rl) => rl.include && !rl.releaseId)
            }
            loading={busyAction === "resolver"}
            onPress={onConfirmResolver}
          >
            Crear comanda
          </Button>

          {error && <Text className="text-destructive font-sans">{error}</Text>}
        </ScrollView>

        <ReleasePicker
          visible={pickerForLinea !== null}
          onClose={() => setPickerForLinea(null)}
          onSelect={(release) => {
            if (pickerForLinea) assignRelease(pickerForLinea, release);
            setPickerForLinea(null);
          }}
        />
      </Screen>
    );
  }

  const pendents = solicitud.lineas.filter((l) => !l.resuelta);

  return (
    <Screen>
      <View className="flex-row justify-between items-center px-4 pb-3 border-b border-border">
        <Button variant="outline" className="min-h-0 py-2 px-3" onPress={() => router.back()}>
          ← Enrere
        </Button>
        <StatusBadge status={solicitud.estado} label={ESTADO_LABEL[solicitud.estado] ?? solicitud.estado} />
      </View>

      <ScrollView contentContainerClassName="p-4 gap-3 pb-10">
        <Text className="text-foreground font-mono font-sansMedium">{solicitud.numero}</Text>

        {solicitud.lineas.map((l) => (
          <Card key={l.id} className="gap-1">
            <View className="flex-row justify-between items-start">
              <Text className="flex-1 text-foreground font-sans pr-2">
                {l.artist ? `${l.artist} — ${l.title}` : l.title ?? "—"}
              </Text>
              <Text className="text-mutedForeground font-mono text-sm">×{l.quantity}</Text>
            </View>
            {l.resuelta ? (
              <Text className="text-accent font-sans text-xs">Resolta</Text>
            ) : (
              l.release_id && (
                <Button
                  variant="secondary"
                  className="mt-1"
                  loading={busyAction === `estoc-${l.id}`}
                  onPress={() => setEstocFor({ lineaId: l.id, releaseId: l.release_id as string })}
                >
                  Resoldre des d&apos;estoc
                </Button>
              )
            )}
          </Card>
        ))}

        {solicitud.estado === "oberta" && pendents.length > 0 && (
          <Button onPress={startResolving}>Resoldre a comanda ({pendents.length})</Button>
        )}
        {solicitud.estado === "oberta" && (
          <Button variant="destructive" loading={busyAction === "cancelada"} onPress={onCancelar}>
            Cancel·lar sol·licitud
          </Button>
        )}

        {error && <Text className="text-destructive font-sans">{error}</Text>}
      </ScrollView>

      <EstocPickerModal
        releaseId={estocFor?.releaseId ?? null}
        onClose={() => setEstocFor(null)}
        onPick={(itemId) => estocFor && onResoldreDesdeEstoc(estocFor.lineaId, itemId)}
      />
    </Screen>
  );
}
