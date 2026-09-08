'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  PieChart, Pie, Cell,
} from 'recharts';
import { authFetch } from '../lib/auth';
import { useT } from '../lib/i18n';
import MIcon from '../../components/ui/m-icon';

const STATUS_COLOR = {
  pendiente_pago: 'bg-yellow-100 text-yellow-700',
  pagado:         'bg-blue-100 text-blue-700',
  enviado:        'bg-purple-100 text-purple-700',
  entregado:      'bg-green-100 text-green-700',
  cancelado:      'bg-surface-container-high text-secondary-foreground',
};
const STATUS_KEY = {
  pendiente_pago: 'order.status.pending',
  pagado:         'order.status.paid',
  enviado:        'order.status.shipped',
  entregado:      'order.status.delivered',
  cancelado:      'order.status.cancelled',
};

const VENDA_ESTATS_REALS = ['pagado', 'enviado', 'entregado'];
const COLOR_WEB = '#12b3a0';
const COLOR_TPV = '#f59e0b';

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

  // Vendes per dia del mes en curs (només el rang que realment tenim carregat
  // — ventasExternas es demana des de l'1 del mes, mai abans, així que un
  // gràfic de "últims 14 dies" tindria forats abans del dia 1 si el mes és
  // jove; per això el rang és sempre "des de l'1 fins avui", mai inventat).
  const dailyData = useMemo(() => {
    const days = [];
    for (let d = new Date(dMes); d <= dAvui; d.setDate(d.getDate() + 1)) {
      days.push(new Date(d));
    }
    return days.map(d => {
      const key = d.toDateString();
      const web = vendesRealsOrders
        .filter(o => new Date(o.created_at).toDateString() === key)
        .reduce((s, o) => s + parseFloat(o.total || 0), 0);
      const tpv = ventasExternas
        .filter(v => new Date(v.date).toDateString() === key)
        .reduce((s, v) => s + parseFloat(v.sale_price || 0), 0);
      return { dia: d.getDate(), web: +web.toFixed(2), tpv: +tpv.toFixed(2) };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orders, ventasExternas]);

  const splitData = [
    { name: t('dashboard.sales.web_label'), value: vendesMes.web },
    { name: t('dashboard.sales.tpv_label'), value: vendesMes.mostrador },
  ];
  const hasSplitData = vendesMes.total > 0;

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
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="flex items-baseline justify-between">
        <h2 className="font-headline font-bold text-2xl text-on-surface">{t('dashboard.title')}</h2>
        <span className="text-xs text-secondary-foreground uppercase tracking-wide">
          {now.toLocaleDateString('ca-ES', { weekday: 'long', day: 'numeric', month: 'long' })}
        </span>
      </div>

      {/* Stat cards */}
      <StatStrip
        entries={[
          { label: t('dashboard.pending_orders'), value: pending, icon: 'schedule', href: '/admin/vendes-web' },
          { label: t('dashboard.total_orders'), value: orders.length, icon: 'shopping_bag', href: '/admin/vendes-web' },
          { label: t('dashboard.catalog'), value: '—', icon: 'album', href: '/admin/catalogo' },
          { label: t('dashboard.tpv'), value: '—', icon: 'point_of_sale', href: '/admin/tpv' },
        ]}
      />

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-card rounded-xl border border-border shadow-sm p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-headline font-bold text-base text-on-surface">{t('dashboard.chart.sales_by_day', 'Vendes del mes, per dia')}</h3>
            <div className="flex items-center gap-3 text-xs text-secondary-foreground">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: COLOR_WEB }} /> {t('dashboard.sales.web_label')}</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: COLOR_TPV }} /> {t('dashboard.sales.tpv_label')}</span>
            </div>
          </div>
          {dailyData.length === 0 ? (
            <div className="h-56 flex items-center justify-center text-secondary-foreground text-sm">{t('common.loading')}</div>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={dailyData} barGap={2}>
                <CartesianGrid vertical={false} stroke="var(--border)" />
                <XAxis dataKey="dia" tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }} axisLine={false} tickLine={false} width={40} />
                <Tooltip
                  formatter={(value) => fmtEur(value)}
                  labelFormatter={(dia) => `${t('dashboard.chart.day', 'Dia')} ${dia}`}
                  contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                />
                <Bar dataKey="web" stackId="v" fill={COLOR_WEB} radius={[0, 0, 0, 0]} />
                <Bar dataKey="tpv" stackId="v" fill={COLOR_TPV} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="bg-card rounded-xl border border-border shadow-sm p-5">
          <h3 className="font-headline font-bold text-base text-on-surface mb-4">{t('dashboard.chart.web_vs_tpv', 'Web vs. TPV — mes')}</h3>
          {hasSplitData ? (
            <>
              <ResponsiveContainer width="100%" height={160}>
                <PieChart>
                  <Pie data={splitData} dataKey="value" nameKey="name" innerRadius={45} outerRadius={70} paddingAngle={3}>
                    <Cell fill={COLOR_WEB} />
                    <Cell fill={COLOR_TPV} />
                  </Pie>
                  <Tooltip formatter={(value) => fmtEur(value)} contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-1.5 mt-2">
                {splitData.map((s, i) => (
                  <div key={s.name} className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-1.5 text-secondary-foreground">
                      <span className="w-2 h-2 rounded-full" style={{ background: i === 0 ? COLOR_WEB : COLOR_TPV }} /> {s.name}
                    </span>
                    <span className="font-semibold text-on-surface tabular-nums">{fmtEur(s.value)}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="h-56 flex items-center justify-center text-secondary-foreground text-sm text-center px-4">
              {t('dashboard.no_sales_yet', 'Encara no hi ha vendes aquest mes.')}
            </div>
          )}
        </div>
      </div>

      {/* Attention list */}
      <div>
        <SectionLabel>{t('dashboard.section.alerts')}</SectionLabel>
        <div className="bg-card rounded-xl border border-border shadow-sm divide-y divide-border overflow-hidden">
          {alertRows.map((row, i) => (
            <Link
              key={i}
              href={row.href}
              className="flex items-center gap-3 px-4 py-3 hover:bg-surface-container-high transition-colors"
            >
              <span className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${row.value > 0 ? 'bg-primary-container text-on-primary-container' : 'bg-surface-container-high text-secondary-foreground'}`}>
                <MIcon name={row.icon} size={16} />
              </span>
              <span className="text-sm text-on-surface flex-1 truncate">{row.label}</span>
              {row.subtext && <span className="hidden sm:inline text-xs text-secondary-foreground">{row.subtext}</span>}
              <span className={`text-sm font-bold tabular-nums w-6 text-right ${row.value > 0 ? 'text-on-surface' : 'text-secondary-foreground/50'}`}>
                {row.value}
              </span>
              <MIcon name="chevron_right" size={16} className="text-secondary-foreground shrink-0" />
            </Link>
          ))}
        </div>
      </div>

      <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
        <div className="px-5 py-3.5 border-b border-border flex items-center justify-between">
          <h3 className="font-headline font-bold text-base text-on-surface">{t('dashboard.recent_orders')}</h3>
          <Link href="/admin/vendes-web" className="text-xs font-semibold text-primary hover:underline">
            {t('common.see_all')}
          </Link>
        </div>

        {loading ? (
          <div className="p-10 text-center text-secondary-foreground text-sm">{t('common.loading')}</div>
        ) : orders.length === 0 ? (
          <div className="p-10 text-center text-secondary-foreground text-sm">{t('dashboard.no_orders')}</div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-[11px] text-secondary-foreground uppercase tracking-wider">
              <tr>
                <th className="px-5 py-2.5 text-left font-bold">{t('dashboard.col.date')}</th>
                <th className="px-5 py-2.5 text-left font-bold">{t('dashboard.col.email')}</th>
                <th className="px-5 py-2.5 text-left font-bold">{t('dashboard.col.shipping')}</th>
                <th className="px-5 py-2.5 text-right font-bold">Total</th>
                <th className="px-5 py-2.5 text-left font-bold">{t('dashboard.col.status')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
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
    <h3 className="text-[11px] font-bold text-secondary-foreground uppercase tracking-wider mb-2">{children}</h3>
  );
}

function StatStrip({ entries }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
      {entries.map((e, i) => {
        const inner = (
          <div className="bg-card p-4 rounded-xl border border-border shadow-sm flex items-center gap-3 h-full">
            <span className="w-10 h-10 rounded-lg bg-primary-container text-on-primary-container flex items-center justify-center shrink-0">
              <MIcon name={e.icon} size={20} />
            </span>
            <div className="min-w-0">
              <div className="text-xl font-headline font-bold text-on-surface leading-none">{e.value}</div>
              <div className="text-xs text-secondary-foreground mt-1 truncate">{e.label}</div>
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
