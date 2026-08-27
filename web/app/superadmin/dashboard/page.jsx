'use client';

import { useCallback, useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { Badge } from '../../../components/ui/badge';
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from '../../../components/ui/table';
import { superadminAuthFetch } from '../../lib/superadmin-auth';

function activityBadge(row) {
  if (!row.last_order_at) return <Badge variant="secondary">Sense vendes</Badge>;
  if (row.orders_last_7d === 0) return <Badge variant="warning">Sense activitat recent</Badge>;
  return <Badge variant="success">Actiu</Badge>;
}

export default function SuperadminDashboardPage() {
  const [features, setFeatures] = useState(null);
  const [health, setHealth] = useState(null);

  const load = useCallback(async () => {
    const [featuresRes, healthRes] = await Promise.all([
      superadminAuthFetch('/superadmin/dashboard/features'),
      superadminAuthFetch('/superadmin/dashboard/tenant-health'),
    ]);
    if (featuresRes.ok) setFeatures(await featuresRes.json());
    if (healthRes.ok) setHealth(await healthRes.json());
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-8 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Dashboard</h2>
        <p className="text-sm text-slate-500 mt-1">
          Adopció de features i activitat recent dels tenants actius.
        </p>
      </div>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">Adopció de features</h3>
        {features === null ? (
          <div className="flex items-center gap-2 text-slate-500 text-sm">
            <Loader2 size={14} className="animate-spin" /> Carregant...
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {features.map((f) => {
              const pct = f.total_tenants > 0 ? Math.round((f.enabled_count / f.total_tenants) * 100) : 0;
              return (
                <div key={f.feature_key} className="border border-slate-200 rounded-lg px-4 py-3 space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium text-slate-700">{f.label}</span>
                    <span className="text-slate-500">{f.enabled_count} / {f.total_tenants}</span>
                  </div>
                  <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">Salut per tenant</h3>
        {health === null ? (
          <div className="flex items-center gap-2 text-slate-500 text-sm">
            <Loader2 size={14} className="animate-spin" /> Carregant...
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tenant</TableHead>
                <TableHead>Comandes totals</TableHead>
                <TableHead>Comandes (7 dies)</TableHead>
                <TableHead>Última comanda</TableHead>
                <TableHead>Activitat</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {health.map((row) => (
                <TableRow key={row.tenant_id}>
                  <TableCell className="font-medium text-slate-900">{row.nombre}</TableCell>
                  <TableCell className="text-slate-500">{row.total_orders}</TableCell>
                  <TableCell className="text-slate-500">{row.orders_last_7d}</TableCell>
                  <TableCell className="text-slate-500">
                    {row.last_order_at ? new Date(row.last_order_at).toLocaleDateString('ca-ES') : '—'}
                  </TableCell>
                  <TableCell>{activityBadge(row)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>
    </div>
  );
}
