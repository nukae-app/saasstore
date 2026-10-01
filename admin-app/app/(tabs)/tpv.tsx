import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";

import { BarcodeScanButton } from "../../components/ui/BarcodeScanButton";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { Screen } from "../../components/ui/Screen";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { ApiError, createVentaExternaLote, fetchTiposIva, searchCatalog } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { colors } from "../../lib/theme";
import type { CatalogItem, CatalogRelease, PaymentMethod, VentaExternaOut } from "../../lib/types";
import { useDebouncedValue } from "../../lib/useDebouncedValue";

interface CartLine {
  key: string;
  itemId?: string;
  tipusIvaId?: number;
  title: string;
  subtitle?: string;
  unitPrice: string;
  quantity: number;
  maxQuantity: number;
}

const PAYMENT_METHODS: { value: PaymentMethod; label: string }[] = [
  { value: "efectivo", label: "Efectiu" },
  { value: "tarjeta", label: "Targeta" },
  { value: "bizum", label: "Bizum" },
  { value: "bono_cultural", label: "Bo cultural" },
];

function itemAvailable(item: CatalogItem): number {
  return item.condition === "nou" ? item.quantity - item.reserved_quantity : item.status === "disponible" ? 1 : 0;
}

function Chip({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      className={`rounded-badge px-3 py-2 border ${active ? "bg-primary border-primary" : "bg-card border-border"}`}
    >
      <Text className={`font-sansMedium text-sm ${active ? "text-primary-foreground" : "text-foreground"}`}>
        {label}
      </Text>
    </Pressable>
  );
}

export default function Tpv() {
  const { tenantSlug, accessToken } = useAuth();
  const queryClient = useQueryClient();

  const [query, setQuery] = useState("");
  const debouncedQuery = useDebouncedValue(query, 300);
  const [cart, setCart] = useState<CartLine[]>([]);
  const [manualOpen, setManualOpen] = useState(false);
  const [manualDesc, setManualDesc] = useState("");
  const [manualPrice, setManualPrice] = useState("");
  const [manualIva, setManualIva] = useState<number | null>(null);
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [clientName, setClientName] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("efectivo");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saleResult, setSaleResult] = useState<VentaExternaOut[] | null>(null);

  const { data: searchPage, isFetching: searching } = useQuery({
    queryKey: ["tpv-search", tenantSlug, debouncedQuery],
    queryFn: () => searchCatalog(tenantSlug as string, accessToken as string, debouncedQuery),
    enabled: !!tenantSlug && !!accessToken && debouncedQuery.trim().length >= 2,
  });

  const { data: tiposIva } = useQuery({
    queryKey: ["tipus-iva", tenantSlug],
    queryFn: () => fetchTiposIva(tenantSlug as string, accessToken as string),
    enabled: !!tenantSlug && !!accessToken,
  });
  const ivaOptions = (tiposIva ?? []).filter((t) => !t.is_rebu);

  function addItem(release: CatalogRelease, item: CatalogItem) {
    const available = itemAvailable(item);
    if (available <= 0) return;
    setCart((prev) => {
      const existing = prev.find((l) => l.itemId === item.id);
      if (existing) {
        if (existing.quantity >= existing.maxQuantity) return prev;
        return prev.map((l) => (l.itemId === item.id ? { ...l, quantity: l.quantity + 1 } : l));
      }
      const subtitle = [item.condition, item.estado_disco].filter(Boolean).join(" · ");
      return [
        ...prev,
        {
          key: item.id,
          itemId: item.id,
          title: release.artista ? `${release.artista} — ${release.title}` : release.title,
          subtitle,
          unitPrice: item.price,
          quantity: 1,
          maxQuantity: available,
        },
      ];
    });
  }

  function addManual() {
    if (!manualDesc.trim() || !manualPrice || manualIva == null) return;
    setCart((prev) => [
      ...prev,
      {
        key: `manual-${Date.now()}`,
        tipusIvaId: manualIva,
        title: manualDesc.trim(),
        unitPrice: manualPrice,
        quantity: 1,
        maxQuantity: 99,
      },
    ]);
    setManualDesc("");
    setManualPrice("");
    setManualIva(null);
    setManualOpen(false);
  }

  function changeQuantity(key: string, delta: number) {
    setCart((prev) =>
      prev
        .map((l) => (l.key === key ? { ...l, quantity: Math.min(l.maxQuantity, Math.max(0, l.quantity + delta)) } : l))
        .filter((l) => l.quantity > 0),
    );
  }

  function changePrice(key: string, value: string) {
    setCart((prev) => prev.map((l) => (l.key === key ? { ...l, unitPrice: value } : l)));
  }

  function removeLine(key: string) {
    setCart((prev) => prev.filter((l) => l.key !== key));
  }

  const total = cart.reduce((sum, l) => sum + (Number(l.unitPrice) || 0) * l.quantity, 0);

  async function onConfirmSale() {
    setError(null);
    setBusy(true);
    try {
      const result = await createVentaExternaLote(tenantSlug as string, accessToken as string, {
        lineas: cart.map((l) => ({
          item_id: l.itemId,
          description: l.itemId ? undefined : l.title,
          tipus_iva_id: l.tipusIvaId,
          sale_price: ((Number(l.unitPrice) || 0) * l.quantity).toFixed(2),
          quantity: l.quantity,
        })),
        channel: "mostrador",
        payment_method: paymentMethod,
        date: new Date().toISOString(),
        client_name: clientName.trim() || undefined,
      });
      setSaleResult(result);
      setCart([]);
      setCheckoutOpen(false);
      setClientName("");
      setQuery("");
      queryClient.invalidateQueries({ queryKey: ["orders"] });
    } catch (e) {
      setError(e instanceof ApiError ? `${e.status}: ${e.message}` : "No s'ha pogut cobrar la venda");
    } finally {
      setBusy(false);
    }
  }

  if (saleResult) {
    return (
      <Screen>
        <View className="flex-1 items-center justify-center p-6 gap-3">
          <Text className="text-2xl font-sansBold text-accent">Venda cobrada</Text>
          <Text className="text-4xl font-monoSemibold text-foreground">
            {saleResult.reduce((s, v) => s + Number(v.sale_price), 0).toFixed(2)} €
          </Text>
          <Text className="text-mutedForeground font-sans">
            {PAYMENT_METHODS.find((p) => p.value === saleResult[0]?.payment_method)?.label} ·{" "}
            {new Date(saleResult[0]?.date).toLocaleTimeString()}
          </Text>
          <Button className="mt-6" onPress={() => setSaleResult(null)}>
            Nova venda
          </Button>
        </View>
      </Screen>
    );
  }

  return (
    <Screen>
      <View className="px-4 pt-2 pb-3 border-b border-border">
        <Text className="text-xl font-sansBold text-foreground">TPV</Text>
      </View>

      <ScrollView contentContainerClassName="p-4 gap-3 pb-10" keyboardShouldPersistTaps="handled">
        <View className="flex-row gap-2 items-center">
          <View className="flex-1">
            <Input
              placeholder="Cerca artista, títol o EAN..."
              value={query}
              onChangeText={setQuery}
              autoCapitalize="none"
            />
          </View>
          <BarcodeScanButton onScan={setQuery} />
        </View>

        {searching && (
          <View className="py-4 items-center">
            <ActivityIndicator color={colors.primary} />
          </View>
        )}

        {searchPage?.results.map((release) => (
          <Card key={release.id}>
            <Text className="font-sansMedium text-foreground">
              {release.artista ? `${release.artista} — ${release.title}` : release.title}
            </Text>
            <View className="gap-2 mt-2">
              {release.items.map((item) => {
                const available = itemAvailable(item);
                return (
                  <Pressable
                    key={item.id}
                    disabled={available <= 0}
                    onPress={() => addItem(release, item)}
                    className={`flex-row justify-between items-center border border-border rounded-button px-3 py-2 ${
                      available <= 0 ? "opacity-40" : ""
                    }`}
                  >
                    <View className="flex-1 pr-2">
                      <StatusBadge status={item.condition} label={item.condition === "nou" ? "Nou" : "2a mà"} />
                      {item.estado_disco && (
                        <Text className="text-mutedForeground font-sans text-xs mt-1">
                          {item.estado_disco}
                          {item.estado_funda ? ` / ${item.estado_funda}` : ""}
                        </Text>
                      )}
                    </View>
                    <Text className="font-monoSemibold text-foreground">{item.price} €</Text>
                  </Pressable>
                );
              })}
            </View>
          </Card>
        ))}

        <Pressable onPress={() => setManualOpen((v) => !v)}>
          <Text className="text-primary font-sansMedium">
            {manualOpen ? "− Amagar article manual" : "+ Article manual"}
          </Text>
        </Pressable>

        {manualOpen && (
          <Card className="gap-2">
            <Input placeholder="Descripció" value={manualDesc} onChangeText={setManualDesc} />
            <Input
              placeholder="Preu (€)"
              keyboardType="decimal-pad"
              value={manualPrice}
              onChangeText={setManualPrice}
            />
            <View className="flex-row flex-wrap gap-2">
              {ivaOptions.map((t) => (
                <Chip
                  key={t.id}
                  label={`${t.name} (${t.percentage}%)`}
                  active={manualIva === t.id}
                  onPress={() => setManualIva(t.id)}
                />
              ))}
            </View>
            <Button
              variant="secondary"
              disabled={!manualDesc.trim() || !manualPrice || manualIva == null}
              onPress={addManual}
            >
              Afegir al carret
            </Button>
          </Card>
        )}

        {cart.length > 0 && (
          <Card className="gap-3">
            <Text className="text-xs uppercase tracking-wide text-mutedForeground font-sansSemibold">Carret</Text>
            {cart.map((line, index) => (
              <View
                key={line.key}
                className={`gap-2 ${index < cart.length - 1 ? "border-b border-border pb-3" : ""}`}
              >
                <View className="flex-row justify-between items-start">
                  <View className="flex-1 pr-2">
                    <Text className="text-foreground font-sans">{line.title}</Text>
                    {line.subtitle && <Text className="text-mutedForeground font-sans text-xs">{line.subtitle}</Text>}
                  </View>
                  <Pressable onPress={() => removeLine(line.key)} hitSlop={8}>
                    <Text className="text-destructive font-sansMedium">Treure</Text>
                  </Pressable>
                </View>
                <View className="flex-row items-center justify-between">
                  <View className="flex-row items-center gap-3">
                    <Pressable
                      onPress={() => changeQuantity(line.key, -1)}
                      hitSlop={8}
                      className="w-8 h-8 items-center justify-center rounded-button bg-muted"
                    >
                      <Text className="text-foreground font-sansBold">−</Text>
                    </Pressable>
                    <Text className="font-sansMedium text-foreground w-6 text-center">{line.quantity}</Text>
                    <Pressable
                      onPress={() => changeQuantity(line.key, 1)}
                      disabled={line.quantity >= line.maxQuantity}
                      hitSlop={8}
                      className={`w-8 h-8 items-center justify-center rounded-button bg-muted ${
                        line.quantity >= line.maxQuantity ? "opacity-40" : ""
                      }`}
                    >
                      <Text className="text-foreground font-sansBold">+</Text>
                    </Pressable>
                  </View>
                  <View className="flex-row items-center gap-2">
                    <Input
                      className="w-24 text-right"
                      keyboardType="decimal-pad"
                      value={line.unitPrice}
                      onChangeText={(v) => changePrice(line.key, v)}
                    />
                    <Text className="text-mutedForeground font-sans text-xs">€/u</Text>
                  </View>
                </View>
              </View>
            ))}
            <View className="flex-row justify-between pt-1">
              <Text className="text-foreground font-sansSemibold text-lg">Total</Text>
              <Text className="text-foreground font-monoSemibold text-lg">{total.toFixed(2)} €</Text>
            </View>
          </Card>
        )}

        {cart.length > 0 && !checkoutOpen && (
          <Button onPress={() => setCheckoutOpen(true)}>Cobrar {total.toFixed(2)} €</Button>
        )}

        {checkoutOpen && (
          <Card className="gap-3">
            <Input placeholder="Nom del client (opcional)" value={clientName} onChangeText={setClientName} />
            <View className="flex-row flex-wrap gap-2">
              {PAYMENT_METHODS.map((m) => (
                <Chip
                  key={m.value}
                  label={m.label}
                  active={paymentMethod === m.value}
                  onPress={() => setPaymentMethod(m.value)}
                />
              ))}
            </View>
            <Button loading={busy} onPress={onConfirmSale}>
              Confirmar cobrament de {total.toFixed(2)} €
            </Button>
          </Card>
        )}

        {error && <Text className="text-destructive font-sans">{error}</Text>}
      </ScrollView>
    </Screen>
  );
}
