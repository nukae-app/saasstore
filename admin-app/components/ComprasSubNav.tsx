import { useRouter } from "expo-router";
import { Pressable, ScrollView, Text } from "react-native";

type Section = "comandes" | "solicituds" | "historial" | "peticions";

const SECTIONS: { key: Section; label: string; href: string }[] = [
  { key: "comandes", label: "Comandes", href: "/compras" },
  { key: "solicituds", label: "Sol·licituds", href: "/compras/solicituds" },
  { key: "peticions", label: "Peticions", href: "/compras/peticions" },
  { key: "historial", label: "Historial", href: "/compras/historial" },
];

/** Fila de subnavegación entre las secciones de Compres — se repetía a
 * mano en cada pantalla, extraído aquí antes de que crezca más
 * (Particulars/Proveïdors siguientes). Scroll horizontal: con 4+ secciones
 * ya no cabe siempre en una pantalla estrecha. */
export function ComprasSubNav({ active }: { active: Section }) {
  const router = useRouter();
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerClassName="flex-row gap-4 px-4 pt-3">
      {SECTIONS.map((s) => (
        <Pressable key={s.key} onPress={() => router.replace(s.href)} disabled={s.key === active}>
          <Text
            className={
              s.key === active
                ? "text-primary font-sansSemibold border-b-2 border-primary pb-2"
                : "text-mutedForeground font-sansMedium pb-2"
            }
          >
            {s.label}
          </Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}
