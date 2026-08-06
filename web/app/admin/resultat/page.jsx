'use client';

import { useState, useEffect } from 'react';
import { authFetch } from '../../lib/auth';
import { ChevronDown, ChevronRight, Lock, Unlock } from 'lucide-react';
import { Button } from '../../../components/ui/button';
import CaixaDiaria from './CaixaDiaria';

function fmtEur(v) {
  if (v == null) return '—';
  return parseFloat(v).toFixed(2) + ' €';
}

const CATEGORIA_LABELS = {
  compres_material: 'Compres de material',
  subministraments: 'Subministraments (llum, aigua...)',
  serveis_externs: 'Serveis externs',
  lloguers: 'Lloguers',
  personal: 'Personal',
  transport: 'Transport i logística',
  marketing: 'Màrqueting i publicitat',
  fiscal: 'Gestoria i fiscal',
  bancaris: 'Comissions bancàries',
  altres: 'Altres despeses',
};

const MESOS = ['Gener', 'Febrer', 'Març', 'Abril', 'Maig', 'Juny', 'Juliol', 'Agost', 'Setembre', 'Octubre', 'Novembre', 'Desembre'];
const NOW = new Date();

export default function ResultatPage() {
  const [year, setYear] = useState(NOW.getFullYear());
  const [mes, setMes] = useState(NOW.getMonth() + 1);
  const [data, setData] = useState(null);
  const [periodes, setPeriodes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expandedDespeses, setExpandedDespeses] = useState(true);
  const [tab, setTab] = useState('resum');

  async function loadData() {
    setLoading(true);
    try {
      const [r1, r2] = await Promise.all([
        authFetch(`/admin/resultat/${year}/${mes}`),
        authFetch('/admin/periodes'),
      ]);
      setData(await r1.json());
      setPeriodes(await r2.json());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadData(); }, [year, mes]);

  async function togglePeriode() {
    const endpoint = data?.periode_tancat
      ? `/admin/periodes/${year}/${mes}/obrir`
      : `/admin/periodes/${year}/${mes}/tancar`;
    await authFetch(endpoint, { method: 'POST' });
    loadData();
  }

  // Mesos tancats per marcar al selector
  const mesosTancats = new Set(
    periodes.filter(p => p.year === year && p.tancat).map(p => p.mes)
  );

  return (
    <div className={`space-y-5 ${tab === 'resum' ? 'max-w-4xl mx-auto' : 'max-w-6xl mx-auto'}`}>
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-zinc-900">Resultat mensual</h2>
        {tab === 'resum' && data && (
          <Button variant={data.periode_tancat ? 'secondary' : 'default'} onClick={togglePeriode}
            className="flex items-center gap-1.5">
            {data.periode_tancat ? <><Unlock size={14} /> Obrir període</> : <><Lock size={14} /> Tancar mes</>}
          </Button>
        )}
      </div>

      {/* Pestanyes */}
      <div className="inline-flex gap-1 p-1 bg-zinc-100 rounded-lg">
        {[['resum', 'Resum mensual'], ['caixa', 'Control de caixa']].map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${tab === id ? 'bg-white text-zinc-900 shadow-sm' : 'text-zinc-500 hover:text-zinc-700'}`}>
            {label}
          </button>
        ))}
      </div>

      {/* Selector any / mes */}
      <div className="flex items-center gap-3 flex-wrap">
        <select value={year} onChange={e => setYear(Number(e.target.value))}
          className="border border-zinc-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-zinc-900">
          {[2023, 2024, 2025, 2026].map(y => <option key={y}>{y}</option>)}
        </select>
        <div className="flex flex-wrap gap-1.5">
          {MESOS.map((m, i) => {
            const n = i + 1;
            return (
              <button key={n} onClick={() => setMes(n)}
                className={`px-3 py-1 rounded-lg text-sm border transition-colors relative ${mes === n ? 'bg-zinc-900 text-white border-zinc-900' : 'bg-white text-zinc-600 border-zinc-200 hover:border-zinc-400'}`}>
                {m.slice(0, 3)}
                {mesosTancats.has(n) && (
                  <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-green-400 border border-white" title="Tancat" />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {tab === 'resum' && data?.periode_tancat && (
        <div className="inline-flex items-center gap-2 text-sm px-3 py-1.5 rounded-lg bg-green-50 text-green-700 border border-green-200">
          <Lock size={13} /> Període tancat
        </div>
      )}

      {tab === 'caixa' && <CaixaDiaria year={year} mes={mes} />}

      {tab !== 'resum' ? null : loading ? (
        <div className="p-12 text-center text-zinc-400 text-sm">Carregant...</div>
      ) : !data ? null : (
        <div className="space-y-4">
          {/* Targes resum */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-green-50 border border-green-200 rounded-xl p-4">
              <div className="text-xs text-green-600 mb-1">Ingressos</div>
              <div className="text-xl font-bold text-green-700">+{fmtEur(data.total_ingressos)}</div>
            </div>
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
              <div className="text-xs text-blue-600 mb-1">Marge brut</div>
              <div className="text-xl font-bold text-blue-700">{parseFloat(data.marge_brut) >= 0 ? '+' : ''}{fmtEur(data.marge_brut)}</div>
            </div>
            <div className="bg-red-50 border border-red-200 rounded-xl p-4">
              <div className="text-xs text-red-600 mb-1">Despeses operatives</div>
              <div className="text-xl font-bold text-red-700">−{fmtEur(data.total_despeses_operatives)}</div>
            </div>
            <div className={`border rounded-xl p-4 ${parseFloat(data.resultat) >= 0 ? 'bg-emerald-50 border-emerald-200' : 'bg-red-50 border-red-200'}`}>
              <div className={`text-xs mb-1 ${parseFloat(data.resultat) >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>Resultat net</div>
              <div className={`text-xl font-bold ${parseFloat(data.resultat) >= 0 ? 'text-emerald-700' : 'text-red-700'}`}>
                {parseFloat(data.resultat) >= 0 ? '+' : ''}{fmtEur(data.resultat)}
              </div>
            </div>
          </div>

          {/* Ingressos detall */}
          <div className="bg-white border border-zinc-200 rounded-2xl overflow-hidden shadow-sm">
            <div className="flex items-center justify-between px-5 py-3 bg-green-50 border-b border-green-100">
              <span className="font-semibold text-green-800">Ingressos</span>
              <span className="font-bold text-green-700">+{fmtEur(data.total_ingressos)}</span>
            </div>
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500">
                <tr>
                  <th className="px-5 py-2 text-left font-medium">Canal</th>
                  <th className="px-5 py-2 text-right font-medium">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {[
                  { label: 'Vendes web', val: data.vendes_web },
                  { label: 'Vendes mostrador (TPV)', val: data.vendes_mostrador },
                  { label: 'Vendes Discogs', val: data.vendes_discogs },
                ].filter(r => parseFloat(r.val) > 0).map(r => (
                  <tr key={r.label} className="hover:bg-zinc-50">
                    <td className="px-5 py-2.5 text-zinc-700">{r.label}</td>
                    <td className="px-5 py-2.5 text-right font-medium text-green-600">+{fmtEur(r.val)}</td>
                  </tr>
                ))}
                {parseFloat(data.total_ingressos) === 0 && (
                  <tr><td colSpan={2} className="px-5 py-4 text-zinc-400 text-center text-xs">Sense ingressos</td></tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Cost de vendes (COGS) */}
          <div className="bg-white border border-zinc-200 rounded-2xl overflow-hidden shadow-sm">
            <div className="flex items-center justify-between px-5 py-3 bg-orange-50 border-b border-orange-100">
              <span className="font-semibold text-orange-800">Cost de les vendes (COGS)</span>
              <span className="font-bold text-orange-700">−{fmtEur(data.total_cogs)}</span>
            </div>
            <table className="w-full text-sm">
              <tbody className="divide-y divide-zinc-100">
                {parseFloat(data.cogs_web) > 0 && (
                  <tr className="hover:bg-zinc-50">
                    <td className="px-5 py-2.5 text-zinc-700">Cost vendes web</td>
                    <td className="px-5 py-2.5 text-right font-medium text-orange-600">−{fmtEur(data.cogs_web)}</td>
                  </tr>
                )}
                {parseFloat(data.cogs_extern) > 0 && (
                  <tr className="hover:bg-zinc-50">
                    <td className="px-5 py-2.5 text-zinc-700">Cost vendes TPV / Discogs</td>
                    <td className="px-5 py-2.5 text-right font-medium text-orange-600">−{fmtEur(data.cogs_extern)}</td>
                  </tr>
                )}
                {parseFloat(data.total_cogs) === 0 && (
                  <tr><td colSpan={2} className="px-5 py-4 text-zinc-400 text-center text-xs">Sense vendes aquest mes</td></tr>
                )}
                {data.items_sense_cost > 0 && (
                  <tr>
                    <td colSpan={2} className="px-5 py-2 text-xs text-amber-600 bg-amber-50">
                      ⚠ {data.items_sense_cost} venda{data.items_sense_cost > 1 ? 's' : ''} sense cost informat — el COGS és parcial
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
            <div className="flex items-center justify-between px-5 py-3 bg-blue-50 border-t border-blue-100">
              <span className="font-semibold text-blue-800">= Marge brut</span>
              <span className={`font-bold text-lg ${parseFloat(data.marge_brut) >= 0 ? 'text-blue-700' : 'text-red-700'}`}>
                {parseFloat(data.marge_brut) >= 0 ? '+' : ''}{fmtEur(data.marge_brut)}
              </span>
            </div>
          </div>

          {/* Despeses operatives per categoria */}
          <div className="bg-white border border-zinc-200 rounded-2xl overflow-hidden shadow-sm">
            <button className="w-full flex items-center justify-between px-5 py-3 bg-red-50 border-b border-red-100"
              onClick={() => setExpandedDespeses(e => !e)}>
              <span className="font-semibold text-red-800 flex items-center gap-2">
                {expandedDespeses ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                Despeses operatives
              </span>
              <span className="font-bold text-red-700">−{fmtEur(data.total_despeses_operatives)}</span>
            </button>
            {expandedDespeses && (
              <table className="w-full text-sm">
                <thead className="bg-zinc-50 text-xs text-zinc-500">
                  <tr>
                    <th className="px-5 py-2 text-left font-medium">Categoria</th>
                    <th className="px-5 py-2 text-right font-medium">Factures</th>
                    <th className="px-5 py-2 text-right font-medium">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {data.despeses.filter(d => d.categoria !== 'compres_material').length === 0 ? (
                    <tr><td colSpan={3} className="px-5 py-4 text-zinc-400 text-center text-xs">Sense despeses operatives</td></tr>
                  ) : data.despeses.filter(d => d.categoria !== 'compres_material').map((d, i) => (
                    <tr key={i} className="hover:bg-zinc-50">
                      <td className="px-5 py-2.5 text-zinc-700">{CATEGORIA_LABELS[d.categoria] || d.categoria}</td>
                      <td className="px-5 py-2.5 text-right text-zinc-500">{d.num_factures}</td>
                      <td className="px-5 py-2.5 text-right font-medium text-red-600">−{fmtEur(d.total)}</td>
                    </tr>
                  ))}
                  {data.despeses.find(d => d.categoria === 'compres_material') && (
                    <tr className="bg-zinc-50">
                      <td colSpan={3} className="px-5 py-2 text-xs text-zinc-400 italic">
                        Compres de material no incloses aquí (reflectides al COGS per venda)
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}
          </div>

          {/* Resultat final */}
          <div className={`flex items-center justify-between px-5 py-4 rounded-2xl font-bold text-lg border-2 ${parseFloat(data.resultat) >= 0 ? 'border-emerald-400 bg-emerald-50 text-emerald-800' : 'border-red-400 bg-red-50 text-red-800'}`}>
            <span>Resultat net {MESOS[mes - 1]} {year}</span>
            <span>{parseFloat(data.resultat) >= 0 ? '+' : ''}{fmtEur(data.resultat)}</span>
          </div>
        </div>
      )}
    </div>
  );
}
