'use client';

import { useEffect } from 'react';
import { getWebInstrumentations, initializeFaro } from '@grafana/faro-web-sdk';
import { TracingInstrumentation } from '@grafana/faro-web-tracing';

// Flag pròpia (no `faro.api`: el paquet inicialitza `faro` amb un objecte
// no-op per defecte, així que `faro.api` és sempre veritable encara que
// mai s'hagi cridat initializeFaro — feia que aquest guard no funcionés mai).
let initialized = false;

export default function FaroInit({ collectorUrl }) {
  useEffect(() => {
    if (initialized || !collectorUrl) return;
    initialized = true;

    initializeFaro({
      url: collectorUrl,
      app: { name: 'labotigaaquesta', version: '1.0.0', environment: 'production' },
      instrumentations: [...getWebInstrumentations(), new TracingInstrumentation()],
    });
  }, [collectorUrl]);

  return null;
}
