'use client';

import { useCallback, useEffect, useState } from 'react';
import { Plus, Loader2, Pencil } from 'lucide-react';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Label } from '../../../components/ui/label';
import { Badge } from '../../../components/ui/badge';
import { Switch } from '../../../components/ui/switch';
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from '../../../components/ui/table';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../../components/ui/dialog';
import { superadminAuthFetch } from '../../lib/superadmin-auth';

const EMPTY_FORM = { id: '', name_ca: '', name_es: '', name_en: '' };

export default function SuperadminVerticalsPage() {
  const [verticals, setVerticals] = useState(null);
  const [editing, setEditing] = useState(null); // null = tancat, {} = creant, vertical = editant
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    // include_inactive: a diferència del <select> d'alta de tenant, aquí cal
    // veure també els desactivats per poder-los reactivar.
    const res = await superadminAuthFetch('/superadmin/verticals?include_inactive=true');
    if (res.ok) setVerticals(await res.json());
  }, []);

  useEffect(() => { load(); }, [load]);

  function openCreate() {
    setForm(EMPTY_FORM);
    setError('');
    setEditing({});
  }

  function openEdit(vertical) {
    setForm({ id: vertical.id, name_ca: vertical.name_ca, name_es: vertical.name_es, name_en: vertical.name_en });
    setError('');
    setEditing(vertical);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setSaving(true);
    try {
      const isCreate = !editing?.id;
      const res = isCreate
        ? await superadminAuthFetch('/superadmin/verticals', { method: 'POST', body: JSON.stringify(form) })
        : await superadminAuthFetch(`/superadmin/verticals/${editing.id}`, {
            method: 'PATCH',
            body: JSON.stringify({ name_ca: form.name_ca, name_es: form.name_es, name_en: form.name_en }),
          });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.detail || 'No s\'ha pogut desar el vertical.');
        return;
      }
      setEditing(null);
      load();
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleActive(vertical, next) {
    const res = await superadminAuthFetch(`/superadmin/verticals/${vertical.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ active: next }),
    });
    if (res.ok) load();
  }

  return (
    <div className="space-y-5 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Verticals</h2>
          <p className="text-sm text-slate-500 mt-1">
            Tipus de negoci que pot tenir un tenant (discos, floristeria...). Desactivar-ne un
            el treu del selector d&apos;alta de tenant nou, sense afectar els tenants que ja el fan servir.
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus size={16} /> Nou vertical
        </Button>
      </div>

      {verticals === null ? (
        <div className="flex items-center gap-2 text-slate-500 text-sm">
          <Loader2 size={14} className="animate-spin" /> Carregant...
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Id</TableHead>
              <TableHead>Nom (CAT)</TableHead>
              <TableHead>Nom (ESP)</TableHead>
              <TableHead>Nom (ENG)</TableHead>
              <TableHead>Actiu</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {verticals.map((v) => (
              <TableRow key={v.id}>
                <TableCell className="font-mono text-xs text-slate-500">{v.id}</TableCell>
                <TableCell>{v.name_ca}</TableCell>
                <TableCell className="text-slate-500">{v.name_es}</TableCell>
                <TableCell className="text-slate-500">{v.name_en}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Switch checked={v.active} onCheckedChange={(next) => handleToggleActive(v, next)} />
                    <Badge variant={v.active ? 'default' : 'secondary'}>{v.active ? 'Actiu' : 'Inactiu'}</Badge>
                  </div>
                </TableCell>
                <TableCell>
                  <Button variant="ghost" size="sm" onClick={() => openEdit(v)}>
                    <Pencil size={14} />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog open={!!editing} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing?.id ? `Editar ${editing.id}` : 'Nou vertical'}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            {!editing?.id && (
              <div className="space-y-1.5">
                <Label htmlFor="v-id">Id</Label>
                <Input id="v-id" required value={form.id}
                  onChange={(e) => setForm((f) => ({ ...f, id: e.target.value }))}
                  placeholder="floristry" />
                <p className="text-xs text-slate-400">
                  Minúscules/dígits/guió baix, sense espais — identificador tècnic estable, no editable després.
                </p>
              </div>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="v-ca">Nom (català)</Label>
              <Input id="v-ca" required value={form.name_ca}
                onChange={(e) => setForm((f) => ({ ...f, name_ca: e.target.value }))} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="v-es">Nom (castellà)</Label>
              <Input id="v-es" required value={form.name_es}
                onChange={(e) => setForm((f) => ({ ...f, name_es: e.target.value }))} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="v-en">Nom (anglès)</Label>
              <Input id="v-en" required value={form.name_en}
                onChange={(e) => setForm((f) => ({ ...f, name_en: e.target.value }))} />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <DialogFooter>
              <Button type="submit" disabled={saving}>
                {saving ? 'Desant...' : 'Desar'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
