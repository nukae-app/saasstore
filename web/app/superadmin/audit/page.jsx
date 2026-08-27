'use client';

import { useCallback, useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from '../../../components/ui/table';
import { superadminAuthFetch } from '../../lib/superadmin-auth';

const ACTION_LABEL = {
  'tenant.create': 'Tenant creat',
  'tenant.update': 'Tenant editat',
  'tenant.suspend': 'Tenant suspès',
  'tenant.reactivate': 'Tenant reactivat',
  'tenant_feature.toggle': 'Feature modificada',
  'vertical.create': 'Vertical creat',
  'vertical.update': 'Vertical editat',
  'admin.create': 'Operador creat',
  'admin.update': 'Operador editat',
  'plan.create': 'Pla creat',
  'plan.update': 'Pla editat',
  'tenant_billing.update': 'Facturació editada',
};

export default function SuperadminAuditPage() {
  const [entries, setEntries] = useState(null);
  const [tenantsById, setTenantsById] = useState({});

  const load = useCallback(async () => {
    const [logRes, tenantsRes] = await Promise.all([
      superadminAuthFetch('/superadmin/audit-log'),
      superadminAuthFetch('/superadmin/tenants'),
    ]);
    if (tenantsRes.ok) {
      const tenants = await tenantsRes.json();
      setTenantsById(Object.fromEntries(tenants.map((t) => [t.id, t.nombre])));
    }
    if (logRes.ok) setEntries(await logRes.json());
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-5 max-w-4xl">
      <h2 className="text-2xl font-bold text-slate-900">Audit log</h2>
      <p className="text-sm text-slate-500">
        Rastre de les accions de mutació fetes des d&apos;aquest panell (crear/editar/suspendre
        tenants, canviar features). Les 100 més recents.
      </p>

      {entries === null ? (
        <div className="flex items-center gap-2 text-slate-500 text-sm">
          <Loader2 size={14} className="animate-spin" /> Carregant...
        </div>
      ) : entries.length === 0 ? (
        <p className="text-sm text-slate-500">Encara no hi ha cap acció registrada.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Data</TableHead>
              <TableHead>Acció</TableHead>
              <TableHead>Tenant</TableHead>
              <TableHead>Detalls</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.map((e) => (
              <TableRow key={e.id}>
                <TableCell className="text-slate-500 whitespace-nowrap">
                  {new Date(e.created_at).toLocaleString('ca-ES')}
                </TableCell>
                <TableCell className="font-medium text-slate-900">
                  {ACTION_LABEL[e.action] ?? e.action}
                </TableCell>
                <TableCell className="text-slate-500">
                  {e.target_tenant_id ? (tenantsById[e.target_tenant_id] ?? e.target_tenant_id) : '—'}
                </TableCell>
                <TableCell className="text-slate-400 text-xs font-mono">
                  {e.details ? JSON.stringify(e.details) : '—'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
