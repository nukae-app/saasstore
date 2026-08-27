'use client';

import { useCallback, useEffect, useState } from 'react';
import { Plus, Loader2 } from 'lucide-react';
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
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../../components/ui/select';
import { superadminAuthFetch } from '../../lib/superadmin-auth';

const EMPTY_FORM = { email: '', password: '', nombre: '', role: 'support' };
const ROLE_LABEL = { owner: 'Owner', support: 'Support (només lectura)' };

export default function SuperadminAdminsPage() {
  const [admins, setAdmins] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [rowError, setRowError] = useState('');

  const load = useCallback(async () => {
    const res = await superadminAuthFetch('/superadmin/admins');
    if (res.ok) setAdmins(await res.json());
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleCreate(e) {
    e.preventDefault();
    setError('');
    setCreating(true);
    try {
      const res = await superadminAuthFetch('/superadmin/admins', {
        method: 'POST',
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.detail || 'No s\'ha pogut crear l\'operador.');
        return;
      }
      setShowCreate(false);
      setForm(EMPTY_FORM);
      load();
    } finally {
      setCreating(false);
    }
  }

  async function patchAdmin(admin, payload) {
    setRowError('');
    const res = await superadminAuthFetch(`/superadmin/admins/${admin.id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setRowError(body.detail || 'No s\'ha pogut desar el canvi.');
      return;
    }
    load();
  }

  return (
    <div className="space-y-5 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Operadors</h2>
          <p className="text-sm text-slate-500 mt-1">
            Qui pot entrar a aquest panell. &quot;Owner&quot; té control total; &quot;Support&quot; només pot llegir.
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <Plus size={16} /> Nou operador
        </Button>
      </div>

      {rowError && <p className="text-sm text-red-600">{rowError}</p>}

      {admins === null ? (
        <div className="flex items-center gap-2 text-slate-500 text-sm">
          <Loader2 size={14} className="animate-spin" /> Carregant...
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Email</TableHead>
              <TableHead>Nom</TableHead>
              <TableHead>Rol</TableHead>
              <TableHead>Actiu</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {admins.map((a) => (
              <TableRow key={a.id}>
                <TableCell className="font-medium text-slate-900">{a.email}</TableCell>
                <TableCell className="text-slate-500">{a.nombre || '—'}</TableCell>
                <TableCell>
                  <Select value={a.role} onValueChange={(v) => patchAdmin(a, { role: v })}>
                    <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {Object.entries(ROLE_LABEL).map(([value, label]) => (
                        <SelectItem key={value} value={value}>{label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Switch checked={a.activo} onCheckedChange={(next) => patchAdmin(a, { activo: next })} />
                    <Badge variant={a.activo ? 'default' : 'secondary'}>{a.activo ? 'Actiu' : 'Inactiu'}</Badge>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nou operador</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="a-email">Email</Label>
              <Input id="a-email" type="email" required value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="a-nombre">Nom</Label>
              <Input id="a-nombre" value={form.nombre}
                onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="a-password">Contrasenya</Label>
              <Input id="a-password" type="password" required minLength={8} value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} />
              <p className="text-xs text-slate-400">Mínim 8 caràcters. Comunica-la per un canal segur.</p>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="a-role">Rol</Label>
              <Select value={form.role} onValueChange={(v) => setForm((f) => ({ ...f, role: v }))}>
                <SelectTrigger id="a-role"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(ROLE_LABEL).map(([value, label]) => (
                    <SelectItem key={value} value={value}>{label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <DialogFooter>
              <Button type="submit" disabled={creating}>
                {creating ? 'Creant...' : 'Crear operador'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
