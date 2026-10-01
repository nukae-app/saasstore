import * as SecureStore from "expo-secure-store";

/**
 * Refresh token y slug de tenant, en Keychain (iOS) / Keystore (Android) vía
 * expo-secure-store — nunca AsyncStorage. Ver docs/ARQUITECTURA_APPS_NATIVAS.md
 * §3.2 (backend: repo raíz, no este). El access token NO se persiste aquí a
 * propósito: vive en memoria (estado de React), se recupera con un refresh
 * en cada arranque de la app.
 */
const REFRESH_TOKEN_KEY = "ulr_admin_refresh_token";
const TENANT_SLUG_KEY = "ulr_admin_tenant_slug";

export async function getStoredRefreshToken(): Promise<string | null> {
  return SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
}

export async function setStoredRefreshToken(token: string): Promise<void> {
  await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, token);
}

export async function clearStoredRefreshToken(): Promise<void> {
  await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
}

export async function getStoredTenantSlug(): Promise<string | null> {
  return SecureStore.getItemAsync(TENANT_SLUG_KEY);
}

export async function setStoredTenantSlug(slug: string): Promise<void> {
  await SecureStore.setItemAsync(TENANT_SLUG_KEY, slug);
}
