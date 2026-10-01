import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, Text, View } from "react-native";

import { ReleasePicker } from "../../../../components/ReleasePicker";
import { Button } from "../../../../components/ui/Button";
import { Card } from "../../../../components/ui/Card";
import { Input } from "../../../../components/ui/Input";
import { Screen } from "../../../../components/ui/Screen";
import { StatusBadge } from "../../../../components/ui/StatusBadge";
import {
  ApiError,
  cancelarPeticion,
  catalogarPeticion,
  fetchPeticionDetail,
  fetchProveedores,
  fijarPrecioPeticion,
  vincularPeticionASolicitud,
} from "../../../../lib/api";
import { useAuth } from "../../../../lib/auth";
import { colors } from "../../../../lib/theme";

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

const CANCELABLE = new Set(["pendent", "pendent_acceptacio", "acceptada", "en_tramit", "reservada"]);

export default function PeticionDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { tenantSlug, accessToken } = useAuth();

  const [pickerOpen, setPickerOpen] = useState(false);
  const [price, setPrice] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [proveedorId, setProveedorId] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: peticion, isLoading } = useQuery({
    queryKey: ["peticion", tenantSlug, id],
    queryFn: () => fetchPeticionDetail(tenantSlug as string, accessToken as string, id as string),
    enabled: !!tenantSlug && !!accessToken && !!id,
  });

  const { data: proveedores } = useQuery({
    queryKey: ["proveedores", tenantSlug],
    queryFn: () => fetchProveedores(tenantSlug as string, accessToken as string),
    enabled: peticion?.status === "acceptada" && !!tenantSlug && !!accessToken,
  });

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["peticion", tenantSlug, id] });
    queryClient.invalidateQueries({ queryKey: ["peticions", tenantSlug] });
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

  function onCatalogar(release: { id: string }) {
    runAction("catalogar", () => catalogarPeticion(tenantSlug as string, accessToken as string, id as string, release.id));
  }

  function onFixarPreu() {
    if (!price) return;
    runAction("preu", () => fijarPrecioPeticion(tenantSlug as string, accessToken as string, id as string, price));
  }

  function onVincular() {
    runAction("vincular", async () => {
      await vincularPeticionASolicitud(
        tenantSlug as string,
        accessToken as string,
        id as string,
        Number(quantity) || 1,
        proveedorId ?? undefined,
      );
    });
  }

  function onCancelar() {
    Alert.alert("Cancel·lar petició?", "Aquesta acció no es pot desfer.", [
      { text: "No", style: "cancel" },
      {
        text: "Sí, cancel·lar",
        style: "destructive",
        onPress: () => runAction("cancelada", () => cancelarPeticion(tenantSlug as string, accessToken as string, id as string)),
      },
    ]);
  }

  if (isLoading || !peticion) {
    return (
      <Screen>
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator color={colors.primary} />
        </View>
      </Screen>
    );
  }

  const disco = peticion.artista ? `${peticion.artista} — ${peticion.titulo}` : peticion.titulo ?? "Disc sense catalogar";

  return (
    <Screen>
      <View className="flex-row justify-between items-center px-4 pb-3 border-b border-border">
        <Button variant="outline" className="min-h-0 py-2 px-3" onPress={() => router.back()}>
          ← Enrere
        </Button>
        <StatusBadge status={peticion.status} label={ESTADO_LABEL[peticion.status] ?? peticion.status} />
      </View>

      <ScrollView contentContainerClassName="p-4 gap-3 pb-10" keyboardShouldPersistTaps="handled">
        <Card>
          <Text className="text-xs uppercase tracking-wide text-mutedForeground font-sansSemibold mb-1">Client</Text>
          <Text className="text-foreground font-sansMedium">{peticion.user_nombre ?? peticion.user_email}</Text>
          <Text className="text-mutedForeground font-sans text-xs mt-1">{peticion.user_email}</Text>
        </Card>

        <Card>
          <Text className="text-xs uppercase tracking-wide text-mutedForeground font-sansSemibold mb-1">Disc</Text>
          <Text className="text-foreground font-sansMedium">{disco}</Text>
          {peticion.estimated_price && (
            <Text className="text-foreground font-monoSemibold mt-1">{peticion.estimated_price} €</Text>
          )}
          {peticion.client_notes && <Text className="text-foreground font-sans mt-2">{peticion.client_notes}</Text>}
        </Card>

        {(peticion.status === "pendent" || peticion.status === "pendent_acceptacio") && !peticion.release_id && (
          <Button loading={busyAction === "catalogar"} onPress={() => setPickerOpen(true)}>
            Catalogar disc
          </Button>
        )}

        {peticion.status === "pendent" && peticion.release_id && (
          <Card className="gap-2">
            <Input placeholder="Preu (€)" keyboardType="decimal-pad" value={price} onChangeText={setPrice} />
            <Button disabled={!price} loading={busyAction === "preu"} onPress={onFixarPreu}>
              Fixar preu (el client ja ho ha acceptat de paraula)
            </Button>
          </Card>
        )}

        {peticion.status === "acceptada" && (
          <Card className="gap-2">
            <Text className="text-xs uppercase tracking-wide text-mutedForeground font-sansSemibold">
              Vincular a sol·licitud de compra
            </Text>
            <Input placeholder="Quantitat" keyboardType="number-pad" value={quantity} onChangeText={setQuantity} />
            <View className="flex-row flex-wrap gap-2">
              {(proveedores ?? []).map((p) => (
                <Pressable
                  key={p.id}
                  onPress={() => setProveedorId((prev) => (prev === p.id ? null : p.id))}
                  className={`rounded-badge px-3 py-2 border ${proveedorId === p.id ? "bg-primary border-primary" : "bg-card border-border"}`}
                >
                  <Text className={`font-sansMedium text-sm ${proveedorId === p.id ? "text-primary-foreground" : "text-foreground"}`}>
                    {p.name}
                  </Text>
                </Pressable>
              ))}
            </View>
            <Button loading={busyAction === "vincular"} onPress={onVincular}>
              Afegir al pool de compres
            </Button>
          </Card>
        )}

        {CANCELABLE.has(peticion.status) && (
          <Button variant="destructive" loading={busyAction === "cancelada"} onPress={onCancelar}>
            Cancel·lar petició
          </Button>
        )}

        {error && <Text className="text-destructive font-sans">{error}</Text>}
      </ScrollView>

      <ReleasePicker visible={pickerOpen} onClose={() => setPickerOpen(false)} onSelect={onCatalogar} />
    </Screen>
  );
}
