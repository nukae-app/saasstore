'use client';

import { useCallback, useEffect, useState } from 'react';
import { authFetch } from '../../lib/auth';
import { Plus, Pencil, Trash2, ArrowUp, ArrowDown } from 'lucide-react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../../../components/ui/dialog';
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetFooter,
} from '../../../components/ui/sheet';
import { BLOCK_META, BLOCK_TYPES } from '../../../components/store/blocks/meta';
import HeroPropsForm from '../../../components/store/blocks/HeroPropsForm';
import CarouselPropsForm from '../../../components/store/blocks/CarouselPropsForm';

const PROPS_FORMS = {
  hero: HeroPropsForm,
  carousel: CarouselPropsForm,
};

function blockSummary(block) {
  const meta = BLOCK_META[block.block_type];
  if (block.block_type === 'hero') return block.props?.title || '(sense títol)';
  if (block.block_type === 'carousel') return `${block.props?.heading || '(sense títol)'} · #${block.props?.etiqueta_slug || '—'}`;
  return meta?.description || '';
}

export default function AdminPaginaIniciPage() {
  const [blocks, setBlocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [adding, setAdding] = useState(false);
  const [editingBlock, setEditingBlock] = useState(null);
  const [editingProps, setEditingProps] = useState({});
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [reordering, setReordering] = useState(false);
  const [err, setErr] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await authFetch('/admin/home-blocks');
      setBlocks(await r.json());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function addBlock(type) {
    setAdding(true);
    setErr('');
    try {
      const r = await authFetch('/admin/home-blocks', {
        method: 'POST',
        body: JSON.stringify({ block_type: type, props: {} }),
      });
      if (!r.ok) { const b = await r.json(); setErr(typeof b.detail === 'string' ? b.detail : 'Error en afegir el bloc'); return; }
      const created = await r.json();
      await load();
      setAddOpen(false);
      if (BLOCK_META[type]?.editable) {
        setEditingBlock(created);
        setEditingProps(created.props || {});
      }
    } finally {
      setAdding(false);
    }
  }

  function openEdit(block) {
    setEditingBlock(block);
    setEditingProps(block.props || {});
    setErr('');
  }

  async function saveEdit() {
    if (!editingBlock) return;
    setSaving(true);
    setErr('');
    try {
      const r = await authFetch(`/admin/home-blocks/${editingBlock.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ props: editingProps }),
      });
      if (!r.ok) { const b = await r.json(); setErr(typeof b.detail === 'string' ? b.detail : 'Error en guardar'); return; }
      await load();
      setEditingBlock(null);
    } finally {
      setSaving(false);
    }
  }

  async function toggleEnabled(block) {
    await authFetch(`/admin/home-blocks/${block.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled: !block.enabled }),
    });
    await load();
  }

  async function deleteBlock(block) {
    if (!confirm(`Eliminar el bloc "${BLOCK_META[block.block_type]?.label || block.block_type}"?`)) return;
    setDeletingId(block.id);
    try {
      await authFetch(`/admin/home-blocks/${block.id}`, { method: 'DELETE' });
      await load();
    } finally {
      setDeletingId(null);
    }
  }

  async function move(block, direction) {
    const idx = blocks.findIndex((b) => b.id === block.id);
    const swapIdx = direction === 'up' ? idx - 1 : idx + 1;
    if (swapIdx < 0 || swapIdx >= blocks.length) return;
    const reordered = [...blocks];
    [reordered[idx], reordered[swapIdx]] = [reordered[swapIdx], reordered[idx]];
    setBlocks(reordered);
    setReordering(true);
    try {
      await authFetch('/admin/home-blocks/reorder', {
        method: 'PATCH',
        body: JSON.stringify({ order: reordered.map((b, i) => ({ id: b.id, position: i + 1 })) }),
      });
      await load();
    } finally {
      setReordering(false);
    }
  }

  const availableToAdd = BLOCK_TYPES.filter((type) => type === 'carousel' || !blocks.some((b) => b.block_type === type));
  const EditForm = editingBlock ? PROPS_FORMS[editingBlock.block_type] : null;

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-zinc-900">Pàgina d&apos;inici</h1>
          <p className="text-sm text-zinc-500 mt-0.5">Ordena i configura els blocs que formen el home de la teva botiga</p>
        </div>
        <button
          onClick={() => { setErr(''); setAddOpen(true); }}
          className="flex items-center gap-1.5 bg-zinc-900 text-white text-sm px-4 py-2 rounded-xl hover:bg-zinc-700 transition-colors"
        >
          <Plus size={15} /> Afegir bloc
        </button>
      </div>

      {loading ? (
        <p className="text-zinc-400 text-sm">Carregant…</p>
      ) : (
        <div className="flex flex-col gap-2">
          {blocks.map((block, i) => {
            const meta = BLOCK_META[block.block_type];
            return (
              <div
                key={block.id}
                className={`flex items-center gap-3 bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] px-4 py-3 transition-opacity ${block.enabled ? '' : 'opacity-50'}`}
              >
                <div className="flex flex-col shrink-0 -my-1">
                  <button
                    onClick={() => move(block, 'up')}
                    disabled={i === 0 || reordering}
                    className="text-zinc-300 hover:text-zinc-700 disabled:opacity-30 disabled:hover:text-zinc-300"
                  >
                    <ArrowUp size={14} />
                  </button>
                  <button
                    onClick={() => move(block, 'down')}
                    disabled={i === blocks.length - 1 || reordering}
                    className="text-zinc-300 hover:text-zinc-700 disabled:opacity-30 disabled:hover:text-zinc-300"
                  >
                    <ArrowDown size={14} />
                  </button>
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-zinc-900 text-sm">{meta?.label || block.block_type}</span>
                    <span className="text-[10px] bg-zinc-100 text-zinc-500 px-1.5 py-0.5 rounded-full">{block.block_type}</span>
                  </div>
                  <p className="text-xs text-zinc-400 mt-0.5 truncate">{blockSummary(block)}</p>
                </div>

                <div className="flex items-center gap-1 shrink-0">
                  <button
                    type="button"
                    onClick={() => toggleEnabled(block)}
                    title={block.enabled ? 'Actiu' : 'Inactiu'}
                    className={`w-10 h-5 rounded-full transition-colors relative shrink-0 ${block.enabled ? 'bg-green-500' : 'bg-zinc-300'}`}
                  >
                    <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${block.enabled ? 'left-5' : 'left-0.5'}`} />
                  </button>
                  {meta?.editable && (
                    <button onClick={() => openEdit(block)} className="p-1.5 text-zinc-400 hover:text-zinc-700 rounded-lg hover:bg-zinc-50 transition-colors">
                      <Pencil size={14} />
                    </button>
                  )}
                  <button
                    onClick={() => deleteBlock(block)}
                    disabled={deletingId === block.id}
                    className="p-1.5 text-zinc-300 hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            );
          })}
          {blocks.length === 0 && (
            <p className="text-zinc-400 text-sm py-8 text-center">Cap bloc configurat. La pàgina d&apos;inici es mostrarà buida — afegeix-ne un!</p>
          )}
        </div>
      )}

      {/* Afegir bloc */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Afegir bloc</DialogTitle>
            <DialogDescription>Tria un tipus de bloc per afegir-lo al final del home.</DialogDescription>
          </DialogHeader>
          {err && <p className="text-red-500 text-xs">{err}</p>}
          <div className="grid grid-cols-1 gap-2">
            {availableToAdd.map((type) => {
              const meta = BLOCK_META[type];
              return (
                <button
                  key={type}
                  onClick={() => addBlock(type)}
                  disabled={adding}
                  className="flex flex-col items-start gap-0.5 p-3 rounded-xl border border-zinc-200 hover:border-zinc-900 text-left transition-colors disabled:opacity-50"
                >
                  <span className="text-sm font-semibold text-zinc-900">{meta.label}</span>
                  <span className="text-xs text-zinc-400">{meta.description}</span>
                </button>
              );
            })}
            {availableToAdd.length === 0 && (
              <p className="text-sm text-zinc-400 text-center py-4">Ja tens tots els blocs disponibles configurats.</p>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Editar props */}
      <Sheet open={!!editingBlock} onOpenChange={(open) => { if (!open) setEditingBlock(null); }}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>{editingBlock ? BLOCK_META[editingBlock.block_type]?.label : ''}</SheetTitle>
          </SheetHeader>
          <div className="mt-4">
            {EditForm && editingBlock && (
              <EditForm props={editingProps} onChange={setEditingProps} />
            )}
          </div>
          {err && <p className="text-red-500 text-xs mt-3">{err}</p>}
          <SheetFooter className="mt-6">
            <button
              onClick={() => setEditingBlock(null)}
              className="text-sm px-4 py-2 rounded-xl border border-zinc-200 hover:bg-zinc-50 transition-colors"
            >
              Cancel·lar
            </button>
            <button
              onClick={saveEdit}
              disabled={saving}
              className="bg-zinc-900 text-white text-sm px-5 py-2 rounded-xl hover:bg-zinc-700 disabled:opacity-50 transition-colors"
            >
              {saving ? 'Guardant…' : 'Guardar canvis'}
            </button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </div>
  );
}
