import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Alert, ScrollView, Text, View } from "react-native";

import { Button } from "../../../components/ui/Button";
import { Card } from "../../../components/ui/Card";
import { Input } from "../../../components/ui/Input";
import { Screen } from "../../../components/ui/Screen";
import { StatusBadge } from "../../../components/ui/StatusBadge";
import { ApiError, avisarRecollida, fetchOrderDetail, marcarPagadoTienda, updateOrderStatus } from "../../../lib/api";
import { useAuth } from "../../../lib/auth";
import { colors } from "../../../lib/theme";

const LOGISTIC_STATUSES = ["pagado", "enviado", "entregado"] as const;
const CANCELABLE_STATUSES = new Set(["pendiente_pago", "pagado", "enviado"]);

const STATUS_LABEL: Record<string, string> = {
  pendiente_pago: "Pendent de pagar",
  pagado: "Pagat",
  enviado: "Enviat",
  entregado: "Entregat",
  cancelado: "Cancel·lat",
};

export default function OrderDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { tenantSlug, accessToken } = useAuth();

  const [tracking, setTracking] = useState("");
  const [carrier, setCarrier] = useState("");
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: order, isLoading } = useQuery({
    queryKey: ["order", tenantSlug, id],
    queryFn: () => fetchOrderDetail(tenantSlug as string, accessToken as string, id as string),
    enabled: !!tenantSlug && !!accessToken && !!id,
  });

  // Solo al cargar el pedido (no en cada refetch tras una acción, para no
  // pisar lo que el usuario esté escribiendo si guarda seguimiento justo
  // después de otra acción) — por eso depende de `order?.id`, no de `order`.
  useEffect(() => {
    if (order) {
      setTracking(order.numero_seguiment ?? "");
      setCarrier(order.transportista ?? "");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [order?.id]);

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["order", tenantSlug, id] });
    queryClient.invalidateQueries({ queryKey: ["orders", tenantSlug] });
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

  function onChangeStatus(status: string) {
    runAction(status, () =>
      updateOrderStatus(tenantSlug as string, accessToken as string, id as string, { status }),
    );
  }

  function onSaveTracking() {
    runAction("tracking", () =>
      updateOrderStatus(tenantSlug as string, accessToken as string, id as string, {
        tracking_number: tracking,
        carrier,
      }),
    );
  }

  function onCancel() {
    Alert.alert("Cancel·lar comanda?", "Es retornarà l'estoc a la venda. Aquesta acció no es pot desfer.", [
      { text: "No", style: "cancel" },
      { text: "Sí, cancel·lar", style: "destructive", onPress: () => onChangeStatus("cancelado") },
    ]);
  }

  function onMarcarPagado(method: "efectivo" | "tarjeta") {
    runAction(`pagado-${method}`, () =>
      marcarPagadoTienda(tenantSlug as string, accessToken as string, id as string, method),
    );
  }

  function onAvisarRecollida() {
    runAction("avisar", () => avisarRecollida(tenantSlug as string, accessToken as string, id as string));
  }

  if (isLoading || !order) {
    return (
      <Screen>
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator color={colors.primary} />
        </View>
      </Screen>
    );
  }

  const canMarcarPagadoTienda = order.status === "pendiente_pago" && order.metodo_pago === "tienda";
  const canPickLogisticStatus = LOGISTIC_STATUSES.includes(order.status as (typeof LOGISTIC_STATUSES)[number]);
  const canCancel = CANCELABLE_STATUSES.has(order.status);
  const canAvisarRecollida =
    order.metodo_envio === "recogida_tienda" &&
    order.status === "pagado" &&
    !order.avisada_recollida_at &&
    !order.items.some((i) => i.pendent_arribada);

  return (
    <Screen>
      <View className="flex-row justify-between items-center px-4 pb-3 border-b border-border">
        <Button variant="outline" className="px-3 py-2 min-h-0" onPress={() => router.back()}>
          ← Enrere
        </Button>
        <StatusBadge status={order.status} label={STATUS_LABEL[order.status] ?? order.status} />
      </View>

      <ScrollView contentContainerClassName="p-4 gap-3 pb-10">
        <Card>
          <Text className="text-xs uppercase tracking-wide text-mutedForeground font-sansSemibold mb-1">Client</Text>
          <Text className="text-foreground font-sansMedium">{order.email}</Text>
          <Text className="text-mutedForeground font-mono text-xs mt-1">#{order.id.slice(0, 8)}</Text>
          {order.notas && <Text className="text-foreground font-sans mt-2">{order.notas}</Text>}
        </Card>

        <Card>
          <Text className="text-xs uppercase tracking-wide text-mutedForeground font-sansSemibold mb-2">
            Articles
          </Text>
          {order.items.map((item) => (
            <View key={item.order_item_id} className="flex-row justify-between py-1.5">
              <View className="flex-1 pr-2">
                <Text className="text-foreground font-sans">
                  {item.artista ? `${item.artista} — ${item.titulo}` : item.titulo}
                </Text>
                {item.condicion && (
                  <Text className="text-mutedForeground font-sans text-xs">
                    {item.condicion}
                    {item.estado_disco ? ` · ${item.estado_disco}` : ""}
                    {item.pendent_arribada ? " · pendent d'arribar" : ""}
                  </Text>
                )}
              </View>
              <Text className="text-foreground font-mono">{item.precio} €</Text>
            </View>
          ))}
          <View className="flex-row justify-between border-t border-border mt-2 pt-2">
            <Text className="text-foreground font-sansSemibold">Total</Text>
            <Text className="text-foreground font-monoSemibold">{order.total} €</Text>
          </View>
          {Number(order.coste_envio) > 0 && (
            <Text className="text-mutedForeground font-sans text-xs mt-1">
              Inclou {order.coste_envio} € d&apos;enviament
            </Text>
          )}
        </Card>

        <Card>
          <Text className="text-xs uppercase tracking-wide text-mutedForeground font-sansSemibold mb-1">Enviament</Text>
          <Text className="text-foreground font-sans">
            {order.metodo_envio === "recogida_tienda" ? "Recollida a botiga" : "Enviament a domicili"}
          </Text>
          {order.metodo_envio === "envio" && (
            <View className="gap-2 mt-3">
              <Input placeholder="Número de seguiment" value={tracking} onChangeText={setTracking} />
              <Input placeholder="Transportista" value={carrier} onChangeText={setCarrier} />
              <Button variant="secondary" loading={busyAction === "tracking"} onPress={onSaveTracking}>
                Guardar seguiment
              </Button>
            </View>
          )}
          {canAvisarRecollida && (
            <Button className="mt-3" loading={busyAction === "avisar"} onPress={onAvisarRecollida}>
              Avisar client que ja pot recollir
            </Button>
          )}
          {order.avisada_recollida_at && (
            <Text className="text-accent font-sans text-sm mt-2">
              Avisat el {new Date(order.avisada_recollida_at).toLocaleString()}
            </Text>
          )}
        </Card>

        {canMarcarPagadoTienda && (
          <Card>
            <Text className="text-xs uppercase tracking-wide text-mutedForeground font-sansSemibold mb-2">
              Cobrar a botiga
            </Text>
            <View className="flex-row gap-2">
              <Button
                className="flex-1"
                loading={busyAction === "pagado-efectivo"}
                onPress={() => onMarcarPagado("efectivo")}
              >
                Efectiu
              </Button>
              <Button
                className="flex-1"
                variant="secondary"
                loading={busyAction === "pagado-tarjeta"}
                onPress={() => onMarcarPagado("tarjeta")}
              >
                Targeta
              </Button>
            </View>
          </Card>
        )}

        {canPickLogisticStatus && (
          <Card>
            <Text className="text-xs uppercase tracking-wide text-mutedForeground font-sansSemibold mb-2">Estat</Text>
            <View className="flex-row gap-2">
              {LOGISTIC_STATUSES.map((s) => (
                <Button
                  key={s}
                  className="flex-1"
                  variant={order.status === s ? "primary" : "outline"}
                  loading={busyAction === s}
                  onPress={() => onChangeStatus(s)}
                >
                  {STATUS_LABEL[s]}
                </Button>
              ))}
            </View>
          </Card>
        )}

        {canCancel && (
          <Button variant="destructive" loading={busyAction === "cancelado"} onPress={onCancel}>
            Cancel·lar comanda
          </Button>
        )}

        {error && <Text className="text-destructive font-sans">{error}</Text>}
      </ScrollView>
    </Screen>
  );
}
