'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { Plus, Loader2 } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from '../../components/ui/table';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../components/ui/dialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../components/ui/select';
import { superadminAuthFetch } from '../lib/superadmin-auth';

const EMPTY_FORM = { slug: '', domain: '', nombre: '', fiscal_name: '', address: '', vertical_id: '' };

export default function SuperadminTenantsPage() {
  const [tenants, setTenants] = useState(null);
  const [verticals, setVerticals] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    const res = await superadminAuthFetch('/superadmin/tenants');
    if (res.ok) setTenants(await res.json());
  }, []);

  const loadVerticals = useCallback(async () => {
    // Fuente única (tabla `verticals`, ver docs/ARQUITECTURA_CORE_VERTICAL.md)
    // en vez del array hardcodeado que había aquí antes.
    const res = await superadminAuthFetch('/superadmin/verticals');
    if (res.ok) {
      const data = await res.json();
      setVerticals(data);
      if (data.length > 0) setForm((f) => (f.vertical_id ? f : { ...f, vertical_id: data[0].id }));
    }
  }, []);

  useEffect(() => { load(); loadVerticals(); }, [load, loadVerticals]);

  async function handleCreate(e) {
    e.preventDefault();
    setError('');
    setCreating(true);
    try {
      const res = await superadminAuthFetch('/superadmin/tenants', {
        method: 'POST',
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.detail || 'No s\'ha pogut crear el tenant.');
        return;
      }
      setShowCreate(false);
      setForm({ ...EMPTY_FORM, vertical_id: verticals[0]?.id ?? '' });
      load();
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="space-y-5 max-w-4xl">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-slate-900">Tenants</h2>
        <Button onClick={() => setShowCreate(true)}>
          <Plus size={16} /> Nou tenant
        </Button>
      </div>

      {tenants === null ? (
        <div className="flex items-center gap-2 text-slate-500 text-sm">
          <Loader2 size={14} className="animate-spin" /> Carregant...
        </div>
      ) : tenants.length === 0 ? (
        <p className="text-sm text-slate-500">Encara no hi ha cap tenant.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nom</TableHead>
              <TableHead>Slug</TableHead>
              <TableHead>Domini</TableHead>
              <TableHead>Vertical</TableHead>
              <TableHead>Estat</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {tenants.map((t) => (
              <TableRow key={t.id}>
                <TableCell>
                  <Link href={`/superadmin/tenants/${t.id}`} className="font-medium text-slate-900 hover:underline">
                    {t.nombre}
                  </Link>
                </TableCell>
                <TableCell className="text-slate-500">{t.slug}</TableCell>
                <TableCell className="text-slate-500">{t.domain}</TableCell>
                <TableCell className="text-slate-500">
                  {verticals.find((v) => v.id === t.vertical_id)?.name_ca ?? t.vertical_id}
                </TableCell>
                <TableCell>
                  <Badge variant={t.activo ? 'default' : 'secondary'}>{t.activo ? 'Actiu' : 'Inactiu'}</Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nou tenant</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-3">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Identitat tècnica</p>
              <div className="space-y-1.5">
                <Label htmlFor="slug">Slug</Label>
                <Input id="slug" required value={form.slug}
                  onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))}
                  placeholder="florqa" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="domain">Domini (opcional)</Label>
                <Input id="domain" value={form.domain}
                  onChange={(e) => setForm((f) => ({ ...f, domain: e.target.value }))}
                  placeholder={form.slug ? `${form.slug}.nukae.cloud` : 'florqa.exemple.com'} />
                <p className="text-xs text-slate-400">
                  Buit = neix a {form.slug ? `${form.slug}.nukae.cloud` : '‹slug›.nukae.cloud'} (es pot canviar
                  després pel domini propi del tenant, des de la fitxa del tenant).
                </p>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="nombre">Nom comercial</Label>
                <Input id="nombre" required value={form.nombre}
                  onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="vertical">Vertical</Label>
                <Select value={form.vertical_id} onValueChange={(v) => setForm((f) => ({ ...f, vertical_id: v }))}>
                  <SelectTrigger id="vertical"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {verticals.map((v) => (
                      <SelectItem key={v.id} value={v.id}>{v.name_ca}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-slate-400">
                  Decideix els valors per defecte (p. ex. Discogs actiu només per al vertical de discos).
                </p>
              </div>
            </div>
            <div className="space-y-3 pt-2 border-t border-slate-100">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Identitat fiscal</p>
              <div className="space-y-1.5">
                <Label htmlFor="fiscal_name">Nom fiscal</Label>
                <Input id="fiscal_name" required value={form.fiscal_name}
                  onChange={(e) => setForm((f) => ({ ...f, fiscal_name: e.target.value }))} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="address">Adreça</Label>
                <Input id="address" required value={form.address}
                  onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))} />
              </div>
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <DialogFooter>
              <Button type="submit" disabled={creating}>
                {creating ? 'Creant...' : 'Crear tenant'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
