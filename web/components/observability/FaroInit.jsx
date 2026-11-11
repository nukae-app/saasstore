'use client';

import { useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { faro, getWebInstrumentations, initializeFaro } from '@grafana/faro-web-sdk';
import { TracingInstrumentation } from '@grafana/faro-web-tracing';

// Flag pròpia (no `faro.api`: el paquet inicialitza `faro` amb un objecte
// no-op per defecte, així que `faro.api` és sempre veritable encara que
// mai s'hagi cridat initializeFaro — feia que aquest guard no funcionés mai).
let initialized = false;

export default function FaroInit({ collectorUrl }) {
  const pathname = usePathname();

  useEffect(() => {
    if (initialized || !collectorUrl) return;
    initialized = true;

    initializeFaro({
      url: collectorUrl,
      app: { name: 'labotigaaquesta', version: '1.0.0', environment: 'production' },
      instrumentations: [...getWebInstrumentations(), new TracingInstrumentation()],
    });
  }, [collectorUrl]);

  // Next.js navega entre rutes (p. ex. /es -> /ca) sense recarregar la
  // pàgina, i Faro només registra càrregues completes
  // (faro.performance.navigation). Cada canvi de ruta es registra com a vista
  // (setView, que alimenta el page_id dels logs) i com a esdeveniment
  // `page_view`, que és el que compta el dashboard de Grafana. Va després de
  // l'effect d'inicialització: React executa els effects en ordre de
  // declaració, així que la primera càrrega també queda registrada.
  useEffect(() => {
    if (!initialized || !pathname) return;
    faro.api.setView({ name: pathname });
    faro.api.pushEvent('page_view', { path: pathname });
  }, [pathname]);

  return null;
}
