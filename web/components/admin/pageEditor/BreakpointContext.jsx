'use client';

// Estado compartido de qué breakpoint se está editando/previsualizando —
// mismo mecanismo ya probado en el spike de Fase 0 (checkpoint de
// breakpoints responsive): un selector Desktop/Tablet/Mòbil que decide qué
// nivel de la cascada {base,tablet?,mobile?} edita el panel de propiedades,
// y a la vez estrecha el canvas para previsualizar. La resolución real en
// el storefront público es CSS con `@media` (`responsiveStyle.js`), esto es
// solo la UI del editor.
import { createContext, useContext, useState } from 'react';

const BreakpointContext = createContext({ breakpoint: 'base', setBreakpoint: () => {} });

export const BREAKPOINTS = [
  { key: 'base', label: 'Desktop', width: null },
  { key: 'tablet', label: 'Tablet', width: 768 },
  { key: 'mobile', label: 'Mòbil', width: 375 },
];

export function BreakpointProvider({ children }) {
  const [breakpoint, setBreakpoint] = useState('base');
  return (
    <BreakpointContext.Provider value={{ breakpoint, setBreakpoint }}>
      {children}
    </BreakpointContext.Provider>
  );
}

export function useBreakpoint() {
  return useContext(BreakpointContext);
}

// Lee/escribe un nivel de la cascada {base,tablet?,mobile?} sin mutar el
// objeto original — usado por los paneles de settings (StackSettings, etc).
export function readAtBreakpoint(value, breakpoint) {
  if (value == null || typeof value !== 'object') return breakpoint === 'base' ? value : undefined;
  return value[breakpoint];
}

export function writeAtBreakpoint(value, breakpoint, newValue) {
  const base = value && typeof value === 'object' ? { ...value } : { base: value };
  if (newValue === undefined) {
    delete base[breakpoint];
  } else {
    base[breakpoint] = newValue;
  }
  return base;
}
