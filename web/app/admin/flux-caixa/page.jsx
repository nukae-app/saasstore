'use client';

import { useState, useEffect } from 'react';
import { authFetch } from '../../lib/auth';
import { useT } from '../../lib/i18n';

function fmtEur(v) {
  if (v == null) return '—';
  return parseFloat(v).toFixed(2) + ' €';
}

const MESOS_FALLBACK = ['Gener', 'Febrer', 'Març', 'Abril', 'Maig', 'Juny', 'Juliol', 'Agost', 'Setembre', 'Octubre', 'Novembre', 'Desembre'];
function mesLabel(t, mes) {
  return t(`resultat.month.${mes - 1}`, MESOS_FALLBACK[mes - 1]);
}

const HORITZONS = [3, 6, 12];

export default function FluxCaixaPage() {
  const t = useT();
  const [mesos, setMesos] = useState(6);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    authFetch(`/admin/flux-caixa-projectat?mesos=${mesos}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); });
  }, [mesos]);

  return (
    <div className="space-y-5 max-w-4xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold text-zinc-900">{t('flux_caixa.title', 'Flux de caixa projectat')}</h2>
        <p className="text-sm text-zinc-500 mt-1">
          {t('flux_caixa.subtitle', "Projecció, no historial: combina el saldo actual de tresoreria amb la mitjana de vendes d'aquest mateix mes en anys anteriors i les despeses ja facturades pendents de pagar. Una despesa recurrent futura que encara no s'ha donat d'alta (per exemple, el lloguer del mes vinent) no hi apareix fins que es registri com a factura.")}
        </p>
      </div>

      <div className="flex gap-1 bg-zinc-100 p-1 rounded-xl w-fit">
        {HORITZONS.map(h => (
          <button key={h} onClick={() => setMesos(h)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${mesos === h ? 'bg-white shadow-sm text-zinc-900' : 'text-zinc-600 hover:text-zinc-900'}`}>
            {t('flux_caixa.months', '{n} mesos').replace('{n}', h)}
          </button>
        ))}
      </div>

      {loading || !data ? (
        <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading', 'Carregant...')}</div>
      ) : (
        <>
          <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-4 flex items-center justify-between">
            <span className="text-sm text-zinc-500">{t('flux_caixa.current_balance', 'Saldo actual (caixa + bancs)')}</span>
            <span className="text-lg font-bold text-zinc-900">{fmtEur(data.saldo_actual)}</span>
          </div>

          <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
                <tr>
                  <th className="px-4 py-3 text-left font-medium">{t('common.month', 'Mes')}</th>
                  <th className="px-4 py-3 text-right font-medium">{t('flux_caixa.estimated_income', 'Ingressos estimats')}</th>
                  <th className="px-4 py-3 text-right font-medium">{t('flux_caixa.pending_expenses', 'Despeses pendents')}</th>
                  <th className="px-4 py-3 text-right font-medium">{t('flux_caixa.projected_balance', 'Saldo projectat')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {data.linies.map(l => (
                  <tr key={`${l.year}-${l.mes}`}>
                    <td className="px-4 py-2.5 text-zinc-700">{mesLabel(t, l.mes)} {l.year}</td>
                    <td className="px-4 py-2.5 text-right text-green-700">+{fmtEur(l.ingressos_estimats)}</td>
                    <td className="px-4 py-2.5 text-right text-red-600">
                      {parseFloat(l.despeses_pendents) > 0 ? `−${fmtEur(l.despeses_pendents)}` : fmtEur(0)}
                    </td>
                    <td className={`px-4 py-2.5 text-right font-semibold ${parseFloat(l.saldo_projectat) < 0 ? 'text-red-600' : 'text-zinc-900'}`}>
                      {fmtEur(l.saldo_projectat)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
