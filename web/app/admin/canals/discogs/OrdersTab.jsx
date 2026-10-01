'use client';

// Pestaña Comandes: los pedidos de Discogs son los MISMOS pedidos de "Vendes web" (origen discogs); aquí se ven
// filtrados, junto con lo propio del canal: última consulta, incidencias (sin coincidencia, conflicto, estado
// desconocido) y la opción de marcar enviado con seguimiento (que se comunica a Discogs si hay escritura).

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { Button } from '../../../../components/ui/button';
import MIcon from '../../../../components/ui/m-icon';
import { Badge, CH, ErrorBox, Panel, api, fmtDate, fmtPrice } from './shared';

const STATUS = {
  pendiente_pago: { label: 'Pendent de cobrament', cls: 'bg-amber-100 text-amber-800' },
  pagado: { label: 'Pagada', cls: 'bg-blue-100 text-blue-800' },
  enviado: { label: 'Enviada', cls: 'bg-green-100 text-green-800' },
  entregado: { label: 'Entregada', cls: 'bg-green-100 text-green-800' },
  cancelado: { label: 'Cancel·lada', cls: 'bg-surface-container-high text-secondary-foreground' },
};

export default function OrdersTab({ t, account, goTab }) {
  const [orders, setOrders] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [settings, setSettings] = useState(null);
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');
  const [syncing, setSyncing] = useState(false);
  const [shipping, setShipping] = useState(null);   // { id, tracking, carrier }
  const [onlyOpen, setOnlyOpen] = useState(true);

  const load = useCallback(async () => {
    const [o, a, s] = await Promise.all([
      api('/admin/orders?origen=discogs'),
      api(`${CH}/alerts?status=open&limit=100`),
      api(`${CH}/settings`),
    ]);
    if (o.ok) setOrders(o.data);
    if (a.ok) setAlerts(a.data.alerts.filter((x) => x.kind.startsWith('order') || x.kind === 'orders_poll_failed'));
    if (s.ok) setSettings(s.data);
  }, []);
  useEffect(() => { load(); }, [load]);

  async function sync(completa) {
    setSyncing(true);
    setMsg('');
    setError('');
    const r = await api(`/admin/discogs/sync/orders${completa ? '?completa=true' : ''}`, { method: 'POST' });
    setSyncing(false);
    if (!r.ok) { setError(r.data.detail || 'No s\'ha pogut sincronitzar.'); return; }
    const d = r.data;
    setMsg(`${d.creats} noves · ${d.actualitzats} actualitzades · ${d.sense_match} sense coincidència · ${d.conflictes} conflictes · ${d.errors} errors`);
    load();
  }

  async function ship() {
    const r = await api(`/admin/orders/${shipping.id}/status`, {
      method: 'PATCH', body: { status: 'enviado', tracking_number: shipping.tracking || null, carrier: shipping.carrier || null },
    });
    if (!r.ok) { setError(r.data.detail || 'No s\'ha pogut marcar com a enviada.'); return; }
    setShipping(null);
    load();
  }

  async function alertAction(id, action) {
    await api(`${CH}/alerts/${id}`, { method: 'POST', body: { action } });
    load();
  }

  const shown = (orders || []).filter((o) => !onlyOpen || ['pendiente_pago', 'pagado'].includes(o.status));
  const last = settings?.orders_last_result;

  return (
    <div className="space-y-5">
      <ErrorBox>{error}</ErrorBox>
      <Panel>
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="text-sm">
            <p className="font-medium text-on-surface">{t('discogs.orders.last_pull', 'Última consulta de comandes')}: {settings?.orders_last_pull_at ? fmtDate(settings.orders_last_pull_at) : '—'}</p>
            {last && (
              <p className={`text-xs mt-1 ${last.error ? 'text-red-700' : 'text-secondary-foreground'}`}>
                {last.error || `${last.creats} noves · ${last.actualitzats} actualitzades · ${last.sense_match} sense coincidència · ${last.conflictes ?? 0} conflictes`}
              </p>
            )}
            <p className="text-xs text-secondary-foreground mt-1">
              {settings?.orders_auto
                ? `${t('discogs.orders.auto_on', 'Es consulten soles cada')} ${settings.orders_poll_minutes} min (${t('discogs.orders.after_load', 'un cop feta la càrrega inicial')}).`
                : t('discogs.orders.auto_off', 'La consulta automàtica està apagada (Configuració).')}
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Button variant="secondary" size="sm" onClick={() => sync(true)} disabled={syncing} title={t('discogs.orders.full_hint', 'Ignora l\'últim punt i mira els darrers 60 dies')}>
              {t('discogs.orders.full', 'Revisar 60 dies')}
            </Button>
            <Button size="sm" onClick={() => sync(false)} disabled={syncing}>
              <MIcon name="refresh" size={14} className={syncing ? 'animate-spin' : ''} /> {t('discogs.orders.sync_now', 'Sincronitzar ara')}
            </Button>
          </div>
        </div>
        {msg && <p className="text-xs text-secondary-foreground">{msg}</p>}
      </Panel>

      {alerts.length > 0 && (
        <Panel title={t('discogs.orders.issues', 'Incidències de comandes')} className="border-red-200">
          <ul className="divide-y divide-outline-variant text-sm">
            {alerts.map((a) => (
              <li key={a.id} className="py-2 flex items-start justify-between gap-3">
                <div>
                  <Badge cls={a.severity === 'error' ? 'bg-red-100 text-red-800' : 'bg-amber-100 text-amber-800'}>{a.kind.replace('order_', '').replace('_', ' ')}</Badge>
                  <span className="ml-2">{a.message}</span>
                  <span className="ml-2 text-xs text-secondary-foreground">{fmtDate(a.created_at)}</span>
                </div>
                <div className="shrink-0 flex gap-3 text-xs">
                  <button type="button" className="text-primary hover:underline" onClick={() => alertAction(a.id, 'resolve')}>{t('discogs.alerts.resolve', 'Resolta')}</button>
                  <button type="button" className="text-secondary-foreground hover:underline" onClick={() => alertAction(a.id, 'dismiss')}>{t('discogs.alerts.dismiss', 'Descarta')}</button>
                </div>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <div className="bg-card rounded-2xl border border-outline-variant shadow-sm overflow-hidden">
        <div className="p-4 flex items-center justify-between gap-3 flex-wrap border-b border-outline-variant">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={onlyOpen} onChange={(e) => setOnlyOpen(e.target.checked)} />
            {t('discogs.orders.only_open', 'Només obertes (pendents d\'enviar)')}
          </label>
          <Link href="/admin/vendes-web" className="text-xs text-primary hover:underline">{t('discogs.orders.all_sales', 'Veure totes les vendes online (web i Discogs) →')}</Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-surface-container-high text-xs text-secondary-foreground border-b border-outline-variant">
              <tr>
                <th className="px-4 py-3 text-left font-medium">{t('discogs.orders.col_order', 'Comanda')}</th>
                <th className="px-4 py-3 text-left font-medium">{t('discogs.orders.col_buyer', 'Comprador')}</th>
                <th className="px-4 py-3 text-left font-medium">{t('discogs.listings.col_state', 'Estat')}</th>
                <th className="px-4 py-3 text-right font-medium">Total</th>
                <th className="px-4 py-3 text-left font-medium">{t('discogs.canal.col_date', 'Data')}</th>
                <th className="px-4 py-3 text-left font-medium">{t('discogs.orders.col_tracking', 'Seguiment')}</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {orders === null && <tr><td colSpan={7} className="px-4 py-8 text-center text-secondary-foreground">{t('common.loading')}</td></tr>}
              {shown.map((o) => (
                <tr key={o.id} className="border-b border-outline-variant last:border-0">
                  <td className="px-4 py-2.5">
                    <a href={`https://www.discogs.com/sell/order/${o.discogs_order_id}`} target="_blank" rel="noreferrer" className="text-primary hover:underline">{o.discogs_order_id}</a>
                  </td>
                  <td className="px-4 py-2.5 text-secondary-foreground">{(o.email || '').replace('@discogs-buyer.local', '')}</td>
                  <td className="px-4 py-2.5"><Badge cls={STATUS[o.status]?.cls}>{STATUS[o.status]?.label || o.status}</Badge></td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{fmtPrice(o.total)}</td>
                  <td className="px-4 py-2.5 text-secondary-foreground">{fmtDate(o.created_at)}</td>
                  <td className="px-4 py-2.5 text-secondary-foreground">{o.numero_seguiment || '—'}</td>
                  <td className="px-4 py-2.5 text-right">
                    {['pendiente_pago', 'pagado'].includes(o.status) && (
                      <button type="button" className="text-xs text-primary hover:underline" onClick={() => setShipping({ id: o.id, tracking: '', carrier: '' })}>
                        {t('discogs.orders.mark_shipped', 'Marcar enviada')}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {orders !== null && shown.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-10 text-center text-secondary-foreground">{t('discogs.orders.none', 'Cap comanda de Discogs.')}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {shipping && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-card rounded-2xl border border-outline-variant shadow-xl max-w-md w-full p-6 space-y-4">
            <p className="text-lg font-semibold text-on-surface">{t('discogs.orders.ship_title', 'Marcar com a enviada')}</p>
            <input value={shipping.tracking} onChange={(e) => setShipping({ ...shipping, tracking: e.target.value })}
              placeholder={t('discogs.orders.tracking_ph', 'Número de seguiment')} className="w-full border border-outline-variant rounded-xl px-3 py-2 text-sm bg-card" />
            <input value={shipping.carrier} onChange={(e) => setShipping({ ...shipping, carrier: e.target.value })}
              placeholder={t('discogs.orders.carrier_ph', 'Transportista')} className="w-full border border-outline-variant rounded-xl px-3 py-2 text-sm bg-card" />
            <p className="text-xs text-secondary-foreground">
              {account?.solo_lectura
                ? t('discogs.orders.ship_ro', 'Mode només lectura: es marcarà enviada a l\'app però NO es comunicarà a Discogs.')
                : t('discogs.orders.ship_rw', 'També es marcarà com a enviada a Discogs, amb el seguiment.')}
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setShipping(null)}>{t('common.cancel', 'Cancel·la')}</Button>
              <Button onClick={ship}>{t('discogs.orders.ship_confirm', 'Marcar enviada')}</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
