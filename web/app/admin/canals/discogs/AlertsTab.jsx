'use client';

// Pestaña Alertes: bandeja de excepciones accionables del canal + auditoría contra el inventario real de Discogs.

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { Button } from '../../../../components/ui/button';
import MIcon from '../../../../components/ui/m-icon';
import { Badge, CH, ErrorBox, ProgressPanel, api, fmtDate } from './shared';

const KINDS = {
  order_sense_match: 'Comanda sense coincidència', order_conflict: 'Conflicte de comanda',
  order_status_unknown: 'Estat de comanda desconegut', orders_poll_failed: 'Error en consultar comandes',
  listing_error: 'Error de listing', listing_gone: 'Listing desaparegut', sync_failed: 'Sincronització fallida',
  retire_guard: 'Retirades aturades', audit_orphan_listing: 'Listing orfe a Discogs',
  audit_missing_listing: 'Ja no és a Discogs', audit_price_diff: 'Preu diferent', audit_summary: 'Resum d\'auditoria',
};
const SEV = { error: 'bg-red-100 text-red-800', warning: 'bg-amber-100 text-amber-800', info: 'bg-blue-100 text-blue-800' };

export default function AlertsTab({ t, account, estat, reload, goTab }) {
  const [status, setStatus] = useState('open');
  const [kind, setKind] = useState('');
  const [data, setData] = useState({ total: 0, alerts: [], open: {} });
  const [error, setError] = useState('');
  const [auditing, setAuditing] = useState(false);
  const job = estat?.job;
  const auditJob = job && job.mode === 'audit' ? job : null;
  const running = !!auditJob && ['queued', 'running'].includes(auditJob.status);

  const load = useCallback(async () => {
    const p = new URLSearchParams({ status, limit: '100' });
    if (kind) p.set('kind', kind);
    const r = await api(`${CH}/alerts?${p}`);
    if (r.ok) setData(r.data);
  }, [status, kind]);
  useEffect(() => { load(); }, [load, job?.id, job?.status]);

  async function act(id, action) {
    await api(`${CH}/alerts/${id}`, { method: 'POST', body: { action } });
    load();
  }

  async function audit() {
    setError('');
    setAuditing(true);
    const r = await api(`${CH}/audit`, { method: 'POST' });
    setAuditing(false);
    if (!r.ok) { setError(r.data.detail || 'No s\'ha pogut iniciar l\'auditoria.'); return; }
    reload();
  }

  const adopcio = !!account?.adopcio_feta;
  return (
    <div className="space-y-4">
      <ErrorBox>{error}</ErrorBox>
      <div className="bg-card rounded-2xl border border-outline-variant shadow-sm p-5 flex items-center justify-between gap-4 flex-wrap">
        <div>
          <p className="text-sm font-semibold text-on-surface">{t('discogs.alerts.audit', 'Auditoria amb Discogs')}</p>
          <p className="text-xs text-secondary-foreground mt-1 max-w-xl">
            {adopcio
              ? t('discogs.alerts.audit_hint', 'Compara el que l\'app creu publicat amb l\'inventari real de Discogs i obre una alerta per cada diferència. Només llegeix. S\'executa sola cada nit.')
              : t('discogs.alerts.audit_needs_load', 'Disponible quan s\'hagi fet la càrrega inicial (pestanya Sincronització).')}
          </p>
        </div>
        <Button onClick={audit} disabled={!adopcio || running || auditing}>
          <MIcon name={running ? 'progress_activity' : 'fact_check'} size={16} className={running ? 'animate-spin' : ''} />
          {running ? t('discogs.canal.running', 'En marxa…') : t('discogs.alerts.audit_now', 'Auditar ara')}
        </Button>
      </div>
      {running && <ProgressPanel t={t} job={auditJob} />}
      {auditJob && auditJob.status === 'error' && <ErrorBox>{auditJob.error}</ErrorBox>}

      <div className="flex items-center gap-3 flex-wrap">
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="border border-outline-variant rounded-xl px-3 py-2 text-sm bg-card">
          <option value="open">{t('discogs.alerts.s_open', 'Obertes')} ({Object.values(data.open || {}).reduce((a, b) => a + b, 0)})</option>
          <option value="dismissed">{t('discogs.alerts.s_dismissed', 'Descartades')}</option>
          <option value="resolved">{t('discogs.alerts.s_resolved', 'Resoltes')}</option>
          <option value="all">{t('discogs.alerts.s_all', 'Totes')}</option>
        </select>
        <select value={kind} onChange={(e) => setKind(e.target.value)} className="border border-outline-variant rounded-xl px-3 py-2 text-sm bg-card">
          <option value="">{t('discogs.alerts.all_kinds', 'Tots els tipus')}</option>
          {Object.entries(KINDS).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
        </select>
      </div>

      <div className="bg-card rounded-2xl border border-outline-variant shadow-sm divide-y divide-outline-variant">
        {data.alerts.map((a) => (
          <div key={a.id} className="p-4 flex items-start justify-between gap-4">
            <div className="space-y-1 text-sm">
              <div className="flex items-center gap-2 flex-wrap">
                <Badge cls={SEV[a.severity]}>{KINDS[a.kind] || a.kind}</Badge>
                <span className="text-xs text-secondary-foreground">{fmtDate(a.created_at)}{a.occurrences > 1 ? ` · ${a.occurrences}×` : ''}</span>
                {a.status !== 'open' && <Badge>{a.status}</Badge>}
              </div>
              <p className="text-on-surface">{a.message}</p>
              <p className="text-xs flex gap-3">
                {a.order_id && <Link href="/admin/vendes-web" className="text-primary hover:underline">{t('discogs.alerts.see_order', 'Veure comanda')}</Link>}
                {a.item_id && <button type="button" className="text-primary hover:underline" onClick={() => goTab('listings')}>{t('discogs.alerts.see_listings', 'Veure a Listings')}</button>}
                {a.external_id && <a href={`https://www.discogs.com/sell/item/${a.external_id}`} target="_blank" rel="noreferrer" className="text-primary hover:underline">#{a.external_id}</a>}
              </p>
            </div>
            <div className="shrink-0 flex gap-3 text-xs">
              {a.status === 'open' ? (
                <>
                  <button type="button" className="text-primary hover:underline" onClick={() => act(a.id, 'resolve')}>{t('discogs.alerts.resolve', 'Resolta')}</button>
                  <button type="button" className="text-secondary-foreground hover:underline" onClick={() => act(a.id, 'dismiss')}>{t('discogs.alerts.dismiss', 'Descarta')}</button>
                </>
              ) : (
                <button type="button" className="text-primary hover:underline" onClick={() => act(a.id, 'reopen')}>{t('discogs.alerts.reopen', 'Reobre')}</button>
              )}
            </div>
          </div>
        ))}
        {data.alerts.length === 0 && (
          <div className="p-10 text-center text-sm text-secondary-foreground">{t('discogs.alerts.none', 'Cap alerta. Tot en ordre.')}</div>
        )}
      </div>
    </div>
  );
}
