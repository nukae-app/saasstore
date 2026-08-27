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
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../../components/ui/select';
import { superadminAuthFetch } from '../../lib/superadmin-auth';

const EMPTY_FORM = {
  name: '', price: '', currency: 'EUR', billing_period: 'monthly',
  revolut_plan_id: '', revolut_variation_id: '',
};
const PERIOD_LABEL = { monthly: 'Mensual', yearly: 'Anual' };

export default function SuperadminPlansPage() {
  const [plans, setPlans] = useState(null);
  const [editing, setEditing] = useState(null); // null = tancat, {} = creant, plan = editant
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    const res = await superadminAuthFetch('/superadmin/plans');
    if (res.ok) setPlans(await res.json());
  }, []);

  useEffect(() => { load(); }, [load]);

  function openCreate() {
    setForm(EMPTY_FORM);
    setError('');
    setEditing({});
  }

  function openEdit(plan) {
    setForm({
      name: plan.name, price: plan.price, currency: plan.currency, billing_period: plan.billing_period,
      revolut_plan_id: plan.revolut_plan_id || '', revolut_variation_id: plan.revolut_variation_id || '',
    });
    setError('');
    setEditing(plan);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setSaving(true);
    try {
      const payload = {
        ...form,
        revolut_plan_id: form.revolut_plan_id || null,
        revolut_variation_id: form.revolut_variation_id || null,
      };
      const isCreate = !editing?.id;
      const res = isCreate
        ? await superadminAuthFetch('/superadmin/plans', { method: 'POST', body: JSON.stringify(payload) })
        : await superadminAuthFetch(`/superadmin/plans/${editing.id}`, { method: 'PATCH', body: JSON.stringify(payload) });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.detail || 'No s\'ha pogut desar el pla.');
        return;
      }
      setEditing(null);
      load();
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleActive(plan, next) {
    const res = await superadminAuthFetch(`/superadmin/plans/${plan.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ active: next }),
    });
    if (res.ok) load();
  }

  return (
    <div className="space-y-5 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Plans</h2>
          <p className="text-sm text-slate-500 mt-1">
            Catàleg de tarifes que un tenant paga a la plataforma. Els ids de Revolut
            (Plan/Variation) s&apos;enganxen a mà un cop creats des del seu dashboard.
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus size={16} /> Nou pla
        </Button>
      </div>

      {plans === null ? (
        <div className="flex items-center gap-2 text-slate-500 text-sm">
          <Loader2 size={14} className="animate-spin" /> Carregant...
        </div>
      ) : plans.length === 0 ? (
        <p className="text-sm text-slate-500">Encara no hi ha cap pla.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nom</TableHead>
              <TableHead>Preu</TableHead>
              <TableHead>Periodicitat</TableHead>
              <TableHead>Revolut Plan/Variation</TableHead>
              <TableHead>Actiu</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {plans.map((p) => (
              <TableRow key={p.id}>
                <TableCell className="font-medium text-slate-900">{p.name}</TableCell>
                <TableCell className="text-slate-500">{p.price} {p.currency}</TableCell>
                <TableCell className="text-slate-500">{PERIOD_LABEL[p.billing_period] ?? p.billing_period}</TableCell>
                <TableCell className="text-slate-400 text-xs font-mono">
                  {p.revolut_plan_id ? `${p.revolut_plan_id} / ${p.revolut_variation_id ?? '—'}` : '—'}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Switch checked={p.active} onCheckedChange={(next) => handleToggleActive(p, next)} />
                    <Badge variant={p.active ? 'default' : 'secondary'}>{p.active ? 'Actiu' : 'Inactiu'}</Badge>
                  </div>
                </TableCell>
                <TableCell>
                  <Button variant="ghost" size="sm" onClick={() => openEdit(p)}>
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
            <DialogTitle>{editing?.id ? `Editar ${editing.name}` : 'Nou pla'}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="p-name">Nom</Label>
              <Input id="p-name" required value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Bàsic" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="p-price">Preu</Label>
                <Input id="p-price" required type="number" step="0.01" min="0" value={form.price}
                  onChange={(e) => setForm((f) => ({ ...f, price: e.target.value }))} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="p-currency">Moneda</Label>
                <Input id="p-currency" required value={form.currency}
                  onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value.toUpperCase() }))}
                  maxLength={3} />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="p-period">Periodicitat</Label>
              <Select value={form.billing_period} onValueChange={(v) => setForm((f) => ({ ...f, billing_period: v }))}>
                <SelectTrigger id="p-period"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(PERIOD_LABEL).map(([value, label]) => (
                    <SelectItem key={value} value={value}>{label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-3 pt-2 border-t border-slate-100">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Revolut (opcional)</p>
              <div className="space-y-1.5">
                <Label htmlFor="p-revolut-plan">Plan id</Label>
                <Input id="p-revolut-plan" value={form.revolut_plan_id}
                  onChange={(e) => setForm((f) => ({ ...f, revolut_plan_id: e.target.value }))} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="p-revolut-variation">Variation id</Label>
                <Input id="p-revolut-variation" value={form.revolut_variation_id}
                  onChange={(e) => setForm((f) => ({ ...f, revolut_variation_id: e.target.value }))} />
              </div>
              <p className="text-xs text-slate-400">
                Creats a mà des del dashboard de Revolut Business mentre no hi ha
                credencials de sandbox per crear-los des d&apos;aquí.
              </p>
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
