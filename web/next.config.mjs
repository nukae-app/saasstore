import createNextIntlPlugin from "next-intl/plugin";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Evita que `next dev` regenere AGENTS.md/CLAUDE.md propios en web/ (nueva
  // función de esta preview): no queremos ficheros de instrucciones para IA
  // ajenos al CLAUDE.md real del proyecto.
  agentRules: false,
  images: {
    // imagen_url es un camp lliure a l'admin (no sempre ve de Discogs, ver
    // app/admin/catalogo/page.jsx): calia obrir l'allowlist a qualsevol host
    // HTTPS perquè next/image funcioni amb portades introduïdes a mà.
    remotePatterns: [{ protocol: "https", hostname: "**" }],
  },
};

const withNextIntl = createNextIntlPlugin("./i18n/request.js");

export default withNextIntl(nextConfig);
