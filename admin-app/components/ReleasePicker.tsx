import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ActivityIndicator, Image, Modal, Pressable, ScrollView, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import {
  ApiError,
  createRelease,
  fetchConfigPublic,
  resolveOrCreateDiscogsRelease,
  searchCatalog,
  searchDiscogs,
} from "../lib/api";
import { useAuth } from "../lib/auth";
import { colors } from "../lib/theme";
import { useDebouncedValue } from "../lib/useDebouncedValue";
import type { DiscogsSearchResult, ReleaseRef } from "../lib/types";
import { BarcodeScanButton } from "./ui/BarcodeScanButton";
import { Button } from "./ui/Button";
import { Card } from "./ui/Card";
import { Input } from "./ui/Input";

type Tab = "catalog" | "discogs" | "manual";

function TabButton({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} className={`flex-1 items-center py-2 border-b-2 ${active ? "border-primary" : "border-transparent"}`}>
      <Text className={`font-sansMedium text-sm ${active ? "text-primary" : "text-mutedForeground"}`}>{label}</Text>
    </Pressable>
  );
}

/** Buscar (en catálogo local o Discogs) o, si no existe, crear a mano un
 * `Release` — reutilizado por Comandes, Compres particulars y Sol·licituds.
 * Manual siempre disponible (CLAUDE.md: el alta debe permitir siempre
 * meter datos a mano, sin depender de Discogs/catálogo). */
export function ReleasePicker({
  visible,
  onClose,
  onSelect,
}: {
  visible: boolean;
  onClose: () => void;
  onSelect: (release: ReleaseRef) => void;
}) {
  const insets = useSafeAreaInsets();
  const { tenantSlug, accessToken } = useAuth();

  const [tab, setTab] = useState<Tab>("catalog");
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebouncedValue(query, 300);
  const [title, setTitle] = useState("");
  const [artista, setArtista] = useState("");
  const [sello, setSello] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: config } = useQuery({
    queryKey: ["config-public", tenantSlug],
    queryFn: () => fetchConfigPublic(tenantSlug as string, accessToken as string),
    enabled: visible && !!tenantSlug && !!accessToken,
    staleTime: 5 * 60 * 1000,
  });
  const discogsEnabled = config?.discogs_habilitat ?? false;

  const { data: catalogPage, isFetching: catalogFetching } = useQuery({
    queryKey: ["release-picker-catalog", tenantSlug, debouncedQuery],
    queryFn: () => searchCatalog(tenantSlug as string, accessToken as string, debouncedQuery),
    enabled: visible && tab === "catalog" && !!tenantSlug && !!accessToken && debouncedQuery.trim().length >= 2,
  });

  const { data: discogsResults, isFetching: discogsFetching } = useQuery({
    queryKey: ["release-picker-discogs", tenantSlug, debouncedQuery],
    queryFn: () => searchDiscogs(tenantSlug as string, accessToken as string, debouncedQuery),
    enabled: visible && tab === "discogs" && discogsEnabled && !!tenantSlug && !!accessToken && debouncedQuery.trim().length >= 3,
  });

  function reset() {
    setTab("catalog");
    setQuery("");
    setTitle("");
    setArtista("");
    setSello("");
    setError(null);
  }

  function handleSelect(release: ReleaseRef) {
    reset();
    onSelect(release);
    onClose();
  }

  async function handleCreateManual() {
    if (!title.trim()) return;
    setError(null);
    setCreating(true);
    try {
      const release = await createRelease(tenantSlug as string, accessToken as string, {
        title: title.trim(),
        artista: artista.trim() || undefined,
        sello: sello.trim() || undefined,
      });
      handleSelect({ id: release.id, artista: release.artista, title: release.title });
    } catch (e) {
      setError(e instanceof ApiError ? `${e.status}: ${e.message}` : "No s'ha pogut crear el disc");
    } finally {
      setCreating(false);
    }
  }

  async function handleSelectDiscogs(result: DiscogsSearchResult) {
    setError(null);
    setCreating(true);
    try {
      const release = await resolveOrCreateDiscogsRelease(tenantSlug as string, accessToken as string, result);
      handleSelect(release);
    } catch (e) {
      setError(e instanceof ApiError ? `${e.status}: ${e.message}` : "No s'ha pogut importar de Discogs");
    } finally {
      setCreating(false);
    }
  }

  return (
    <Modal
      visible={visible}
      animationType="slide"
      onRequestClose={() => {
        reset();
        onClose();
      }}
    >
      <View className="flex-1 bg-background" style={{ paddingTop: insets.top }}>
        <View className="flex-row justify-between items-center px-4 pb-3 border-b border-border">
          <Text className="text-lg font-sansBold text-foreground">Buscar disc</Text>
          <Pressable
            onPress={() => {
              reset();
              onClose();
            }}
            hitSlop={8}
          >
            <Text className="text-primary font-sansMedium">Tancar</Text>
          </Pressable>
        </View>

        <View className="flex-row border-b border-border">
          <TabButton label="Catàleg" active={tab === "catalog"} onPress={() => setTab("catalog")} />
          {discogsEnabled && <TabButton label="Discogs" active={tab === "discogs"} onPress={() => setTab("discogs")} />}
          <TabButton label="Manual" active={tab === "manual"} onPress={() => setTab("manual")} />
        </View>

        <ScrollView contentContainerClassName="p-4 gap-3 pb-10" keyboardShouldPersistTaps="handled">
          {tab !== "manual" && (
            <View className="flex-row gap-2 items-center">
              <View className="flex-1">
                <Input placeholder="Artista, títol o EAN..." value={query} onChangeText={setQuery} autoCapitalize="none" />
              </View>
              <BarcodeScanButton onScan={setQuery} />
            </View>
          )}

          {tab === "catalog" && (
            <>
              {catalogFetching && (
                <View className="py-4 items-center">
                  <ActivityIndicator color={colors.primary} />
                </View>
              )}
              {catalogPage?.results.map((release) => (
                <Pressable
                  key={release.id}
                  onPress={() => handleSelect({ id: release.id, artista: release.artista, title: release.title })}
                >
                  <Card>
                    <Text className="font-sansMedium text-foreground">
                      {release.artista ? `${release.artista} — ${release.title}` : release.title}
                    </Text>
                    {release.sello && <Text className="text-mutedForeground font-sans text-xs">{release.sello}</Text>}
                  </Card>
                </Pressable>
              ))}
              {!catalogFetching && catalogPage && catalogPage.results.length === 0 && (
                <Text className="text-mutedForeground font-sans">Cap resultat al catàleg.</Text>
              )}
            </>
          )}

          {tab === "discogs" && (
            <>
              {(discogsFetching || creating) && (
                <View className="py-4 items-center">
                  <ActivityIndicator color={colors.primary} />
                </View>
              )}
              {!discogsFetching &&
                discogsResults?.map((result) => (
                  <Pressable key={result.discogs_release_id} disabled={creating} onPress={() => handleSelectDiscogs(result)}>
                    <Card className="flex-row gap-3">
                      {result.imagen_url && (
                        <Image source={{ uri: result.imagen_url }} className="w-12 h-12 rounded-button" />
                      )}
                      <View className="flex-1">
                        <Text className="font-sansMedium text-foreground">
                          {result.artista ? `${result.artista} — ${result.titulo}` : result.titulo}
                        </Text>
                        <Text className="text-mutedForeground font-sans text-xs">
                          {[result.sello, result.anio].filter(Boolean).join(" · ")}
                        </Text>
                      </View>
                    </Card>
                  </Pressable>
                ))}
              {!discogsFetching && discogsResults && discogsResults.length === 0 && (
                <Text className="text-mutedForeground font-sans">Cap resultat a Discogs.</Text>
              )}
            </>
          )}

          {tab === "manual" && (
            <Card className="gap-2">
              <Input placeholder="Títol (obligatori)" value={title} onChangeText={setTitle} />
              <Input placeholder="Artista" value={artista} onChangeText={setArtista} />
              <Input placeholder="Segell" value={sello} onChangeText={setSello} />
              <Button variant="secondary" disabled={!title.trim()} loading={creating} onPress={handleCreateManual}>
                Crear i afegir
              </Button>
            </Card>
          )}

          {error && <Text className="text-destructive font-sans">{error}</Text>}
        </ScrollView>
      </View>
    </Modal>
  );
}
