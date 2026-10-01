import MaterialCommunityIcons from "@expo/vector-icons/MaterialCommunityIcons";
import { CameraView, useCameraPermissions, type BarcodeScanningResult } from "expo-camera";
import { useState } from "react";
import { Modal, Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { colors } from "../../lib/theme";

/** Botón de cámara + modal de escaneo de código de barras (EAN-13/EAN-8/
 * UPC), sin librería externa — `expo-camera` ya la trae. Reutilizado por
 * TPV (buscar artículo) y, más adelante, por la recepción de comandas por
 * EAN (ver docs/ARQUITECTURA_APPS_NATIVAS.md §7sexies). */
export function BarcodeScanButton({ onScan }: { onScan: (code: string) => void }) {
  const insets = useSafeAreaInsets();
  const [open, setOpen] = useState(false);
  const [scanned, setScanned] = useState(false);
  const [permission, requestPermission] = useCameraPermissions();

  async function openScanner() {
    let granted = permission?.granted;
    if (!granted) {
      granted = (await requestPermission()).granted;
    }
    if (!granted) return;
    setScanned(false);
    setOpen(true);
  }

  function handleScanned(result: BarcodeScanningResult) {
    if (scanned) return;
    setScanned(true);
    setOpen(false);
    onScan(result.data);
  }

  return (
    <>
      <Pressable
        onPress={openScanner}
        accessibilityLabel="Escanejar codi de barres"
        hitSlop={8}
        className="w-11 h-11 items-center justify-center rounded-button border border-border bg-card"
      >
        <MaterialCommunityIcons name="barcode-scan" size={22} color={colors.primary} />
      </Pressable>

      <Modal visible={open} animationType="slide" onRequestClose={() => setOpen(false)}>
        <View className="flex-1 bg-foreground">
          <CameraView
            style={{ flex: 1 }}
            onBarcodeScanned={handleScanned}
            barcodeScannerSettings={{ barcodeTypes: ["ean13", "ean8", "upc_a", "upc_e"] }}
          />
          <Pressable
            onPress={() => setOpen(false)}
            accessibilityLabel="Tancar l'escàner"
            hitSlop={8}
            className="absolute right-6 w-11 h-11 items-center justify-center rounded-badge bg-card"
            style={{ top: insets.top + 12 }}
          >
            <MaterialCommunityIcons name="close" size={24} color={colors.foreground} />
          </Pressable>
          <View className="absolute left-0 right-0 items-center" style={{ bottom: insets.bottom + 32 }}>
            <Text className="text-card font-sansMedium bg-foreground/70 px-4 py-2 rounded-badge">
              Apunta al codi de barres
            </Text>
          </View>
        </View>
      </Modal>
    </>
  );
}
