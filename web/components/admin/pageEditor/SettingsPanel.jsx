'use client';

// Panel de propiedades del nodo seleccionado — mismo patrón que el spike de
// Fase 0: `query.getEvent('selected').last()` + `node.related.settings`,
// cada tipo aporta su propio formulario (StackSettings/TextNodeSettings/...)
// en vez de un editor de props genérico.
import { useEditor } from '@craftjs/core';
import { BREAKPOINTS, useBreakpoint } from './BreakpointContext';

export default function SettingsPanel() {
  const { breakpoint, setBreakpoint } = useBreakpoint();
  const { selected, isRoot } = useEditor((state, query) => {
    const currentNodeId = query.getEvent('selected').last();
    if (!currentNodeId) return { selected: null, isRoot: false };
    const node = state.nodes[currentNodeId];
    return {
      selected: {
        id: currentNodeId,
        displayName: node.data.displayName,
        settings: node.related?.settings,
      },
      isRoot: currentNodeId === 'ROOT',
    };
  });
  const { actions, query } = useEditor();

  return (
    <div className="flex flex-col gap-4">
      <div>
        <label className="block text-xs font-medium text-on-surface-variant mb-2">Breakpoint</label>
        <div className="flex gap-1">
          {BREAKPOINTS.map((bp) => (
            <button
              key={bp.key}
              onClick={() => setBreakpoint(bp.key)}
              className={`flex-1 text-xs px-2 py-1.5 rounded-lg border transition-colors ${
                breakpoint === bp.key ? 'border-primary bg-primary text-white' : 'border-outline-variant text-secondary-foreground'
              }`}
            >
              {bp.label}
            </button>
          ))}
        </div>
      </div>

      <div className="border-t border-outline-variant pt-4">
        {!selected && <p className="text-xs text-secondary-foreground">Selecciona un node al canvas per editar-lo.</p>}
        {selected && (
          <>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold text-on-surface">{selected.displayName}</span>
              {!isRoot && (
                <button
                  onClick={() => {
                    if (query.node(selected.id).isDeletable()) actions.delete(selected.id);
                  }}
                  className="text-[11px] text-red-500 hover:underline"
                >
                  Eliminar
                </button>
              )}
            </div>
            {selected.settings ? <selected.settings /> : <p className="text-xs text-secondary-foreground">Aquest tipus no té propietats editables.</p>}
          </>
        )}
      </div>
    </div>
  );
}
