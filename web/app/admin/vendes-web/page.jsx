'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { authFetch } from '../../lib/auth';
import { useT } from '../../lib/i18n';
import { Button } from '../../../components/ui/button';
import ReturnSaleModal from '../../../components/admin/ReturnSaleModal';
import { useSortFilter } from '../../../components/admin/table/useSortFilter';
import { SortableTh } from '../../../components/admin/table/SortableTh';
import Link from 'next/link';
import { X, RotateCcw, Truck, RefreshCw, Store, Clock, CreditCard, Printer, Search } from 'lucide-react';

const STATUS_COLOR = {
  pendiente_pago: 'bg-yellow-100 text-yellow-700',
  pagado:         'bg-blue-100 text-blue-700',
  enviado:        'bg-purple-100 text-purple-700',
  entregado:      'bg-green-100 text-green-700',
  cancelado:      'bg-zinc-100 text-zinc-500',
};
const STATUS_KEY = {
  pendiente_pago: 'order.status.pending',
  pagado:         'order.status.paid',
  enviado:        'order.status.shipped',
  entregado:      'order.status.delivered',
  cancelado:      'order.status.cancelled',
};
// Un pedido puede tener varios intentos de pago Redsys (p. ej. uno denegado
// y luego un reintento autorizado): se listan todos, más reciente primero.
const PAYMENT_STATUS_COLOR = {
  creado:     'bg-zinc-100 text-zinc-500',
  autorizado: 'bg-green-100 text-green-700',
  denegado:   'bg-red-100 text-red-700',
  error:      'bg-amber-100 text-amber-700',
};
const PAYMENT_STATUS_FALLBACK = {
  creado:     'Creat',
  autorizado: 'Autoritzat',
  denegado:   'Denegat',
  error:      'Error',
};
function paymentStatusLabel(t, estat) {
  return t(`orders.payment_status.${estat}`, PAYMENT_STATUS_FALLBACK[estat] ?? estat);
}
// Una comanda neix "pendiente_pago": si es paga amb targeta (Redsys), el pas
// a "pagado" l'automatitza la notificació del banc; si es paga a la botiga
// (recollida en persona), un admin la marca com pagada aquí a mà. Un cop
// pagada, l'estoc ja està venut i no torna a canviar de mans entre
// pagat/enviat/entregat: es poden moure lliurement en qualsevol direcció
// per corregir errades. Cancel·lar allibera l'estoc, així que només val
// abans d'entregar, i mai es pot desfer (l'exemplar pot haver-se venut a
// algú altre mentre estava alliberat).
const ESTATS_LOGISTICS = ['pagado', 'enviado', 'entregado'];
const ESTATS_CANCELABLES = new Set(['pendiente_pago', 'pagado', 'enviado']);
const RETURNABLE = new Set(['pagado', 'enviado', 'entregado']);
const TAB_RECOLLIDA = '__recollida_botiga__';

// Dades fiscals de la botiga (remitent) per a l'etiqueta d'enviament impresa.
function useShopConfig() {
  const [config, setConfig] = useState(null);
  useEffect(() => {
    authFetch('/admin/configuracio')
      .then(r => (r.ok ? r.json() : null))
      .then(setConfig)
      .catch(() => {});
  }, []);
  return config;
}

export default function VendesWebPage() {
  const t = useT();
  const [orders, setOrders] = useState([]);
  const [reservesBotiga, setReservesBotiga] = useState([]);
  const [ordersTiendaPendents, setOrdersTiendaPendents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState(null);
  const [selected, setSelected] = useState(null);
  const [updating, setUpdating] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState('');
  const [q, setQ] = useState('');
  const [metodoEnvioFilter, setMetodoEnvioFilter] = useState('');
  const [metodoPagoFilter, setMetodoPagoFilter] = useState('');
  const [origenFilter, setOrigenFilter] = useState('');
  const shopConfig = useShopConfig();

  const TABS = [
    { key: null,             label: t('orders.tab.all') },
    { key: 'pagado',         label: t('orders.tab.paid') },
    { key: 'enviado',        label: t('orders.tab.shipped') },
    { key: TAB_RECOLLIDA,    label: t('orders.tab.pickup_pending', 'Pendents de recollir') },
    { key: 'entregado',      label: t('orders.tab.delivered') },
    { key: 'cancelado',      label: t('orders.tab.cancelled') },
    { key: 'pendiente_pago', label: t('orders.tab.pending') }, // legacy
  ];

  const load = useCallback(async () => {
    setLoading(true);
    if (tab === TAB_RECOLLIDA) {
      const [rOrders, rPeticions, rOrdersTienda] = await Promise.all([
        authFetch('/admin/orders?status=pagado'),
        authFetch('/admin/peticiones/reserves-recollida'),
        authFetch('/admin/orders/pendientes-tienda'),
      ]);
      const totesPagades = await rOrders.json();
      setOrders(totesPagades.filter(o => o.metodo_envio === 'recogida_tienda'));
      setReservesBotiga(rPeticions.ok ? await rPeticions.json() : []);
      setOrdersTiendaPendents(rOrdersTienda.ok ? await rOrdersTienda.json() : []);
      setLoading(false);
      return;
    }
    const params = new URLSearchParams();
    if (tab) params.set('status', tab);
    if (q.trim()) params.set('q', q.trim());
    if (metodoEnvioFilter) params.set('metodo_envio', metodoEnvioFilter);
    if (metodoPagoFilter) params.set('metodo_pago', metodoPagoFilter);
    if (origenFilter) params.set('origen', origenFilter);
    const qs = params.toString();
    const r = await authFetch(`/admin/orders${qs ? `?${qs}` : ''}`);
    setOrders(await r.json());
    setReservesBotiga([]);
    setOrdersTiendaPendents([]);
    setLoading(false);
  }, [tab, q, metodoEnvioFilter, metodoPagoFilter, origenFilter]);

  useEffect(() => { load(); }, [load]);

  const ordersColumns = useMemo(() => ({
    created_at: { sortValue: o => o.created_at ?? '' },
    email: { sortValue: o => (o.email ?? '').toLowerCase() },
    metodo_envio: { sortValue: o => o.metodo_envio === 'recogida_tienda' ? t('orders.shipping.pickup') : t('orders.shipping.delivery') },
    total: { sortValue: o => parseFloat(o.total) || 0 },
    status: { sortValue: o => t(STATUS_KEY[o.status] ?? o.status) },
  }), [t]);
  const { rows: ordersSorted, sort: ordersSort, toggleSort: toggleOrdersSort } = useSortFilter(orders, ordersColumns);

  async function updateOrder(orderId, payload) {
    setUpdating(true);
    const r = await authFetch(`/admin/orders/${orderId}/status`, {
      method: 'PATCH', body: JSON.stringify(payload),
    });
    setUpdating(false);
    if (r.ok) {
      const detail = await authFetch(`/admin/orders/${orderId}`);
      setSelected(await detail.json());
      load();
    }
    return r;
  }

  async function openDetail(order) {
    const r = await authFetch(`/admin/orders/${order.id}`);
    setSelected(await r.json());
  }

  async function marcarRecollit(order) {
    setUpdating(true);
    await authFetch(`/admin/orders/${order.id}/status`, {
      method: 'PATCH', body: JSON.stringify({ status: 'entregado' }),
    });
    setUpdating(false);
    load();
  }

  async function avisarRecollida(orderId) {
    setUpdating(true);
    const r = await authFetch(`/admin/orders/${orderId}/avisar-recollida`, { method: 'POST' });
    setUpdating(false);
    if (r.ok) {
      const detail = await authFetch(`/admin/orders/${orderId}`);
      setSelected(await detail.json());
      load();
    }
    return r;
  }

  async function syncDiscogs() {
    setSyncing(true);
    setSyncMsg('');
    try {
      const r = await authFetch('/admin/discogs/sync/orders', { method: 'POST' });
      const data = await r.json();
      setSyncMsg(t('orders.sync.result', 'Sincronitzat: {n} noves, {a} actualitzades')
        .replace('{n}', data.creats ?? 0).replace('{a}', data.actualitzats ?? 0));
      load();
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div className="space-y-5 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-zinc-900">{t('orders.title')}</h2>
        <div className="flex items-center gap-3">
          {syncMsg && <span className="text-xs text-zinc-500">{syncMsg}</span>}
          <Button variant="secondary" size="sm" onClick={syncDiscogs} disabled={syncing}>
            <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
            {syncing ? t('orders.sync.loading', 'Sincronitzant...') : t('orders.sync.btn', 'Sincronitzar amb Discogs')}
          </Button>
        </div>
      </div>

      <div className="flex gap-1 bg-zinc-100 p-1 rounded-xl w-fit flex-wrap">
        {TABS.map(({ key, label }) => (
          <button key={key ?? 'all'} onClick={() => setTab(key)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${tab === key ? 'bg-white text-zinc-900 shadow-sm' : 'text-zinc-600 hover:text-zinc-900'}`}>
            {label}
          </button>
        ))}
      </div>

      {tab !== TAB_RECOLLIDA && (
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative flex-1 min-w-[220px]">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
            <input value={q} onChange={e => setQ(e.target.value)}
              placeholder={t('orders.search_ph', 'Cerca per email, disc o comanda de Discogs...')}
              className="w-full pl-9 pr-4 py-2 border border-zinc-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white" />
          </div>
          <select value={metodoEnvioFilter} onChange={e => setMetodoEnvioFilter(e.target.value)}
            className="border border-zinc-200 rounded-xl px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-zinc-900">
            <option value="">{t('orders.col.shipping')}: {t('orders.filter.all', 'tots')}</option>
            <option value="envio">{t('orders.shipping.delivery')}</option>
            <option value="recogida_tienda">{t('orders.shipping.pickup')}</option>
          </select>
          <select value={metodoPagoFilter} onChange={e => setMetodoPagoFilter(e.target.value)}
            className="border border-zinc-200 rounded-xl px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-zinc-900">
            <option value="">{t('tpv.col.pago')}: {t('orders.filter.all', 'tots')}</option>
            <option value="redsys">{t('orders.payment.card_redsys', 'Targeta (Redsys)')}</option>
            <option value="tienda">{t('orders.payment.pay_on_pickup', 'Paga en recollir')}</option>
          </select>
          <select value={origenFilter} onChange={e => setOrigenFilter(e.target.value)}
            className="border border-zinc-200 rounded-xl px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-zinc-900">
            <option value="">{t('orders.col.origin', 'Origen')}: {t('orders.filter.all', 'tots')}</option>
            <option value="web">{t('orders.origin.web', 'Web')}</option>
            <option value="discogs">Discogs</option>
            <option value="subscripcio">{t('orders.origin.subscription', 'Subscripció')}</option>
          </select>
          {(q || metodoEnvioFilter || metodoPagoFilter || origenFilter) && (
            <button
              onClick={() => { setQ(''); setMetodoEnvioFilter(''); setMetodoPagoFilter(''); setOrigenFilter(''); }}
              className="text-xs text-zinc-500 hover:text-zinc-900 font-medium px-2">
              {t('orders.clear_filters', 'Netejar filtres')}
            </button>
          )}
        </div>
      )}

      {tab === TAB_RECOLLIDA ? (
        <RecollidaBotigaTab
          orders={orders} reservesBotiga={reservesBotiga} ordersTiendaPendents={ordersTiendaPendents}
          loading={loading}
          onMarcarRecollit={marcarRecollit}
          updating={updating}
        />
      ) : (
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
          {loading ? (
            <div className="p-12 text-center text-zinc-400 text-sm">{t('orders.loading')}</div>
          ) : orders.length === 0 ? (
            <div className="p-12 text-center text-zinc-400 text-sm">{t('orders.no_results')}</div>
          ) : (
            <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
                <tr>
                  <SortableTh label={t('orders.col.date')} sortKey="created_at" sort={ordersSort} onSort={toggleOrdersSort} />
                  <SortableTh label={t('orders.col.email')} sortKey="email" sort={ordersSort} onSort={toggleOrdersSort} />
                  <SortableTh label={t('orders.col.shipping')} sortKey="metodo_envio" sort={ordersSort} onSort={toggleOrdersSort} />
                  <SortableTh label={t('tpv.resum.total')} sortKey="total" sort={ordersSort} onSort={toggleOrdersSort} align="right" />
                  <SortableTh label={t('purchases.col.status', 'Estat')} sortKey="status" sort={ordersSort} onSort={toggleOrdersSort} />
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {ordersSorted.map(o => (
                  <tr key={o.id} className="hover:bg-zinc-50 transition-colors">
                    <td className="px-5 py-3 text-zinc-500">{new Date(o.created_at).toLocaleDateString()}</td>
                    <td className="px-5 py-3 font-medium">{o.email}</td>
                    <td className="px-5 py-3 text-zinc-500">
                      {o.metodo_envio === 'recogida_tienda' ? t('orders.shipping.pickup') : t('orders.shipping.delivery')}
                    </td>
                    <td className="px-5 py-3 text-right font-semibold">{o.total} €</td>
                    <td className="px-5 py-3">
                      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLOR[o.status] ?? 'bg-zinc-100 text-zinc-700'}`}>
                        {t(STATUS_KEY[o.status] ?? o.status)}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-right">
                      <button onClick={() => openDetail(o)} className="text-zinc-900 hover:text-zinc-600 text-xs font-semibold">
                        {t('common.detail')}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          )}
        </div>
      )}

      {selected && (
        <OrderDetail
          order={selected}
          shopConfig={shopConfig}
          onClose={() => setSelected(null)}
          onUpdate={updateOrder}
          onAvisarRecollida={avisarRecollida}
          onReturned={() => { openDetail(selected); load(); }}
          updating={updating}
        />
      )}
    </div>
  );
}

function horesRestants(reservedUntil) {
  const ms = new Date(reservedUntil).getTime() - Date.now();
  if (ms <= 0) return null;
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor((ms % 3_600_000) / 60_000);
  return `${h}h ${m}m`;
}

function RecollidaBotigaTab({ orders, reservesBotiga, ordersTiendaPendents, loading, onMarcarRecollit, updating }) {
  const t = useT();
  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-12 text-center text-zinc-400 text-sm">
        {t('common.loading')}
      </div>
    );
  }
  const llestes = orders.filter(o => !o.pendent_arribada);
  const esperantExemplar = orders.filter(o => o.pendent_arribada);

  if (orders.length === 0 && reservesBotiga.length === 0 && ordersTiendaPendents.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-12 text-center text-zinc-400 text-sm">
        <Store size={28} className="text-zinc-200 mx-auto mb-3" />
        {t('orders.pickup.no_pending', 'Cap disc pendent de recollir a botiga.')}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {llestes.length > 0 && (
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
          <div className="px-5 py-3 bg-zinc-50 text-xs font-semibold text-zinc-500 uppercase tracking-wide border-b border-zinc-100">
            {t('orders.pickup.paid_waiting_client', 'Comandes web pagades, esperant que el client vingui')}
          </div>
          <div className="divide-y divide-zinc-100">
            {llestes.map(o => (
              <div key={o.id} className="flex items-center gap-4 px-5 py-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-zinc-800">{o.email}</p>
                  <p className="text-xs text-zinc-400">{new Date(o.created_at).toLocaleDateString()}</p>
                </div>
                <span className="font-semibold text-zinc-900 shrink-0">{o.total} €</span>
                <button onClick={() => onMarcarRecollit(o)} disabled={updating}
                  className="bg-primary hover:bg-zinc-800 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors disabled:opacity-60 shrink-0">
                  {t('orders.pickup.collected_by_client', 'Recollit pel client')}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {esperantExemplar.length > 0 && (
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
          <div className="px-5 py-3 bg-zinc-50 text-xs font-semibold text-zinc-500 uppercase tracking-wide border-b border-zinc-100">
            {t('orders.pickup.paid_waiting_supplier', "Ja pagades, esperant que arribi l'exemplar del proveïdor")}
          </div>
          <div className="divide-y divide-zinc-100">
            {esperantExemplar.map(o => (
              <div key={o.id} className="flex items-center gap-4 px-5 py-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-zinc-800">{o.email}</p>
                  <p className="text-xs text-zinc-400">{new Date(o.created_at).toLocaleDateString()}</p>
                </div>
                <span className="font-semibold text-zinc-900 shrink-0">{o.total} €</span>
                <Link href="/admin/peticions"
                  className="text-xs font-semibold text-amber-600 hover:text-amber-700 border border-amber-200 rounded-lg px-3 py-1.5 hover:bg-amber-50 transition-colors shrink-0">
                  {t('orders.pickup.see_in_requests', 'Veure a Peticions')}
                </Link>
              </div>
            ))}
          </div>
        </div>
      )}

      {ordersTiendaPendents.length > 0 && (
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
          <div className="px-5 py-3 bg-zinc-50 text-xs font-semibold text-zinc-500 uppercase tracking-wide border-b border-zinc-100">
            {t('orders.pickup.reserved_orders', 'Comandes web reservades, pendents de pagar i recollir (72h)')}
          </div>
          <div className="divide-y divide-zinc-100">
            {ordersTiendaPendents.map(o => {
              const restant = o.reserved_until ? horesRestants(o.reserved_until) : null;
              return (
                <div key={o.order_id} className="flex items-center gap-4 px-5 py-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-zinc-800 truncate">
                      {o.items.map(it => `${it.artista} — ${it.titulo}`).join(', ')}
                    </p>
                    <p className="text-xs text-zinc-400 truncate">{o.email}</p>
                  </div>
                  {restant && (
                    <span className="flex items-center gap-1 text-xs text-red-500 shrink-0"><Clock size={11} /> {restant}</span>
                  )}
                  <span className="font-semibold text-zinc-900 shrink-0">{o.total} €</span>
                  <Link href="/admin/tpv"
                    className="bg-primary hover:bg-zinc-800 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors shrink-0">
                    {t('orders.pickup.charge_at_tpv', 'Cobrar al TPV')}
                  </Link>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {reservesBotiga.length > 0 && (
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
          <div className="px-5 py-3 bg-zinc-50 text-xs font-semibold text-zinc-500 uppercase tracking-wide border-b border-zinc-100">
            {t('orders.pickup.reserved_requests', 'Peticions reservades, pendents de pagar i recollir (72h)')}
          </div>
          <div className="divide-y divide-zinc-100">
            {reservesBotiga.map(r => {
              const restant = r.reserved_until ? horesRestants(r.reserved_until) : null;
              return (
                <div key={r.peticion_id} className="flex items-center gap-4 px-5 py-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-zinc-800 truncate">{r.artista} — {r.titulo}</p>
                    <p className="text-xs text-zinc-400 truncate">{r.user_nombre || r.user_email}</p>
                  </div>
                  {restant && (
                    <span className="flex items-center gap-1 text-xs text-red-500 shrink-0"><Clock size={11} /> {restant}</span>
                  )}
                  <span className="font-semibold text-zinc-900 shrink-0">{r.precio} €</span>
                  <Link href="/admin/tpv"
                    className="bg-primary hover:bg-zinc-800 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors shrink-0">
                    {t('orders.pickup.sell_at_tpv', 'Vendre al TPV')}
                  </Link>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function OrderDetail({ order, shopConfig, onClose, onUpdate, onAvisarRecollida, onReturned, updating }) {
  const t = useT();
  const esRecollida = order.metodo_envio === 'recogida_tienda';
  const canReturn = RETURNABLE.has(order.status);
  const potImprimirEtiqueta = order.metodo_envio === 'envio' && !!order.direccion_envio;
  const [returnItem, setReturnItem] = useState(null);
  const [shipping, setShipping] = useState(false);
  const [editingMetode, setEditingMetode] = useState(false);
  const [statusError, setStatusError] = useState('');
  const [avisError, setAvisError] = useState('');

  let available = [];
  if (order.status === 'pendiente_pago') {
    available = ['pagado'];
  } else if (ESTATS_LOGISTICS.includes(order.status)) {
    available = ESTATS_LOGISTICS.filter(s => s !== order.status);
  }
  if (ESTATS_CANCELABLES.has(order.status)) {
    available = [...available, 'cancelado'];
  }

  const pendentArribada = order.items?.some(it => it.pendent_arribada);
  const potAvisarRecollida = esRecollida && order.status === 'pagado' && !pendentArribada;

  async function handleChangeStatus(status, extra) {
    setStatusError('');
    const r = await onUpdate(order.id, { status, ...extra });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      setStatusError(d.detail || t('orders.detail.status_error', "No s'ha pogut canviar l'estat."));
    }
  }

  async function handleAvisarRecollida() {
    setAvisError('');
    const r = await onAvisarRecollida(order.id);
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      setAvisError(d.detail || t('orders.detail.notify_error', "No s'ha pogut avisar el client."));
    }
  }

  return (
    <>
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
          <h3 className="font-bold text-zinc-900">{t('orders.detail.order')} #{order.id?.slice(0, 8)}</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 p-1 rounded-lg hover:bg-zinc-100"><X size={20} /></button>
        </div>

        <div className="p-6 space-y-5">
          <div className="grid grid-cols-2 gap-4">
            <InfoBlock label={t('purchases.col.email', 'Email')} value={order.email} />
            <InfoBlock label={t('tpv.resum.total')} value={<span className="text-xl font-bold">{order.total} €</span>} />
            <InfoBlock label={t('orders.col.shipping')} value={
              <span className="inline-flex items-center gap-2">
                {order.metodo_envio === 'recogida_tienda' ? t('orders.detail.pickup') : t('orders.detail.delivery')}
                {order.status !== 'cancelado' && (
                  <button onClick={() => setEditingMetode(v => !v)} className="text-zinc-900 hover:text-zinc-600 text-xs font-medium">
                    {t('orders.detail.change_short', 'Canviar')}
                  </button>
                )}
              </span>
            } />
            <InfoBlock label={t('tpv.confirm.pago')}
              value={order.metodo_pago === 'tienda' ? t('orders.payment.at_shop', 'A la botiga') : t('orders.payment.card_redsys', 'Targeta (Redsys)')} />
            <InfoBlock label={t('orders.col.date')}
              value={new Date(order.created_at).toLocaleDateString(undefined, { day: '2-digit', month: 'long', year: 'numeric' })} />
            <InfoBlock label={t('purchases.col.status', 'Estat')} value={
              <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLOR[order.status]}`}>
                {t(STATUS_KEY[order.status])}
              </span>
            } />
            {order.numero_seguiment && (
              <InfoBlock label={t('orders.detail.tracking')} value={
                <span className="inline-flex items-center gap-1.5">
                  <Truck size={14} className="text-zinc-400" />
                  {order.numero_seguiment}{order.transportista ? ` · ${order.transportista}` : ''}
                </span>
              } />
            )}
          </div>

          {potImprimirEtiqueta && (
            <div className="flex justify-end">
              <Button size="sm" variant="secondary" onClick={() => window.print()}>
                <Printer size={14} /> {t('orders.detail.print_shipping_label', "Imprimir etiqueta d'enviament")}
              </Button>
            </div>
          )}

          {editingMetode && (
            <MetodeEditor
              order={order}
              onCancel={() => setEditingMetode(false)}
              onConfirm={async (payload) => {
                const r = await onUpdate(order.id, payload);
                if (r.ok) setEditingMetode(false);
                return r;
              }}
              updating={updating}
            />
          )}

          {order.metodo_pago === 'redsys' && order.payments?.length > 0 && (
            <div className="shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] rounded-xl overflow-hidden">
              <div className="px-4 py-2.5 bg-zinc-50 text-xs font-semibold text-zinc-500 uppercase tracking-wide border-b border-zinc-100 flex items-center gap-1.5">
                <CreditCard size={13} /> {t('orders.detail.redsys_payment', 'Pagament Redsys')}
              </div>
              <div className="divide-y divide-zinc-100">
                {order.payments.map(p => (
                  <div key={p.id} className="flex items-center justify-between px-4 py-2.5 gap-3 text-sm">
                    <div className="min-w-0">
                      <div className="font-mono text-xs text-zinc-500">Ds_Order {p.ds_order}</div>
                      {p.ds_authorisation_code && (
                        <div className="text-xs text-zinc-400">{t('orders.detail.authorization', 'Autorització')} {p.ds_authorisation_code}</div>
                      )}
                    </div>
                    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium shrink-0 ${PAYMENT_STATUS_COLOR[p.estado] ?? 'bg-zinc-100 text-zinc-700'}`}>
                      {paymentStatusLabel(t, p.estado)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Items amb opció de devolució */}
          {(order.items?.length > 0) && (
            <div className="shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] rounded-xl overflow-hidden">
              <div className="px-4 py-2.5 bg-zinc-50 text-xs font-semibold text-zinc-500 uppercase tracking-wide border-b border-zinc-100">
                {t('return.items_title')}
              </div>
              <div className="divide-y divide-zinc-100">
                {order.items.map(it => (
                  <div key={it.order_item_id} className="flex items-center justify-between px-4 py-3 gap-3">
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-zinc-900 truncate">{it.artista} — {it.titulo}</div>
                      <div className="text-xs text-zinc-400">{it.precio} € {it.estado_disco ? `· ${it.estado_disco}` : ''}</div>
                    </div>
                    {it.pendent_arribada ? (
                      <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-amber-100 text-amber-700 shrink-0">
                        {t('orders.detail.pending_arrival', "Pendent d'arribar")}
                      </span>
                    ) : it.devuelto ? (
                      <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-zinc-100 text-zinc-500 shrink-0">
                        {t('return.returned')}
                      </span>
                    ) : canReturn ? (
                      <button
                        onClick={() => setReturnItem(it)}
                        className="flex items-center gap-1.5 text-xs font-semibold text-zinc-900 hover:text-zinc-600 shrink-0 border border-zinc-300 rounded-lg px-2.5 py-1.5 hover:bg-zinc-50 transition-colors"
                      >
                        <RotateCcw size={13} /> {t('return.btn')}
                      </button>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          )}

          {order.notas && (
            <div className="p-3 bg-zinc-50 rounded-xl text-sm text-zinc-600">
              <div className="text-xs text-zinc-400 mb-1 font-medium">{t('common.notes')}</div>
              {order.notas}
            </div>
          )}

          {potAvisarRecollida && (
            <div className="border-t border-zinc-100 pt-4">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <p className="text-sm text-zinc-600">
                  {order.avisada_recollida_at
                    ? `${t('orders.detail.client_notified_on', 'Client avisat el')} ${new Date(order.avisada_recollida_at).toLocaleDateString()}`
                    : t('orders.detail.client_not_notified', 'El client encara no sap que ja el pot recollir.')}
                </p>
                <Button size="sm" variant={order.avisada_recollida_at ? 'secondary' : 'default'}
                  disabled={updating} onClick={handleAvisarRecollida}>
                  <Store size={14} />
                  {order.avisada_recollida_at ? t('orders.detail.notify_again', 'Tornar a avisar') : t('orders.detail.notify_ready', 'Avisar client — ja el pot recollir')}
                </Button>
              </div>
              {avisError && <p className="text-xs text-red-600 mt-2">{avisError}</p>}
            </div>
          )}

          {shipping ? (
            <ShipForm
              order={order}
              onCancel={() => setShipping(false)}
              onConfirm={async (extra) => {
                await handleChangeStatus('enviado', extra);
                setShipping(false);
              }}
              updating={updating}
            />
          ) : available.length > 0 && (
            <div className="border-t border-zinc-100 pt-4">
              <div className="text-xs text-zinc-500 mb-2 font-medium">{t('orders.detail.change')}</div>
              <div className="flex gap-2 flex-wrap">
                {available.map(s => (
                  <Button key={s} variant={s === 'cancelado' ? 'danger' : 'default'} size="sm"
                    disabled={updating}
                    onClick={() => s === 'enviado' ? setShipping(true) : handleChangeStatus(s)}>
                    {esRecollida && s === 'entregado' ? t('orders.pickup.collected_by_client', 'Recollit pel client') : t(STATUS_KEY[s])}
                  </Button>
                ))}
              </div>
              {statusError && <p className="text-xs text-red-600 mt-2">{statusError}</p>}
            </div>
          )}
        </div>
      </div>

      {returnItem && (
        <ReturnSaleModal
          sale={{ item_id: returnItem.item_id, artista: returnItem.artista, titulo: returnItem.titulo,
                  precio: returnItem.precio, order_item_id: returnItem.order_item_id }}
          onClose={() => setReturnItem(null)}
          onSaved={() => { setReturnItem(null); onReturned(); }}
        />
      )}
    </div>

    {/* Contingut invisible en pantalla, mostrat només via window.print() (veure @media print a globals.css) */}
    {potImprimirEtiqueta && (
      <div id="print-area">
        <div className="shipping-label">
          <div className="text-xs uppercase tracking-wide">Remitent</div>
          {shopConfig ? (
            <>
              <div className="font-semibold">{shopConfig.fiscal_name}</div>
              <div>{shopConfig.address}</div>
              {shopConfig.phone && <div>{shopConfig.phone}</div>}
            </>
          ) : (
            <div>—</div>
          )}
          <hr />
          <div className="text-xs uppercase tracking-wide">Destinatari</div>
          <div className="font-semibold text-lg">{order.direccion_envio.recipient_name}</div>
          <div>{order.direccion_envio.address_line1}</div>
          {order.direccion_envio.address_line2 && <div>{order.direccion_envio.address_line2}</div>}
          <div>{order.direccion_envio.postal_code} {order.direccion_envio.city}</div>
          {order.direccion_envio.province && <div>{order.direccion_envio.province}</div>}
          <div>{order.direccion_envio.country || 'ES'}</div>
          {order.direccion_envio.phone && <div>Tel. {order.direccion_envio.phone}</div>}
          <hr />
          <div>Comanda #{order.id?.slice(0, 8)}</div>
          {order.numero_seguiment && (
            <div>{order.transportista ? `${order.transportista} — ` : ''}{order.numero_seguiment}</div>
          )}
        </div>
      </div>
    )}
    </>
  );
}

function MetodeEditor({ order, onCancel, onConfirm, updating }) {
  const t = useT();
  const [metode, setMetode] = useState(order.metodo_envio);
  const [form, setForm] = useState({ recipient_name: '', address_line1: '', city: '', postal_code: '' });
  const [error, setError] = useState('');

  async function confirm() {
    setError('');
    const payload = { shipping_method: metode };
    if (metode === 'envio' && !order.direccion_envio) {
      payload.shipping_address = { ...form, country: 'ES' };
    }
    const r = await onConfirm(payload);
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      setError(d.detail || t('orders.detail.change_method_error', "No s'ha pogut canviar el mètode."));
    }
  }

  return (
    <div className="border border-zinc-200 rounded-xl p-4 space-y-3 bg-zinc-50">
      <div className="flex gap-2">
        {[['recogida_tienda', t('orders.detail.pickup')], ['envio', t('orders.detail.delivery')]].map(([val, label]) => (
          <button key={val} type="button" onClick={() => setMetode(val)}
            className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-colors ${metode === val ? 'border-zinc-900 bg-zinc-100 text-zinc-900' : 'border-zinc-200 text-zinc-600 bg-white'}`}>
            {label}
          </button>
        ))}
      </div>
      {metode === 'envio' && !order.direccion_envio && (
        <div className="grid grid-cols-2 gap-2">
          <input placeholder={t('orders.detail.recipient_name_ph', 'Nom del destinatari')} value={form.recipient_name}
            onChange={e => setForm(f => ({ ...f, recipient_name: e.target.value }))}
            className="col-span-2 border border-zinc-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          <input placeholder={t('orders.detail.address_ph', 'Adreça')} value={form.address_line1}
            onChange={e => setForm(f => ({ ...f, address_line1: e.target.value }))}
            className="col-span-2 border border-zinc-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          <input placeholder={t('orders.detail.postcode_ph', 'Codi postal')} value={form.postal_code}
            onChange={e => setForm(f => ({ ...f, postal_code: e.target.value }))}
            className="border border-zinc-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          <input placeholder={t('orders.detail.city_ph', 'Ciutat')} value={form.city}
            onChange={e => setForm(f => ({ ...f, city: e.target.value }))}
            className="border border-zinc-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
        </div>
      )}
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex gap-2">
        <Button size="sm" disabled={updating} onClick={confirm}>{t('orders.detail.confirm', 'Confirmar')}</Button>
        <button onClick={onCancel} className="text-sm px-3 py-1.5 text-zinc-500 hover:text-zinc-700">{t('common.cancel')}</button>
      </div>
    </div>
  );
}

function ShipForm({ order, onCancel, onConfirm, updating }) {
  const t = useT();
  const [numero, setNumero] = useState('');
  const [transportista, setTransportista] = useState('');

  return (
    <div className="border-t border-zinc-100 pt-4">
      <div className="text-xs text-zinc-500 mb-2 font-medium">{t('orders.modal.ship_title')}</div>
      <div className="flex gap-2 flex-wrap mb-3">
        <input value={numero} onChange={e => setNumero(e.target.value)}
          placeholder={t('orders.modal.tracking_ph')}
          className="flex-1 min-w-[160px] border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
        <input value={transportista} onChange={e => setTransportista(e.target.value)}
          placeholder={t('orders.modal.carrier_ph')}
          className="flex-1 min-w-[140px] border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
      </div>
      <div className="flex gap-2">
        <Button size="sm" disabled={updating}
          onClick={() => onConfirm({ tracking_number: numero || null, carrier: transportista || null })}>
          {t('orders.modal.confirm_ship')}
        </Button>
        <button onClick={onCancel} className="text-sm px-3 py-1.5 text-zinc-500 hover:text-zinc-700">
          {t('common.cancel')}
        </button>
      </div>
    </div>
  );
}

function InfoBlock({ label, value }) {
  return (
    <div>
      <div className="text-xs text-zinc-400 font-medium mb-0.5">{label}</div>
      <div className="text-sm text-zinc-900">{value}</div>
    </div>
  );
}
