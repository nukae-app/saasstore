'use client';

import { useEditor } from '@craftjs/core';

export default function HistoryBar() {
  const { actions, canUndo, canRedo } = useEditor((state, query) => ({
    canUndo: query.history.canUndo(),
    canRedo: query.history.canRedo(),
  }));
  return (
    <div className="flex gap-1">
      <button
        onClick={() => actions.history.undo()}
        disabled={!canUndo}
        className="text-xs px-3 py-1.5 rounded-lg border border-outline-variant disabled:opacity-40 hover:bg-surface-container-high transition-colors"
      >
        Desfer
      </button>
      <button
        onClick={() => actions.history.redo()}
        disabled={!canRedo}
        className="text-xs px-3 py-1.5 rounded-lg border border-outline-variant disabled:opacity-40 hover:bg-surface-container-high transition-colors"
      >
        Refer
      </button>
    </div>
  );
}
