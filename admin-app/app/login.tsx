import { useRouter } from "expo-router";
import { useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";

import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { FormField, Input } from "../components/ui/Input";
import { Screen } from "../components/ui/Screen";
import { ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { MobileTenantOption } from "../lib/types";

type Tab = "password" | "magic";

export default function Login() {
  const router = useRouter();
  const { requestLink, verifyToken, signInWithPassword } = useAuth();

  const [tab, setTab] = useState<Tab>("password");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [linkSent, setLinkSent] = useState(false);
  const [tenantChoices, setTenantChoices] = useState<MobileTenantOption[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function errorMessage(e: unknown, fallback: string) {
    return e instanceof ApiError ? `${e.status}: ${e.message}` : fallback;
  }

  async function onPasswordLogin() {
    setError(null);
    setBusy(true);
    try {
      const choices = await signInWithPassword(email.trim(), password);
      if (choices) {
        setTenantChoices(choices);
      } else {
        router.replace("/orders");
      }
    } catch (e) {
      setError(errorMessage(e, "Email o contrasenya incorrectes"));
    } finally {
      setBusy(false);
    }
  }

  async function onChooseTenant(slug: string) {
    setError(null);
    setBusy(true);
    try {
      await signInWithPassword(email.trim(), password, slug);
      router.replace("/orders");
    } catch (e) {
      setError(errorMessage(e, "No s'ha pogut entrar"));
    } finally {
      setBusy(false);
    }
  }

  async function onRequestLink() {
    setError(null);
    setBusy(true);
    try {
      await requestLink(email.trim());
      setLinkSent(true);
    } catch (e) {
      setError(errorMessage(e, "No s'ha pogut enviar l'enllaç"));
    } finally {
      setBusy(false);
    }
  }

  async function onVerify() {
    setError(null);
    setBusy(true);
    try {
      await verifyToken(token.trim());
      router.replace("/orders");
    } catch (e) {
      setError(errorMessage(e, "Token invàlid o caducat"));
    } finally {
      setBusy(false);
    }
  }

  if (tenantChoices) {
    return (
      <Screen>
        <ScrollView contentContainerClassName="p-6 pt-4 gap-3">
          <Text className="text-2xl font-sansBold text-foreground">Quina botiga?</Text>
          <Text className="text-mutedForeground font-sans mb-2">
            Ets admin en més d&apos;una — tria on vols entrar.
          </Text>
          {tenantChoices.map((t) => (
            <Pressable key={t.slug} disabled={busy} onPress={() => onChooseTenant(t.slug)}>
              <Card className={busy ? "opacity-50" : ""}>
                <Text className="text-base font-sansMedium text-foreground">{t.name}</Text>
                <Text className="text-mutedForeground font-mono text-sm">{t.slug}</Text>
              </Card>
            </Pressable>
          ))}
          {error && <Text className="text-destructive font-sans mt-2">{error}</Text>}
        </ScrollView>
      </Screen>
    );
  }

  return (
    <Screen>
      <ScrollView contentContainerClassName="p-6 pt-4 gap-4">
        <Text className="text-2xl font-sansBold text-foreground">Ultra-Local Admin</Text>

        <View className="flex-row bg-muted rounded-button p-1">
          <Pressable
            className={`flex-1 rounded-button py-2 items-center ${tab === "password" ? "bg-card" : ""}`}
            onPress={() => setTab("password")}
          >
            <Text className={`font-sansMedium ${tab === "password" ? "text-foreground" : "text-mutedForeground"}`}>
              Contrasenya
            </Text>
          </Pressable>
          <Pressable
            className={`flex-1 rounded-button py-2 items-center ${tab === "magic" ? "bg-card" : ""}`}
            onPress={() => setTab("magic")}
          >
            <Text className={`font-sansMedium ${tab === "magic" ? "text-foreground" : "text-mutedForeground"}`}>
              Enllaç per email
            </Text>
          </Pressable>
        </View>

        <Text className="text-mutedForeground font-sans -mt-2">
          No cal que sàpigues el nom de la botiga, ho detectem nosaltres.
        </Text>

        <FormField label="Email">
          <Input
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="email-address"
            autoComplete="email"
            placeholder="tu@email.com"
            value={email}
            onChangeText={setEmail}
          />
        </FormField>

        {tab === "password" ? (
          <>
            <FormField label="Contrasenya">
              <Input secureTextEntry autoComplete="password" value={password} onChangeText={setPassword} />
            </FormField>
            <Button disabled={!email || !password} loading={busy} onPress={onPasswordLogin}>
              Entrar
            </Button>
          </>
        ) : (
          <>
            <Button disabled={!email} loading={busy && !linkSent} onPress={onRequestLink}>
              Enviar enllaç d&apos;accés
            </Button>

            {linkSent && (
              <View className="gap-2 mt-2 border-t border-border pt-6">
                <Text className="text-sm text-mutedForeground font-sans mb-1">
                  Revisa el correu (en dev, el contingut de l&apos;email surt als logs de l&apos;API:{" "}
                  <Text className="font-mono">docker compose logs -f api</Text>) i enganxa aquí el token. Si ets
                  admin en més d&apos;una botiga, rebràs un email per cadascuna — tria&apos;n un.
                </Text>
                <Input autoCapitalize="none" autoCorrect={false} placeholder="token" value={token} onChangeText={setToken} />
                <Button variant="secondary" disabled={!token} loading={busy && linkSent} onPress={onVerify}>
                  Verificar i entrar
                </Button>
              </View>
            )}
          </>
        )}

        {error && <Text className="text-destructive font-sans mt-2">{error}</Text>}
      </ScrollView>
    </Screen>
  );
}
