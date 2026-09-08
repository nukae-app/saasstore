'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { authFetch } from '../lib/auth';
import { useT } from '../lib/i18n';
import { ChevronRight } from 'lucide-react';

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

  const alertRows = [
    { label: t('dashboard.alert.peticiones_precio'), value: peticionsPendentPreu, href: '/admin/peticions' },
    { label: t('dashboard.alert.peticiones_comanda'), value: peticionsPendentComanda, href: '/admin/peticions' },
    { label: t('dashboard.alert.solicituds_obertes'), value: solicitudsObertes.length,
      subtext: solicitudsLineasPendents > 0 ? `${solicitudsLineasPendents} discs` : null, href: '/admin/compras/solicituds' },
    { label: t('dashboard.alert.comandes_pendents'), value: comprasStats?.comandes_pendents ?? 0, href: '/admin/compras/comandes' },
    { label: t('dashboard.alert.recepcions_pendents'), value: comprasStats?.sense_facturar_count ?? 0,
      subtext: comprasStats?.sense_facturar_count ? fmtEur(comprasStats.sense_facturar_import) : null, href: '/admin/compras/comandes' },
    { label: t('dashboard.alert.club_disc', 'Club del disc'), value: enviamentsSubPendents,
      subtext: novesSubscripcions > 0 ? `${novesSubscripcions} noves` : null, href: '/admin/subscripcions' },
  ];

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      <div className="flex items-baseline justify-between">
        <h2 className="font-serif italic text-3xl text-zinc-900">{t('dashboard.title')}</h2>
        <span className="font-mono text-xs text-zinc-400 uppercase tracking-[0.15em]">
          {now.toLocaleDateString('ca-ES', { weekday: 'long', day: 'numeric', month: 'long' })}
        </span>
      </div>

      {/* Register — key counts as a ledger strip, dashed dividers instead of separate cards */}
      <LedgerStrip
        entries={[
          { label: t('dashboard.pending_orders'), value: pending, href: '/admin/vendes-web' },
          { label: t('dashboard.total_orders'), value: orders.length, href: '/admin/vendes-web' },
          { label: t('dashboard.catalog'), value: '—', href: '/admin/catalogo' },
          { label: t('dashboard.tpv'), value: '—', href: '/admin/tpv' },
        ]}
      />

      {/* Sales summary — same ledger language, monetary figures */}
      <div>
        <SectionLabel>{t('dashboard.section.sales_summary')}</SectionLabel>
        <LedgerStrip
          entries={[
            { label: t('dashboard.sales.today'), value: fmtEur(vendesAvui.total),
              subtext: `${t('dashboard.sales.web_label')} ${fmtEur(vendesAvui.web)} · ${t('dashboard.sales.tpv_label')} ${fmtEur(vendesAvui.mostrador)}` },
            { label: t('dashboard.sales.week'), value: fmtEur(vendesSetmana.total),
              subtext: `${t('dashboard.sales.web_label')} ${fmtEur(vendesSetmana.web)} · ${t('dashboard.sales.tpv_label')} ${fmtEur(vendesSetmana.mostrador)}` },
            { label: t('dashboard.sales.month'), value: fmtEur(vendesMes.total),
              subtext: `${t('dashboard.sales.web_label')} ${fmtEur(vendesMes.web)} · ${t('dashboard.sales.tpv_label')} ${fmtEur(vendesMes.mostrador)}` },
          ]}
        />
      </div>

      {/* Attention list — ledger rows instead of a grid of colored icon cards */}
      <div>
        <SectionLabel>{t('dashboard.section.alerts')}</SectionLabel>
        <div className="bg-white rounded-3xl shadow-[0_2px_24px_-6px_rgba(15,23,42,0.08)] divide-y divide-dashed divide-zinc-200 overflow-hidden">
          {alertRows.map((row, i) => (
            <Link
              key={i}
              href={row.href}
              className="flex items-center justify-between gap-4 px-6 py-3.5 hover:bg-zinc-50 transition-colors"
            >
              <span className="text-sm text-zinc-600 truncate">{row.label}</span>
              <div className="flex items-center gap-3 shrink-0">
                {row.subtext && <span className="hidden sm:inline text-xs text-zinc-400">{row.subtext}</span>}
                <span className={`font-mono text-sm font-semibold tabular-nums w-6 text-right ${row.value > 0 ? 'text-zinc-900' : 'text-zinc-300'}`}>
                  {row.value}
                </span>
                <ChevronRight size={14} className="text-zinc-300" />
              </div>
            </Link>
          ))}
        </div>
      </div>

      <div className="bg-white rounded-3xl shadow-[0_2px_24px_-6px_rgba(15,23,42,0.08)] overflow-hidden">
        <div className="px-6 py-4 border-b border-dashed border-zinc-200 flex items-center justify-between">
          <h3 className="font-serif italic text-lg text-zinc-900">{t('dashboard.recent_orders')}</h3>
          <Link href="/admin/vendes-web" className="text-xs font-mono uppercase tracking-wide text-zinc-500 hover:text-zinc-900">
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
            <thead className="text-[10px] text-zinc-400 uppercase tracking-wide font-mono border-b border-dashed border-zinc-200">
              <tr>
                <th className="px-6 py-3 text-left font-medium">{t('dashboard.col.date')}</th>
                <th className="px-6 py-3 text-left font-medium">{t('dashboard.col.email')}</th>
                <th className="px-6 py-3 text-left font-medium">{t('dashboard.col.shipping')}</th>
                <th className="px-6 py-3 text-right font-medium">Total</th>
                <th className="px-6 py-3 text-left font-medium">{t('dashboard.col.status')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dashed divide-zinc-200">
              {orders.slice(0, 8).map(o => (
                <tr key={o.id} className="hover:bg-zinc-50 transition-colors">
                  <td className="px-6 py-3 text-zinc-500">
                    {new Date(o.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-3 font-medium truncate max-w-[200px]">{o.email}</td>
                  <td className="px-6 py-3 text-zinc-500">
                    {o.metodo_envio === 'recogida_tienda' ? t('dashboard.shipping.pickup') : t('dashboard.shipping.delivery')}
                  </td>
                  <td className="px-6 py-3 text-right font-mono font-semibold tabular-nums">{o.total} €</td>
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

function SectionLabel({ children }) {
  return (
    <h3 className="font-mono text-[11px] text-zinc-400 uppercase tracking-[0.2em] mb-3">{children}</h3>
  );
}

// Franja tipus "tiquet": columnes separades per ratlla discontínua en lloc
// de targetes independents amb icona — reutilitza el llenguatge visual del
// receipt-ticket (globals.css) en comptes del patró genèric icona+número.
function LedgerStrip({ entries }) {
  const Item = ({ label, value, subtext, href }) => {
    const inner = (
      <div className="px-5 py-4 sm:px-6 sm:py-5 min-w-0">
        <div className="font-mono text-2xl sm:text-3xl font-semibold text-zinc-900 tabular-nums truncate">{value}</div>
        <div className="text-xs text-zinc-500 mt-1 truncate">{label}</div>
        {subtext && <div className="text-[11px] text-zinc-400 mt-0.5 truncate">{subtext}</div>}
      </div>
    );
    return href ? (
      <Link href={href} className="block hover:bg-zinc-50 transition-colors">{inner}</Link>
    ) : (
      <div>{inner}</div>
    );
  };

  const smCols = entries.length === 3 ? 'sm:grid-cols-3' : 'sm:grid-cols-4';

  return (
    <div className={`bg-white rounded-3xl shadow-[0_2px_24px_-6px_rgba(15,23,42,0.08)] grid grid-cols-2 ${smCols} divide-x divide-dashed divide-zinc-200 overflow-hidden`}>
      {entries.map((e, i) => (
        <div key={i} className={i >= 2 ? 'border-t sm:border-t-0 border-dashed border-zinc-200' : ''}>
          <Item {...e} />
        </div>
      ))}
    </div>
  );
}
