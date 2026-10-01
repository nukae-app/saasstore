import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { loginWithPassword, logoutSession, refreshSession, requestMagicLink, verifyMagicLink } from "./api";
import {
  clearStoredRefreshToken,
  getStoredRefreshToken,
  getStoredTenantSlug,
  setStoredRefreshToken,
  setStoredTenantSlug,
} from "./secureStorage";
import type { MobileTenantOption } from "./types";

type AuthStatus = "loading" | "signedOut" | "signedIn";

interface AuthState {
  status: AuthStatus;
  tenantSlug: string | null;
  accessToken: string | null;
  requestLink: (email: string) => Promise<void>;
  verifyToken: (token: string) => Promise<void>;
  // Devuelve `null` si ha entrado directamente, o la lista de tiendas a
  // elegir si el mismo email+contraseña es válido como admin en más de
  // una — repetir la llamada con `tenantSlug` fijado a la elegida.
  signInWithPassword: (email: string, password: string, tenantSlug?: string) => Promise<MobileTenantOption[] | null>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [tenantSlug, setTenantSlug] = useState<string | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);

  // Al arrancar: si hay slug + refresh token guardados (Keychain/Keystore,
  // ver lib/secureStorage.ts), intenta recuperar sesión en silencio antes
  // de mostrar el login — el usuario no debería tener que volver a entrar
  // cada vez que abre la app.
  useEffect(() => {
    (async () => {
      const [storedSlug, storedRefresh] = await Promise.all([getStoredTenantSlug(), getStoredRefreshToken()]);
      if (!storedSlug || !storedRefresh) {
        setTenantSlug(storedSlug);
        setStatus("signedOut");
        return;
      }
      try {
        const session = await refreshSession(storedSlug, storedRefresh);
        await setStoredRefreshToken(session.refresh_token);
        setTenantSlug(storedSlug);
        setAccessToken(session.access_token);
        setStatus("signedIn");
      } catch {
        await clearStoredRefreshToken();
        setTenantSlug(storedSlug);
        setStatus("signedOut");
      }
    })();
  }, []);

  async function requestLink(email: string) {
    // No hace falta el slug de la tienda: la API busca en qué tenant(s) es
    // admin este email (ver auth_mobile.py::request_magic_link_mobile).
    await requestMagicLink(email);
  }

  async function verifyToken(token: string) {
    // Tampoco aquí: el propio token dice de qué tenant es (token_hash es
    // único a nivel global) — el servidor devuelve `tenant_slug` en la
    // respuesta, es la primera vez que el cliente lo sabe.
    const session = await verifyMagicLink(token);
    if (!session.tenant_slug) throw new Error("La resposta del servidor no inclou el tenant");
    await Promise.all([setStoredTenantSlug(session.tenant_slug), setStoredRefreshToken(session.refresh_token)]);
    setTenantSlug(session.tenant_slug);
    setAccessToken(session.access_token);
    setStatus("signedIn");
  }

  async function signInWithPassword(email: string, password: string, tenantSlugChoice?: string) {
    const result = await loginWithPassword(email, password, tenantSlugChoice);
    if (result.status === "choose_tenant") {
      return result.tenants ?? [];
    }
    // status === "signed_in": tokens/tenant_slug siempre rellenos aquí.
    await Promise.all([
      setStoredTenantSlug(result.tenant_slug as string),
      setStoredRefreshToken(result.refresh_token as string),
    ]);
    setTenantSlug(result.tenant_slug);
    setAccessToken(result.access_token);
    setStatus("signedIn");
    return null;
  }

  async function signOut() {
    const refreshToken = await getStoredRefreshToken();
    if (tenantSlug && refreshToken) {
      // Best-effort: si falla (sin red), igual se limpia la sesión local.
      await logoutSession(tenantSlug, refreshToken).catch(() => {});
    }
    await clearStoredRefreshToken();
    setAccessToken(null);
    setStatus("signedOut");
  }

  return (
    <AuthContext.Provider
      value={{ status, tenantSlug, accessToken, requestLink, verifyToken, signInWithPassword, signOut }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth() fuera de <AuthProvider>");
  return ctx;
}
