'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { CheckCircle2, CircleOff, Loader2 } from 'lucide-react';
import { Badge } from '../../../../components/ui/badge';
import { Button } from '../../../../components/ui/button';
import { Input } from '../../../../components/ui/input';
import { Label } from '../../../../components/ui/label';
import { Switch } from '../../../../components/ui/switch';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../../../components/ui/select';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from '../../../../components/ui/dialog';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../../../../components/ui/tabs';
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from '../../../../components/ui/table';
import { superadminAuthFetch } from '../../../lib/superadmin-auth';

const BILLING_STATUS_LABEL = {
  sense_pla: 'Sense pla', pendent_targeta: 'Pendent de targeta', activa: 'Activa',
  impagada: 'Impagada', cancellada: 'Cancel·lada',
};
const BILLING_STATUS_BADGE = {
  sense_pla: 'secondary', pendent_targeta: 'warning', activa: 'success',
  impagada: 'destructive', cancellada: 'secondary',
};
const INVOICE_STATUS_LABEL = { pagada: 'Pagada', fallida: 'Fallida', pendent: 'Pendent' };

const SECRET_FIELDS = [
  { key: 'redsys_merchant_code', label: 'Redsys — codi de comerç' },
  { key: 'redsys_terminal', label: 'Redsys — terminal' },
  { key: 'redsys_secret_key', label: 'Redsys — clau secreta' },
  { key: 'discogs_token', label: 'Discogs — token' },
  { key: 'spotify_client_id', label: 'Spotify — client id' },
  { key: 'spotify_client_secret', label: 'Spotify — client secret' },
];

function InfoTab({ id }) {
  const [tenant, setTenant] = useState(null);
  const [verticals, setVerticals] = useState([]);
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [showSuspendConfirm, setShowSuspendConfirm] = useState(false);

  const load = useCallback(async () => {
    const [tenantRes, verticalsRes] = await Promise.all([
      superadminAuthFetch(`/superadmin/tenants/${id}`),
      superadminAuthFetch('/superadmin/verticals'),
    ]);
    if (verticalsRes.ok) setVerticals(await verticalsRes.json());
    if (tenantRes.ok) {
      const data = await tenantRes.json();
      setTenant(data);
      setForm({ nombre: data.nombre, domain: data.domain, vertical_id: data.vertical_id });
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  async function patchTenant(payload) {
    setError('');
    const res = await superadminAuthFetch(`/superadmin/tenants/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError(body.detail || 'No s\'ha pogut desar el canvi.');
      return false;
    }
    setTenant(await res.json());
    return true;
  }

  async function handleSave(e) {
    e.preventDefault();
    setSaving(true);
    try {
      await patchTenant(form);
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleActivo(next) {
    if (!next) {
      setShowSuspendConfirm(true);
      return;
    }
    await patchTenant({ activo: true });
  }

  async function confirmSuspend() {
    setShowSuspendConfirm(false);
    await patchTenant({ activo: false });
  }

  if (!tenant || !form) {
    return (
      <div className="flex items-center gap-2 text-slate-500 text-sm">
        <Loader2 size={14} className="animate-spin" /> Carregant...
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-xl">
      <div className="flex items-center justify-between border border-slate-200 rounded-lg px-4 py-3">
        <div>
          <p className="text-sm font-medium text-slate-700">Estat del tenant</p>
          <p className="text-xs text-slate-400">
            Inactiu talla el storefront, l&apos;admin i l&apos;API d&apos;aquest tenant a l&apos;instant.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={tenant.activo ? 'default' : 'secondary'}>{tenant.activo ? 'Actiu' : 'Inactiu'}</Badge>
          <Switch checked={tenant.activo} onCheckedChange={handleToggleActivo} />
        </div>
      </div>

      <form onSubmit={handleSave} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="nombre">Nom comercial</Label>
          <Input id="nombre" value={form.nombre}
            onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="domain">Domini</Label>
          <Input id="domain" value={form.domain}
            onChange={(e) => setForm((f) => ({ ...f, domain: e.target.value }))} />
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
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <Button type="submit" disabled={saving}>{saving ? 'Desant...' : 'Desar canvis'}</Button>
      </form>

      <Dialog open={showSuspendConfirm} onOpenChange={setShowSuspendConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Suspendre {tenant.nombre}?</DialogTitle>
            <DialogDescription>
              El storefront, l&apos;admin i l&apos;API d&apos;aquest tenant deixaran de respondre a l&apos;instant
              (tornaran 404) fins que el reactivis. No s&apos;esborra cap dada.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setShowSuspendConfirm(false)}>Cancel·lar</Button>
            <Button variant="destructive" onClick={confirmSuspend}>Suspendre</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SecretsTab({ id }) {
  const [status, setStatus] = useState(null);

  const load = useCallback(async () => {
    const res = await superadminAuthFetch(`/superadmin/tenants/${id}/secrets`);
    if (res.ok) setStatus(await res.json());
  }, [id]);

  useEffect(() => { load(); }, [load]);

  if (status === null) {
    return (
      <div className="flex items-center gap-2 text-slate-500 text-sm">
        <Loader2 size={14} className="animate-spin" /> Carregant...
      </div>
    );
  }

  return (
    <div className="space-y-3 max-w-xl">
      <p className="text-sm text-slate-500">
        Nomes lectura d&apos;estat — cada tenant gestiona els seus propis secrets des del seu
        propi admin (Configuració → Secrets). El superadmin mai veu ni pot escriure els valors.
      </p>
      {SECRET_FIELDS.map(({ key, label }) => (
        <div key={key} className="flex items-center justify-between border border-slate-200 rounded-lg px-4 py-3">
          <span className="text-sm font-medium text-slate-700">{label}</span>
          {status[key] ? (
            <Badge variant="default" className="gap-1">
              <CheckCircle2 size={11} /> Configurat
            </Badge>
          ) : (
            <Badge variant="secondary" className="gap-1">
              <CircleOff size={11} /> Sense configurar
            </Badge>
          )}
        </div>
      ))}
    </div>
  );
}

function FeaturesTab({ id }) {
  const [features, setFeatures] = useState(null);
  const [pendingKey, setPendingKey] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    const res = await superadminAuthFetch(`/superadmin/tenants/${id}/features`);
    if (res.ok) setFeatures(await res.json());
  }, [id]);

  useEffect(() => { load(); }, [load]);

  async function handleToggle(featureKey, enabled) {
    setError('');
    setPendingKey(featureKey);
    try {
      const res = await superadminAuthFetch(`/superadmin/tenants/${id}/features/${featureKey}`, {
        method: 'PATCH',
        body: JSON.stringify({ enabled }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.detail || 'No s\'ha pogut desar el canvi.');
        return;
      }
      const updated = await res.json();
      setFeatures((prev) => prev.map((f) => (f.feature_key === featureKey ? updated : f)));
    } finally {
      setPendingKey(null);
    }
  }

  if (features === null) {
    return (
      <div className="flex items-center gap-2 text-slate-500 text-sm">
        <Loader2 size={14} className="animate-spin" /> Carregant...
      </div>
    );
  }

  return (
    <div className="space-y-3 max-w-xl">
      {error && <p className="text-sm text-red-600">{error}</p>}
      {features.map((f) => (
        <div key={f.feature_key} className="flex items-center justify-between border border-slate-200 rounded-lg px-4 py-3">
          <span className="text-sm font-medium text-slate-700">{f.label}</span>
          <Switch
            checked={f.enabled}
            disabled={pendingKey === f.feature_key}
            onCheckedChange={(next) => handleToggle(f.feature_key, next)}
          />
        </div>
      ))}
    </div>
  );
}

function BillingTab({ id }) {
  const [billing, setBilling] = useState(null);
  const [plans, setPlans] = useState([]);
  const [invoices, setInvoices] = useState(null);
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    const [billingRes, plansRes, invoicesRes] = await Promise.all([
      superadminAuthFetch(`/superadmin/tenants/${id}/billing`),
      superadminAuthFetch('/superadmin/plans'),
      superadminAuthFetch(`/superadmin/tenants/${id}/invoices`),
    ]);
    if (plansRes.ok) setPlans(await plansRes.json());
    if (invoicesRes.ok) setInvoices(await invoicesRes.json());
    if (billingRes.ok) {
      const data = await billingRes.json();
      setBilling(data);
      setForm({
        plan_id: data.plan_id ?? '',
        status: data.status,
        revolut_customer_id: data.revolut_customer_id ?? '',
        revolut_subscription_id: data.revolut_subscription_id ?? '',
      });
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  async function handleSave(e) {
    e.preventDefault();
    setError('');
    setSaving(true);
    try {
      const payload = {
        plan_id: form.plan_id || null,
        status: form.status,
        revolut_customer_id: form.revolut_customer_id || null,
        revolut_subscription_id: form.revolut_subscription_id || null,
      };
      const res = await superadminAuthFetch(`/superadmin/tenants/${id}/billing`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.detail || 'No s\'ha pogut desar el canvi.');
        return;
      }
      setBilling(await res.json());
      load();
    } finally {
      setSaving(false);
    }
  }

  if (!billing || !form) {
    return (
      <div className="flex items-center gap-2 text-slate-500 text-sm">
        <Loader2 size={14} className="animate-spin" /> Carregant...
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-xl">
      <div className="flex items-center justify-between border border-slate-200 rounded-lg px-4 py-3">
        <div>
          <p className="text-sm font-medium text-slate-700">Estat de facturació</p>
          <p className="text-xs text-slate-400">{billing.plan_name ?? 'Sense pla assignat'}</p>
        </div>
        <Badge variant={BILLING_STATUS_BADGE[billing.status] ?? 'secondary'}>
          {BILLING_STATUS_LABEL[billing.status] ?? billing.status}
        </Badge>
      </div>

      <p className="text-xs text-slate-400 -mt-3">
        Mentre no hi ha credencials de Revolut per crear customer/subscription des d&apos;aquí,
        aquests camps es desen a mà un cop fets al seu dashboard.
      </p>

      <form onSubmit={handleSave} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="b-plan">Pla</Label>
          <Select value={form.plan_id || '__none__'} onValueChange={(v) => setForm((f) => ({ ...f, plan_id: v === '__none__' ? '' : v }))}>
            <SelectTrigger id="b-plan"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__none__">Sense pla</SelectItem>
              {plans.map((p) => (
                <SelectItem key={p.id} value={p.id}>{p.name} — {p.price} {p.currency}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="b-status">Estat</Label>
          <Select value={form.status} onValueChange={(v) => setForm((f) => ({ ...f, status: v }))}>
            <SelectTrigger id="b-status"><SelectValue /></SelectTrigger>
            <SelectContent>
              {Object.entries(BILLING_STATUS_LABEL).map(([value, label]) => (
                <SelectItem key={value} value={value}>{label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="b-customer">Revolut customer id</Label>
          <Input id="b-customer" value={form.revolut_customer_id}
            onChange={(e) => setForm((f) => ({ ...f, revolut_customer_id: e.target.value }))} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="b-subscription">Revolut subscription id</Label>
          <Input id="b-subscription" value={form.revolut_subscription_id}
            onChange={(e) => setForm((f) => ({ ...f, revolut_subscription_id: e.target.value }))} />
          <p className="text-xs text-slate-400">
            El webhook de Revolut fa servir aquest id per trobar el tenant i actualitzar l&apos;estat sol.
          </p>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <Button type="submit" disabled={saving}>{saving ? 'Desant...' : 'Desar canvis'}</Button>
      </form>

      <div className="space-y-3 pt-2 border-t border-slate-100">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Factures</p>
        {invoices === null ? (
          <div className="flex items-center gap-2 text-slate-500 text-sm">
            <Loader2 size={14} className="animate-spin" /> Carregant...
          </div>
        ) : invoices.length === 0 ? (
          <p className="text-sm text-slate-500">Encara no hi ha cap factura (les crea el webhook de Revolut).</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Data</TableHead>
                <TableHead>Import</TableHead>
                <TableHead>Estat</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {invoices.map((inv) => (
                <TableRow key={inv.id}>
                  <TableCell className="text-slate-500 whitespace-nowrap">
                    {new Date(inv.created_at).toLocaleDateString('ca-ES')}
                  </TableCell>
                  <TableCell className="text-slate-700">{inv.amount} {inv.currency}</TableCell>
                  <TableCell>
                    <Badge variant={inv.status === 'pagada' ? 'success' : inv.status === 'fallida' ? 'destructive' : 'secondary'}>
                      {INVOICE_STATUS_LABEL[inv.status] ?? inv.status}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}

export default function TenantDetailPage() {
  const { id } = useParams();
  const searchParams = useSearchParams();
  const initialTab = searchParams.get('tab') || 'info';

  return (
    <div className="space-y-5">
      <h2 className="text-2xl font-bold text-slate-900">Tenant</h2>
      <Tabs defaultValue={initialTab}>
        <TabsList>
          <TabsTrigger value="info">Info</TabsTrigger>
          <TabsTrigger value="features">Features</TabsTrigger>
          <TabsTrigger value="billing">Facturació</TabsTrigger>
          <TabsTrigger value="secrets">Secrets</TabsTrigger>
        </TabsList>
        <TabsContent value="info"><InfoTab id={id} /></TabsContent>
        <TabsContent value="features"><FeaturesTab id={id} /></TabsContent>
        <TabsContent value="billing"><BillingTab id={id} /></TabsContent>
        <TabsContent value="secrets"><SecretsTab id={id} /></TabsContent>
      </Tabs>
    </div>
  );
}
