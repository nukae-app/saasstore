import { Platform } from "react-native";

/**
 * Base de la API real (mismo backend que web/, docker compose local en
 * localhost:8080, ver docker-compose.yml). El emulador de Android no ve
 * "localhost" como el propio host — 10.0.2.2 es su alias fijo hacia la
 * máquina que lo corre. Para un dispositivo físico hace falta la IP de LAN
 * de la máquina, vía EXPO_PUBLIC_API_URL en .env (no hay forma de
 * adivinarla).
 */
const DEFAULT_API_URL = Platform.OS === "android" ? "http://10.0.2.2:8080/api" : "http://localhost:8080/api";

export const API_URL = process.env.EXPO_PUBLIC_API_URL ?? DEFAULT_API_URL;
