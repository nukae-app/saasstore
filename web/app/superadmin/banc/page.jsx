'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { CheckCircle2, CircleOff, Loader2 } from 'lucide-react';
import { Badge } from '../../../components/ui/badge';
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from '../../../components/ui/table';
import { superadminAuthFetch } from '../../lib/superadmin-auth';

const BILLING_STATUS_LABEL = {
  sense_pla: 'Sense pla', pendent_targeta: 'Pendent de targeta', activa: 'Activa',
  impagada: 'Impagada', cancellada: 'Cancel·lada',
};
const BILLING_STATUS_BADGE = {
  sense_pla: 'secondary', pendent_targeta: 'warning', activa: 'success',
  impagada: 'destructive', cancellada: 'secondary',
};
const INVOICE_STATUS_LABEL = { pagada: 'Pagada', fallida: 'Fallida', pendent: 'Pendent' };

export default function SuperadminBancPage() {
  const [status, setStatus] = useState(null);
  const [tenants, setTenants] = useState(null);
  const [invoices, setInvoices] = useState(null);

  const load = useCallback(async () => {
    const [statusRes, tenantsRes, invoicesRes] = await Promise.all([
      superadminAuthFetch('/superadmin/banc/status'),
      superadminAuthFetch('/superadmin/banc/tenants'),
      superadminAuthFetch('/superadmin/banc/invoices'),
    ]);
    if (statusRes.ok) setStatus(await statusRes.json());
    if (tenantsRes.ok) setTenants(await tenantsRes.json());
    if (invoicesRes.ok) setInvoices(await invoicesRes.json());
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-8 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Banc</h2>
        <p className="text-sm text-slate-500 mt-1">
          Integració de pagaments (Revolut Business) i qui paga la plataforma. Els preus
          en si es gestionen a <Link href="/superadmin/plans" className="underline">Plans</Link>.
        </p>
      </div>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">Estat de la integració</h3>
        {status === null ? (
          <div className="flex items-center gap-2 text-slate-500 text-sm">
            <Loader2 size={14} className="animate-spin" /> Carregant...
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="border border-slate-200 rounded-lg px-4 py-3">
              <p className="text-xs text-slate-500 mb-1">Webhook de Revolut</p>
              {status.webhook_configured ? (
                <Badge variant="default" className="gap-1"><CheckCircle2 size={11} /> Configurat</Badge>
              ) : (
                <Badge variant="secondary" className="gap-1"><CircleOff size={11} /> Sense configurar</Badge>
              )}
              <p className="text-xs text-slate-400 mt-2 font-mono">POST /api/webhooks/revolut</p>
            </div>
            <div className="border border-slate-200 rounded-lg px-4 py-3">
              <p className="text-xs text-slate-500 mb-1">Factures registrades</p>
              <p className="text-xl font-bold text-slate-900">{status.invoices_count}</p>
            </div>
            <div className="border border-slate-200 rounded-lg px-4 py-3">
              <p className="text-xs text-slate-500 mb-1">Última activitat</p>
              <p className="text-sm text-slate-700">
                {status.last_invoice_at ? new Date(status.last_invoice_at).toLocaleString('ca-ES') : 'Cap encara'}
              </p>
            </div>
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">Pagaments per tenant</h3>
        {tenants === null ? (
          <div className="flex items-center gap-2 text-slate-500 text-sm">
            <Loader2 size={14} className="animate-spin" /> Carregant...
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tenant</TableHead>
                <TableHead>Pla</TableHead>
                <TableHead>Estat</TableHead>
                <TableHead>Últim pagament</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tenants.map((t) => (
                <TableRow key={t.tenant_id}>
                  <TableCell className="font-medium text-slate-900">
                    <Link href={`/superadmin/tenants/${t.tenant_id}?tab=billing`} className="hover:underline">
                      {t.nombre}
                    </Link>
                  </TableCell>
                  <TableCell className="text-slate-500">{t.plan_name ?? '—'}</TableCell>
                  <TableCell>
                    <Badge variant={BILLING_STATUS_BADGE[t.status] ?? 'secondary'}>
                      {BILLING_STATUS_LABEL[t.status] ?? t.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-slate-500">
                    {t.last_invoice_at ? new Date(t.last_invoice_at).toLocaleDateString('ca-ES') : '—'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">Totes les factures</h3>
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
                <TableHead>Tenant</TableHead>
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
                  <TableCell className="text-slate-700">{inv.tenant_nombre}</TableCell>
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
      </section>
    </div>
  );
}
