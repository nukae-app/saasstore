'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { authFetch } from '../lib/auth';
import { useT } from '../lib/i18n';
import MIcon from '../../components/ui/m-icon';

const STATUS_COLOR = {
  pendiente_pago: 'bg-yellow-100 text-yellow-700',
  pagado:         'bg-blue-100 text-blue-700',
  enviado:        'bg-purple-100 text-purple-700',
  entregado:      'bg-green-100 text-green-700',
  cancelado:      'bg-surface-container-high text-secondary',
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

  const alertRows = [
    { label: t('dashboard.alert.peticiones_precio'), value: peticionsPendentPreu, icon: 'sell', href: '/admin/peticions' },
    { label: t('dashboard.alert.peticiones_comanda'), value: peticionsPendentComanda, icon: 'check_circle', href: '/admin/peticions' },
    { label: t('dashboard.alert.solicituds_obertes'), value: solicitudsObertes.length,
      subtext: solicitudsLineasPendents > 0 ? `${solicitudsLineasPendents} discs` : null, icon: 'pending_actions', href: '/admin/compras/solicituds' },
    { label: t('dashboard.alert.comandes_pendents'), value: comprasStats?.comandes_pendents ?? 0, icon: 'local_shipping', href: '/admin/compras/comandes' },
    { label: t('dashboard.alert.recepcions_pendents'), value: comprasStats?.sense_facturar_count ?? 0,
      subtext: comprasStats?.sense_facturar_count ? fmtEur(comprasStats.sense_facturar_import) : null, icon: 'receipt_long', href: '/admin/compras/comandes' },
    { label: t('dashboard.alert.club_disc', 'Club del disc'), value: enviamentsSubPendents,
      subtext: novesSubscripcions > 0 ? `${novesSubscripcions} noves` : null, icon: 'loyalty', href: '/admin/subscripcions' },
  ];

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex items-baseline justify-between">
        <h2 className="font-headline font-bold text-2xl text-on-surface">{t('dashboard.title')}</h2>
        <span className="text-xs text-secondary uppercase tracking-wide">
          {now.toLocaleDateString('ca-ES', { weekday: 'long', day: 'numeric', month: 'long' })}
        </span>
      </div>

      {/* Register — same metric-strip language as the catalog screen */}
      <StatStrip
        entries={[
          { label: t('dashboard.pending_orders'), value: pending, icon: 'schedule', href: '/admin/vendes-web' },
          { label: t('dashboard.total_orders'), value: orders.length, icon: 'shopping_bag', href: '/admin/vendes-web' },
          { label: t('dashboard.catalog'), value: '—', icon: 'album', href: '/admin/catalogo' },
          { label: t('dashboard.tpv'), value: '—', icon: 'point_of_sale', href: '/admin/tpv' },
        ]}
      />

      {/* Sales summary */}
      <div>
        <SectionLabel>{t('dashboard.section.sales_summary')}</SectionLabel>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            { label: t('dashboard.sales.today'), resum: vendesAvui },
            { label: t('dashboard.sales.week'), resum: vendesSetmana },
            { label: t('dashboard.sales.month'), resum: vendesMes },
          ].map(({ label, resum }) => (
            <div key={label} className="bg-surface-container-low p-4 rounded-xl shadow-[0_4px_20px_rgba(46,50,48,0.04)]">
              <div className="text-xs font-medium text-secondary mb-1">{label}</div>
              <div className="text-2xl font-headline font-bold text-on-surface">{fmtEur(resum.total)}</div>
              <div className="text-xs text-on-surface-variant mt-1">
                {t('dashboard.sales.web_label')} {fmtEur(resum.web)} · {t('dashboard.sales.tpv_label')} {fmtEur(resum.mostrador)}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Attention list */}
      <div>
        <SectionLabel>{t('dashboard.section.alerts')}</SectionLabel>
        <div className="bg-surface-container-low rounded-xl shadow-[0_4px_20px_rgba(46,50,48,0.04)] divide-y divide-outline-variant/40 overflow-hidden">
          {alertRows.map((row, i) => (
            <Link
              key={i}
              href={row.href}
              className="flex items-center gap-3 px-4 py-3 hover:bg-surface-container-high transition-colors"
            >
              <span className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${row.value > 0 ? 'bg-primary-container text-on-primary-container' : 'bg-surface-container-high text-secondary'}`}>
                <MIcon name={row.icon} size={16} />
              </span>
              <span className="text-sm text-on-surface flex-1 truncate">{row.label}</span>
              {row.subtext && <span className="hidden sm:inline text-xs text-secondary">{row.subtext}</span>}
              <span className={`text-sm font-bold tabular-nums w-6 text-right ${row.value > 0 ? 'text-on-surface' : 'text-secondary/50'}`}>
                {row.value}
              </span>
              <MIcon name="chevron_right" size={16} className="text-secondary shrink-0" />
            </Link>
          ))}
        </div>
      </div>

      <div className="bg-surface-container-low rounded-xl shadow-[0_4px_20px_rgba(46,50,48,0.04)] overflow-hidden">
        <div className="px-5 py-3.5 border-b border-outline-variant/40 flex items-center justify-between">
          <h3 className="font-headline font-bold text-base text-on-surface">{t('dashboard.recent_orders')}</h3>
          <Link href="/admin/vendes-web" className="text-xs font-semibold text-primary hover:underline">
            {t('common.see_all')}
          </Link>
        </div>

        {loading ? (
          <div className="p-10 text-center text-secondary text-sm">{t('common.loading')}</div>
        ) : orders.length === 0 ? (
          <div className="p-10 text-center text-secondary text-sm">{t('dashboard.no_orders')}</div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-surface-container-high/60 text-[11px] text-secondary uppercase tracking-wider">
              <tr>
                <th className="px-5 py-2.5 text-left font-bold">{t('dashboard.col.date')}</th>
                <th className="px-5 py-2.5 text-left font-bold">{t('dashboard.col.email')}</th>
                <th className="px-5 py-2.5 text-left font-bold">{t('dashboard.col.shipping')}</th>
                <th className="px-5 py-2.5 text-right font-bold">Total</th>
                <th className="px-5 py-2.5 text-left font-bold">{t('dashboard.col.status')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/40">
              {orders.slice(0, 8).map(o => (
                <tr key={o.id} className="hover:bg-surface-container-high/40 transition-colors">
                  <td className="px-5 py-3 text-on-surface-variant">
                    {new Date(o.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-5 py-3 font-medium text-on-surface truncate max-w-[200px]">{o.email}</td>
                  <td className="px-5 py-3 text-on-surface-variant">
                    {o.metodo_envio === 'recogida_tienda' ? t('dashboard.shipping.pickup') : t('dashboard.shipping.delivery')}
                  </td>
                  <td className="px-5 py-3 text-right font-bold tabular-nums text-on-surface">{o.total} €</td>
                  <td className="px-5 py-3">
                    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLOR[o.status] ?? 'bg-surface-container-high text-on-surface-variant'}`}>
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

function SectionLabel({ children }) {
  return (
    <h3 className="text-[11px] font-bold text-secondary uppercase tracking-wider mb-2">{children}</h3>
  );
}

// Franja de mètriques (mateix llenguatge visual que la "stat metrics strip"
// del mockup del catàleg): targetes petites amb icona, no la franja de
// tiquet/ledger de la iteració anterior.
function StatStrip({ entries }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {entries.map((e, i) => {
        const inner = (
          <div className="bg-surface-container-low p-4 rounded-xl shadow-[0_4px_20px_rgba(46,50,48,0.04)] flex flex-col gap-2 h-full">
            <div className="flex items-center justify-between">
              <span className="w-8 h-8 rounded-lg bg-primary-container text-on-primary-container flex items-center justify-center">
                <MIcon name={e.icon} size={16} />
              </span>
            </div>
            <div>
              <div className="text-xl font-headline font-bold text-on-surface">{e.value}</div>
              <div className="text-xs text-secondary mt-0.5 truncate">{e.label}</div>
            </div>
          </div>
        );
        return e.href ? (
          <Link key={i} href={e.href} className="hover:-translate-y-0.5 transition-transform">{inner}</Link>
        ) : (
          <div key={i}>{inner}</div>
        );
      })}
    </div>
  );
}
