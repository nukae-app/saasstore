import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";

import { ReleasePicker } from "../../../../components/ReleasePicker";
import { Button } from "../../../../components/ui/Button";
import { Card } from "../../../../components/ui/Card";
import { FormField, Input } from "../../../../components/ui/Input";
import { Screen } from "../../../../components/ui/Screen";
import { ApiError, createUser, crearPeticionTienda, searchUsers } from "../../../../lib/api";
import { useAuth } from "../../../../lib/auth";
import { colors } from "../../../../lib/theme";
import { useDebouncedValue } from "../../../../lib/useDebouncedValue";
import type { ReleaseRef, UserSearchResult } from "../../../../lib/types";

export default function NovaPeticio() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { tenantSlug, accessToken } = useAuth();

  const [clientQuery, setClientQuery] = useState("");
  const debouncedClientQuery = useDebouncedValue(clientQuery, 300);
  const [selectedClient, setSelectedClient] = useState<UserSearchResult | null>(null);
  const [newClientOpen, setNewClientOpen] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [newName, setNewName] = useState("");
  const [newPhone, setNewPhone] = useState("");

  const [pickerOpen, setPickerOpen] = useState(false);
  const [release, setRelease] = useState<ReleaseRef | null>(null);
  const [freeMode, setFreeMode] = useState(false);
  const [freeArtist, setFreeArtist] = useState("");
  const [freeTitle, setFreeTitle] = useState("");
  const [notes, setNotes] = useState("");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: clientResults, isFetching: searchingClients } = useQuery({
    queryKey: ["user-search", tenantSlug, debouncedClientQuery],
    queryFn: () => searchUsers(tenantSlug as string, accessToken as string, debouncedClientQuery),
    enabled: !!tenantSlug && !!accessToken && debouncedClientQuery.trim().length >= 2 && !selectedClient,
  });

  async function onCreateClient() {
    if (!newEmail.trim()) return;
    setError(null);
    setBusy(true);
    try {
      const user = await createUser(tenantSlug as string, accessToken as string, {
        email: newEmail.trim(),
        name: newName.trim() || undefined,
        phone: newPhone.trim() || undefined,
      });
      setSelectedClient(user);
      setNewClientOpen(false);
    } catch (e) {
      setError(e instanceof ApiError ? `${e.status}: ${e.message}` : "No s'ha pogut crear el client");
    } finally {
      setBusy(false);
    }
  }

  const canSubmit = !!selectedClient && (!!release || (freeMode && freeArtist.trim() && freeTitle.trim()));

  async function onSubmit() {
    if (!selectedClient || !canSubmit) return;
    setError(null);
    setBusy(true);
    try {
      const peticion = await crearPeticionTienda(tenantSlug as string, accessToken as string, {
        user_id: selectedClient.id,
        release_id: release?.id,
        free_artist: release ? undefined : freeArtist.trim(),
        free_title: release ? undefined : freeTitle.trim(),
        client_notes: notes.trim() || undefined,
      });
      queryClient.invalidateQueries({ queryKey: ["peticions", tenantSlug] });
      router.replace(`/compras/peticions/${peticion.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? `${e.status}: ${e.message}` : "No s'ha pogut crear la petició");
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
        <Text className="text-lg font-sansBold text-foreground ml-3">Nova petició</Text>
      </View>

      <ScrollView contentContainerClassName="p-4 gap-3 pb-10" keyboardShouldPersistTaps="handled">
        <Text className="text-xs uppercase tracking-wide text-mutedForeground font-sansSemibold">Client</Text>

        {selectedClient ? (
          <Card className="flex-row justify-between items-center">
            <View>
              <Text className="font-sansMedium text-foreground">{selectedClient.name ?? selectedClient.email}</Text>
              <Text className="text-mutedForeground font-sans text-xs">{selectedClient.email}</Text>
            </View>
            <Pressable onPress={() => setSelectedClient(null)} hitSlop={8}>
              <Text className="text-destructive font-sansMedium">Canviar</Text>
            </Pressable>
          </Card>
        ) : (
          <>
            <Input placeholder="Nom, email o telèfon..." value={clientQuery} onChangeText={setClientQuery} autoCapitalize="none" />
            {searchingClients && (
              <View className="py-2 items-center">
                <ActivityIndicator color={colors.primary} />
              </View>
            )}
            {(clientResults ?? []).map((u) => (
              <Pressable key={u.id} onPress={() => setSelectedClient(u)}>
                <Card>
                  <Text className="font-sansMedium text-foreground">{u.name ?? u.email}</Text>
                  <Text className="text-mutedForeground font-sans text-xs">{u.email}</Text>
                </Card>
              </Pressable>
            ))}
            <Pressable onPress={() => setNewClientOpen((v) => !v)}>
              <Text className="text-primary font-sansMedium">
                {newClientOpen ? "− Amagar alta de client" : "+ Client nou"}
              </Text>
            </Pressable>
            {newClientOpen && (
              <Card className="gap-2">
                <Input placeholder="Email (obligatori)" autoCapitalize="none" keyboardType="email-address" value={newEmail} onChangeText={setNewEmail} />
                <Input placeholder="Nom" value={newName} onChangeText={setNewName} />
                <Input placeholder="Telèfon" keyboardType="phone-pad" value={newPhone} onChangeText={setNewPhone} />
                <Button variant="secondary" disabled={!newEmail.trim()} loading={busy} onPress={onCreateClient}>
                  Crear client
                </Button>
              </Card>
            )}
          </>
        )}

        <Text className="text-xs uppercase tracking-wide text-mutedForeground font-sansSemibold mt-2">Disc</Text>

        {release ? (
          <Card className="flex-row justify-between items-center">
            <Text className="font-sansMedium text-foreground flex-1 pr-2">
              {release.artista ? `${release.artista} — ${release.title}` : release.title}
            </Text>
            <Pressable onPress={() => setRelease(null)} hitSlop={8}>
              <Text className="text-destructive font-sansMedium">Canviar</Text>
            </Pressable>
          </Card>
        ) : freeMode ? (
          <Card className="gap-2">
            <Input placeholder="Artista" value={freeArtist} onChangeText={setFreeArtist} />
            <Input placeholder="Títol" value={freeTitle} onChangeText={setFreeTitle} />
            <Pressable onPress={() => setFreeMode(false)}>
              <Text className="text-primary font-sansMedium text-sm">Cercar al catàleg en comptes</Text>
            </Pressable>
          </Card>
        ) : (
          <>
            <Button variant="secondary" onPress={() => setPickerOpen(true)}>
              Buscar disc
            </Button>
            <Pressable onPress={() => setFreeMode(true)}>
              <Text className="text-primary font-sansMedium">No sé quin disc és exactament</Text>
            </Pressable>
          </>
        )}

        <FormField label="Notes (opcional)">
          <Input value={notes} onChangeText={setNotes} />
        </FormField>

        <Button className="mt-2" disabled={!canSubmit} loading={busy} onPress={onSubmit}>
          Crear petició
        </Button>

        {error && <Text className="text-destructive font-sans">{error}</Text>}
      </ScrollView>

      <ReleasePicker visible={pickerOpen} onClose={() => setPickerOpen(false)} onSelect={setRelease} />
    </Screen>
  );
}
