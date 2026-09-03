'use client';

import { useState, useEffect } from 'react';
import { authFetch } from '../../lib/auth';
import { useT } from '../../lib/i18n';
import {
  comandaStatusLabel, COMANDA_STATUS_COLOR, fmtEur, costCompra, pendentQty,
} from '../../../components/admin/compras/shared';

export default function ComprasResumPage() {
  const t = useT();
  const [proveedores, setProveedores] = useState([]);

  useEffect(() => {
    authFetch('/admin/proveedores').then(r => r.json()).then(setProveedores);
  }, []);

  return (
    <div className="space-y-5 max-w-5xl mx-auto">
      <h2 className="text-2xl font-bold text-zinc-900">{t('purchases.title')}</h2>
      <ResumTab proveedores={proveedores} />
    </div>
  );
}

// ---- ResumTab (dashboard de compres) -------------------------------------------

function ResumTab({ proveedores }) {
  const t = useT();
  const [stats, setStats] = useState(null);
  const [comandesPendents, setComandesPendents] = useState([]);
  const [comprasPendents, setComprasPendents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      const [statsRes, esborranyRes, enviadaRes, parcialRes, comprasRes] = await Promise.all([
        authFetch('/admin/compras/stats'),
        authFetch('/admin/comandas?status=esborrany'),
        authFetch('/admin/comandas?status=enviada'),
        authFetch('/admin/comandas?status=rebuda_parcial'),
        authFetch('/admin/compras?tipo=proveedor&sense_facturar=true'),
      ]);
      if (statsRes.ok) setStats(await statsRes.json());
      const comandaLists = await Promise.all(
        [esborranyRes, enviadaRes, parcialRes].map(r => (r.ok ? r.json() : []))
      );
      setComandesPendents(comandaLists.flat().sort((a, b) => new Date(a.date) - new Date(b.date)));
      if (comprasRes.ok) {
        const data = await comprasRes.json();
        setComprasPendents(data.sort((a, b) => new Date(a.date) - new Date(b.date)));
      }
      setLoading(false);
    })();
  }, []);

  if (loading) {
    return <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading')}</div>;
  }
  if (!stats) {
    return <div className="p-12 text-center text-zinc-400 text-sm">{t('purchases.resum.load_error', "No s'han pogut carregar les dades.")}</div>;
  }

  const maxProveidor = stats.top_proveidors[0]?.total ?? 0;
  const proveedorNom = Object.fromEntries((proveedores || []).map(p => [p.id, p.name]));

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatTile label={t('purchases.resum.spend_month', 'Despesa aquest mes')} value={fmtEur(stats.total_mes)} />
        <StatTile label={t('purchases.resum.spend_quarter', 'Despesa aquest trimestre')} value={fmtEur(stats.total_trimestre)} />
        <StatTile label={t('purchases.resum.spend_year', 'Despesa aquest any')} value={fmtEur(stats.total_any)} />
        <StatTile label={t('purchases.resum.orders_pending', 'Comandes pendents de rebre')} value={stats.comandes_pendents}
          accent={stats.comandes_pendents > 0} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
          <div className="px-5 py-3 border-b border-zinc-200">
            <div className="text-sm font-semibold text-zinc-700">{t('purchases.resum.orders_pending', 'Comandes pendents de rebre')}</div>
          </div>
          {comandesPendents.length === 0 ? (
            <div className="p-5 text-sm text-zinc-400">{t('purchases.resum.no_pending_orders', 'Cap comanda pendent de rebre.')}</div>
          ) : (
            <div className="divide-y divide-zinc-100 max-h-72 overflow-y-auto">
              {comandesPendents.map(c => (
                <div key={c.id} className="px-5 py-2.5 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-zinc-900 truncate">{c.proveedor_nombre}</span>
                    <span className={`shrink-0 inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${COMANDA_STATUS_COLOR[c.status]}`}>
                      {comandaStatusLabel(t, c.status)}
                    </span>
                  </div>
                  <div className="text-xs text-zinc-400 mt-0.5">
                    {new Date(c.date).toLocaleDateString()}
                    {c.order_number ? ` · ${c.order_number}` : ''} · {pendentQty(c)} {t('purchases.resum.pending_records', 'discs pendents')}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
          <div className="px-5 py-3 border-b border-zinc-200 flex items-center justify-between">
            <div className="text-sm font-semibold text-zinc-700">{t('purchases.resum.receptions_pending_invoice', 'Recepcions pendents de facturar')}</div>
            <span className="text-xs text-zinc-400">{fmtEur(stats.sense_facturar_import)}</span>
          </div>
          {comprasPendents.length === 0 ? (
            <div className="p-5 text-sm text-zinc-400">{t('purchases.resum.no_pending_receptions', 'Cap recepció pendent de facturar.')}</div>
          ) : (
            <div className="divide-y divide-zinc-100 max-h-72 overflow-y-auto">
              {comprasPendents.map(c => (
                <div key={c.id} className="px-5 py-2.5 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-zinc-900 truncate">
                      {c.proveedor_id ? (proveedorNom[c.proveedor_id] ?? '—') : (c.individual_name ?? '—')}
                    </span>
                    <span className="shrink-0 font-medium text-zinc-900">{fmtEur(costCompra(c))}</span>
                  </div>
                  <div className="text-xs text-zinc-400 mt-0.5">
                    {new Date(c.date).toLocaleDateString()}
                    {' · '}{c.delivery_note_number ? `${t('purchases.albaran', 'Albarà')} ${c.delivery_note_number}` : t('purchases.no_albaran', 'Sense núm. albarà')}
                    {' · '}{c.items?.length ?? 0} {t('purchases.copies', 'exemplars')}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-5">
          <div className="text-sm font-semibold text-zinc-700 mb-3">{t('purchases.resum.top_suppliers', 'Top proveïdors (últims 12 mesos)')}</div>
          {stats.top_proveidors.length === 0 ? (
            <div className="text-sm text-zinc-400">{t('purchases.resum.no_data', 'Encara no hi ha dades.')}</div>
          ) : (
            <div className="space-y-2.5">
              {stats.top_proveidors.map(p => {
                const pct = maxProveidor > 0 ? (parseFloat(p.total) / parseFloat(maxProveidor)) * 100 : 0;
                return (
                  <div key={p.proveedor_id}>
                    <div className="flex items-center justify-between text-xs text-zinc-600 mb-1 gap-2">
                      <span className="font-medium truncate">{p.nombre}</span>
                      <span className="text-zinc-400 shrink-0">{fmtEur(p.total)}</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-zinc-100 overflow-hidden">
                      <div className="h-full rounded-full bg-amber-500" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <DespesaMensualChart serie={stats.serie_mensual} />
    </div>
  );
}

function StatTile({ label, value, accent }) {
  return (
    <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-5">
      <div className="text-xs font-medium text-zinc-500 mb-1">{label}</div>
      <div className={`text-2xl font-bold ${accent ? 'text-amber-600' : 'text-zinc-900'}`}>{value}</div>
    </div>
  );
}

const MESOS_CURT_FALLBACK = ['Gen', 'Feb', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Oct', 'Nov', 'Des'];

function DespesaMensualChart({ serie }) {
  const t = useT();
  const [hover, setHover] = useState(null);

  const mesosCurt = MESOS_CURT_FALLBACK.map((fallback, i) => t(`purchases.chart.month.${i}`, fallback));
  const data = serie.map(s => ({
    mes: s.mes,
    label: mesosCurt[parseInt(s.mes.split('-')[1], 10) - 1],
    proveidor: parseFloat(s.proveidor),
    particular: parseFloat(s.particular),
  }));
  const max = Math.max(1, ...data.map(d => Math.max(d.proveidor, d.particular)));
  const W = 760, H = 220, padL = 46, padB = 26, padT = 10, padR = 10;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const groupW = data.length ? plotW / data.length : plotW;
  const barW = Math.min(22, groupW / 2 - 6);
  const y = v => padT + plotH - (v / max) * plotH;
  const ticks = [0, max / 2, max];

  const fmtTick = v => (v >= 1000 ? `${(v / 1000).toFixed(1)}k€` : `${Math.round(v)}€`);

  return (
    <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-5">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="text-sm font-semibold text-zinc-700">{t('purchases.resum.monthly_spend', 'Despesa mensual (últims 12 mesos)')}</div>
        <div className="flex items-center gap-4 text-xs text-zinc-500">
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-blue-600" /> {t('purchases.type.supplier')}</span>
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-amber-500" /> {t('purchases.type.individual')}</span>
        </div>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-56" onMouseLeave={() => setHover(null)}>
        {ticks.map((tickVal, i) => (
          <g key={i}>
            <line x1={padL} x2={W - padR} y1={y(tickVal)} y2={y(tickVal)} stroke="#e4e4e7" strokeWidth={1} />
            <text x={padL - 6} y={y(tickVal)} textAnchor="end" dominantBaseline="middle" fill="#a1a1aa" fontSize={10}>
              {fmtTick(tickVal)}
            </text>
          </g>
        ))}
        {data.map((d, i) => {
          const gx = padL + i * groupW;
          const bx1 = gx + groupW / 2 - barW - 1;
          const bx2 = gx + groupW / 2 + 1;
          const dimmed = hover !== null && hover !== i;
          return (
            <g key={d.mes} onMouseEnter={() => setHover(i)}>
              <rect x={gx} y={padT} width={groupW} height={plotH} fill="transparent" />
              <rect x={bx1} y={y(d.proveidor)} width={barW} height={Math.max(0, y(0) - y(d.proveidor))}
                rx={3} fill="#2563eb" opacity={dimmed ? 0.35 : 1} />
              <rect x={bx2} y={y(d.particular)} width={barW} height={Math.max(0, y(0) - y(d.particular))}
                rx={3} fill="#f59e0b" opacity={dimmed ? 0.35 : 1} />
              <text x={gx + groupW / 2} y={H - padB + 14} textAnchor="middle" fill="#a1a1aa" fontSize={10}>
                {d.label}
              </text>
            </g>
          );
        })}
      </svg>
      {hover !== null && (
        <div className="text-xs text-zinc-600 bg-zinc-50 rounded-lg px-3 py-2 inline-flex items-center gap-3">
          <span className="font-semibold text-zinc-900">{data[hover].mes}</span>
          <span>{t('purchases.type.supplier')}: {fmtEur(data[hover].proveidor)}</span>
          <span>{t('purchases.type.individual')}: {fmtEur(data[hover].particular)}</span>
        </div>
      )}
    </div>
  );
}
