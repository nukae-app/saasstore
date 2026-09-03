'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { authFetch } from '../lib/auth';
import { useT } from '../lib/i18n';
import { Clock, ShoppingBag, Disc3, Store, Tag, CheckCircle2, ClipboardList, PackageCheck, Receipt, Repeat } from 'lucide-react';

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

const VENDA_ESTATS_REALS = ['pagado', 'enviado', 'entregado'];

function fmtEur(n) {
  return `${parseFloat(n || 0).toLocaleString('ca-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

function startOfDay(d) { const x = new Date(d); x.setHours(0, 0, 0, 0); return x; }
function startOfWeek(d) {
  const x = startOfDay(d);
  const day = (x.getDay() + 6) % 7; // 0 = dilluns
  x.setDate(x.getDate() - day);
  return x;
}
function startOfMonth(d) { return new Date(d.getFullYear(), d.getMonth(), 1); }

function sumFrom(rows, from, dateKey, amountKey) {
  return rows
    .filter(r => new Date(r[dateKey]) >= from)
    .reduce((acc, r) => acc + parseFloat(r[amountKey] || 0), 0);
}

export default function AdminDashboard() {
  const t = useT();
  const [orders, setOrders] = useState([]);
  const [peticiones, setPeticiones] = useState([]);
  const [solicitudsObertes, setSolicitudsObertes] = useState([]);
  const [comprasStats, setComprasStats] = useState(null);
  const [ventasExternas, setVentasExternas] = useState([]);
  const [subscripcions, setSubscripcions] = useState([]);
  const [cobramentsPendentsSub, setCobramentsPendentsSub] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const inicioMes = startOfMonth(new Date()).toISOString();
      const [ordersRes, peticionesRes, solicitudsRes, statsRes, ventasRes, subsRes, subsCobramentsRes] = await Promise.all([
        authFetch('/admin/orders'),
        authFetch('/admin/peticiones'),
        authFetch('/admin/solicitudes-compra?estado=oberta'),
        authFetch('/admin/compras/stats'),
        authFetch(`/admin/ventas-externas?desde=${inicioMes}`),
        authFetch('/admin/subscripcions'),
        authFetch('/admin/subscripcions/cobraments-pendents'),
      ]);
      setOrders(ordersRes.ok ? await ordersRes.json() : []);
      setPeticiones(peticionesRes.ok ? await peticionesRes.json() : []);
      setSolicitudsObertes(solicitudsRes.ok ? (await solicitudsRes.json()).results : []);
      setComprasStats(statsRes.ok ? await statsRes.json() : null);
      setVentasExternas(ventasRes.ok ? await ventasRes.json() : []);
      setSubscripcions(subsRes.ok ? await subsRes.json() : []);
      setCobramentsPendentsSub(subsCobramentsRes.ok ? await subsCobramentsRes.json() : []);
      setLoading(false);
    })();
  }, []);

  const pending = orders.filter(o => o.status === 'pagado').length;
  const peticionsPendentPreu = peticiones.filter(p => p.status === 'pendent').length;
  const peticionsPendentComanda = peticiones.filter(p => p.status === 'acceptada').length;
  const solicitudsLineasPendents = solicitudsObertes
    .flatMap(s => s.lineas ?? [])
    .filter(l => !l.resuelta).length;
  const novesSubscripcions = subscripcions.filter(s => s.estat === 'activa' && !s.ultim_disc_rebut).length;
  const enviamentsSubPendents = cobramentsPendentsSub.length;

  const now = new Date();
  const dAvui = startOfDay(now), dSetmana = startOfWeek(now), dMes = startOfMonth(now);
  const vendesRealsOrders = orders.filter(o => VENDA_ESTATS_REALS.includes(o.status));

  function resumVendes(from) {
    const web = sumFrom(vendesRealsOrders, from, 'created_at', 'total');
    const mostrador = sumFrom(ventasExternas, from, 'date', 'sale_price');
    return { web, mostrador, total: web + mostrador };
  }
  const vendesAvui = resumVendes(dAvui);
  const vendesSetmana = resumVendes(dSetmana);
  const vendesMes = resumVendes(dMes);

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <h2 className="text-2xl font-bold text-zinc-900">{t('dashboard.title')}</h2>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Clock}       label={t('dashboard.pending_orders')} value={pending}       color="yellow" href="/admin/vendes-web" />
        <StatCard icon={ShoppingBag} label={t('dashboard.total_orders')}   value={orders.length} color="blue"   href="/admin/vendes-web" />
        <StatCard icon={Disc3}       label={t('dashboard.catalog')}         value="→"            color="amber"  href="/admin/catalogo" />
        <StatCard icon={Store}       label={t('dashboard.tpv')}             value="→"            color="green"  href="/admin/tpv" />
      </div>

      <div>
        <h3 className="text-sm font-semibold text-zinc-500 uppercase tracking-wide mb-3">{t('dashboard.section.alerts')}</h3>
        <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
          <StatCard icon={Tag} label={t('dashboard.alert.peticiones_precio')} value={peticionsPendentPreu}
            color="yellow" accent={peticionsPendentPreu > 0} href="/admin/peticions" />
          <StatCard icon={CheckCircle2} label={t('dashboard.alert.peticiones_comanda')} value={peticionsPendentComanda}
            color="blue" accent={peticionsPendentComanda > 0} href="/admin/peticions" />
          <StatCard icon={ClipboardList} label={t('dashboard.alert.solicituds_obertes')} value={solicitudsObertes.length}
            subtext={solicitudsLineasPendents > 0 ? `${solicitudsLineasPendents} discs` : null}
            color="amber" accent={solicitudsObertes.length > 0} href="/admin/compras/solicituds" />
          <StatCard icon={PackageCheck} label={t('dashboard.alert.comandes_pendents')} value={comprasStats?.comandes_pendents ?? 0}
            color="green" accent={(comprasStats?.comandes_pendents ?? 0) > 0} href="/admin/compras/comandes" />
          <StatCard icon={Receipt} label={t('dashboard.alert.recepcions_pendents')} value={comprasStats?.sense_facturar_count ?? 0}
            subtext={comprasStats?.sense_facturar_count ? fmtEur(comprasStats.sense_facturar_import) : null}
            color="yellow" accent={(comprasStats?.sense_facturar_count ?? 0) > 0} href="/admin/compras/comandes" />
          <StatCard icon={Repeat} label={t('dashboard.alert.club_disc', 'Club del disc')} value={enviamentsSubPendents}
            subtext={novesSubscripcions > 0 ? `${novesSubscripcions} noves` : null}
            color="amber" accent={enviamentsSubPendents > 0 || novesSubscripcions > 0} href="/admin/subscripcions" />
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-zinc-500 uppercase tracking-wide mb-3">{t('dashboard.section.sales_summary')}</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <SalesTile label={t('dashboard.sales.today')} resum={vendesAvui} t={t} />
          <SalesTile label={t('dashboard.sales.week')} resum={vendesSetmana} t={t} />
          <SalesTile label={t('dashboard.sales.month')} resum={vendesMes} t={t} />
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-100 flex items-center justify-between">
          <h3 className="font-semibold text-zinc-900">{t('dashboard.recent_orders')}</h3>
          <Link href="/admin/vendes-web" className="text-sm text-zinc-900 hover:text-zinc-600 font-medium">
            {t('common.see_all')}
          </Link>
        </div>

        {loading ? (
          <div className="p-10 text-center text-zinc-400 text-sm">{t('common.loading')}</div>
        ) : orders.length === 0 ? (
          <div className="p-10 text-center text-zinc-400 text-sm">{t('dashboard.no_orders')}</div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-100">
              <tr>
                <th className="px-6 py-3 text-left font-medium">{t('dashboard.col.date')}</th>
                <th className="px-6 py-3 text-left font-medium">{t('dashboard.col.email')}</th>
                <th className="px-6 py-3 text-left font-medium">{t('dashboard.col.shipping')}</th>
                <th className="px-6 py-3 text-right font-medium">Total</th>
                <th className="px-6 py-3 text-left font-medium">{t('dashboard.col.status')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {orders.slice(0, 8).map(o => (
                <tr key={o.id} className="hover:bg-zinc-50 transition-colors">
                  <td className="px-6 py-3 text-zinc-500">
                    {new Date(o.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-3 font-medium truncate max-w-[200px]">{o.email}</td>
                  <td className="px-6 py-3 text-zinc-500">
                    {o.metodo_envio === 'recogida_tienda' ? t('dashboard.shipping.pickup') : t('dashboard.shipping.delivery')}
                  </td>
                  <td className="px-6 py-3 text-right font-semibold">{o.total} €</td>
                  <td className="px-6 py-3">
                    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLOR[o.status] ?? 'bg-zinc-100 text-zinc-700'}`}>
                      {t(STATUS_KEY[o.status] ?? o.status)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, subtext, color, href, accent }) {
  const bg = { yellow: 'bg-yellow-50 text-yellow-600', blue: 'bg-blue-50 text-blue-600', amber: 'bg-amber-50 text-amber-600', green: 'bg-green-50 text-green-600' };
  return (
    <Link href={href} className="bg-white rounded-2xl border border-zinc-200 p-5 flex items-center gap-4 hover:border-zinc-300 hover:shadow-md transition-all shadow-sm">
      <div className={`p-3 rounded-xl ${bg[color]}`}>
        <Icon size={22} />
      </div>
      <div className="min-w-0">
        <div className={`text-2xl font-bold ${accent ? 'text-amber-600' : 'text-zinc-900'}`}>{value}</div>
        <div className="text-xs text-zinc-500 mt-0.5 leading-tight">{label}</div>
        {subtext && <div className="text-xs text-zinc-400 mt-0.5 truncate">{subtext}</div>}
      </div>
    </Link>
  );
}

function SalesTile({ label, resum, t }) {
  return (
    <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-5">
      <div className="text-xs font-medium text-zinc-500 mb-1">{label}</div>
      <div className="text-2xl font-bold text-zinc-900">{fmtEur(resum.total)}</div>
      <div className="text-xs text-zinc-400 mt-1">
        {t('dashboard.sales.web_label')} {fmtEur(resum.web)} · {t('dashboard.sales.tpv_label')} {fmtEur(resum.mostrador)}
      </div>
    </div>
  );
}
