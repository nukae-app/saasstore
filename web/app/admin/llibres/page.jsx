'use client';

import { useEffect, useMemo, useState } from 'react';
import { authFetch } from '../../lib/auth';
import { Button } from '../../../components/ui/button';
import { Download, CheckCircle2, AlertTriangle } from 'lucide-react';

const MESOS = ['Gener', 'Febrer', 'Març', 'Abril', 'Maig', 'Juny', 'Juliol', 'Agost', 'Setembre', 'Octubre', 'Novembre', 'Desembre'];
const NOW = new Date();
const ANYS = [2024, 2025, 2026, 2027];

function fmtEur(v) {
  return v != null ? parseFloat(v).toFixed(2) + ' €' : '—';
}
function fmtDate(d) {
  if (!d) return '—';
  return new Date(d + 'T00:00:00').toLocaleDateString('ca-ES', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

const TABS = [
  ['diari', 'Diari'],
  ['major', 'Major'],
  ['balanc', 'Balanç de situació'],
  ['pyg', 'Compte de resultats'],
];

export default function LlibresPage() {
  const [tab, setTab] = useState('diari');
  const [year, setYear] = useState(NOW.getFullYear());
  const [mes, setMes] = useState(NOW.getMonth() + 1);

  return (
    <div className="space-y-5 max-w-6xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold text-zinc-900">Llibres comptables</h2>
        <p className="text-sm text-zinc-500 mt-1">
          Derivats de la partida doble — net d&apos;IVA, a diferència de &quot;Resultat&quot; i &quot;IVA&quot;.
        </p>
      </div>

      <div className="inline-flex gap-1 p-1 bg-zinc-100 rounded-lg">
        {TABS.map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${tab === id ? 'bg-white text-zinc-900 shadow-sm' : 'text-zinc-500 hover:text-zinc-700'}`}>
            {label}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <select value={year} onChange={e => setYear(Number(e.target.value))}
          className="border border-zinc-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-zinc-900">
          {ANYS.map(y => <option key={y}>{y}</option>)}
        </select>
        {tab !== 'major' && (
          <div className="flex flex-wrap gap-1.5">
            {MESOS.map((m, i) => {
              const n = i + 1;
              return (
                <button key={n} onClick={() => setMes(n)}
                  className={`px-3 py-1 rounded-lg text-sm border transition-colors ${mes === n ? 'bg-zinc-900 text-white border-zinc-900' : 'bg-white text-zinc-600 border-zinc-200 hover:border-zinc-400'}`}>
                  {m.slice(0, 3)}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {tab === 'diari' && <DiariTab year={year} mes={mes} />}
      {tab === 'major' && <MajorTab year={year} />}
      {tab === 'balanc' && <BalancTab year={year} mes={mes} />}
      {tab === 'pyg' && <PygTab year={year} mes={mes} />}
    </div>
  );
}

function DiariTab({ year, mes }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    setLoading(true);
    authFetch(`/admin/llibre-diari/${year}/${mes}`).then(r => r.json()).then(d => { setData(d); setLoading(false); });
  }, [year, mes]);

  async function exportarCsv() {
    setExporting(true);
    try {
      const r = await authFetch(`/admin/llibre-diari/${year}/export?mes_desde=1&mes_fins=12`);
      if (!r.ok) return;
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `llibre_diari_${year}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  }

  if (loading) return <div className="p-12 text-center text-zinc-400 text-sm">Carregant...</div>;

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button variant="secondary" size="sm" disabled={exporting} onClick={exportarCsv} className="flex items-center gap-1.5">
          <Download size={14} /> {exporting ? 'Exportant...' : `Exportar CSV (any ${year} complet)`}
        </Button>
      </div>

      {!data?.assentaments?.length ? (
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-12 text-center text-zinc-400 text-sm">
          Cap assentament aquest mes
        </div>
      ) : (
        <div className="space-y-3">
          {data.assentaments.map(a => (
            <div key={a.id} className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
              <div className="flex items-center justify-between px-4 py-2.5 bg-zinc-50 border-b border-zinc-200">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs text-zinc-400">#{a.entry_number}</span>
                  <span className="text-sm font-medium text-zinc-800">{a.description}</span>
                </div>
                <span className="text-xs text-zinc-500">{fmtDate(a.date)}</span>
              </div>
              <table className="w-full text-sm">
                <tbody className="divide-y divide-zinc-100">
                  {a.apunts.map(l => (
                    <tr key={l.id}>
                      <td className="px-4 py-2 font-mono text-zinc-500 w-20">{l.compte_code}</td>
                      <td className="px-4 py-2 text-zinc-700">{l.compte_name}</td>
                      <td className="px-4 py-2 text-right text-zinc-900 w-28">{parseFloat(l.debit) > 0 ? fmtEur(l.debit) : ''}</td>
                      <td className="px-4 py-2 text-right text-zinc-900 w-28">{parseFloat(l.credit) > 0 ? fmtEur(l.credit) : ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MajorTab({ year }) {
  const [comptes, setComptes] = useState([]);
  const [compte, setCompte] = useState('');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    authFetch('/admin/comptes-comptables').then(r => r.json()).then(cs => {
      setComptes(cs);
      if (cs.length && !compte) setCompte(cs[0].code);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!compte) return;
    setLoading(true);
    authFetch(`/admin/llibre-major/${year}?compte=${encodeURIComponent(compte)}`)
      .then(r => (r.ok ? r.json() : null))
      .then(d => { setData(d); setLoading(false); });
  }, [year, compte]);

  return (
    <div className="space-y-3">
      <select value={compte} onChange={e => setCompte(e.target.value)}
        className="border border-zinc-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-zinc-900">
        {comptes.map(c => <option key={c.id} value={c.code}>{c.code} — {c.name}</option>)}
      </select>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">Carregant...</div>
        ) : !data?.linies?.length ? (
          <div className="p-12 text-center text-zinc-400 text-sm">Cap moviment aquest any per a aquest compte</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
                <tr>
                  <th className="px-4 py-3 text-left font-medium">Data</th>
                  <th className="px-4 py-3 text-left font-medium">Assentament</th>
                  <th className="px-4 py-3 text-right font-medium">Debe</th>
                  <th className="px-4 py-3 text-right font-medium">Haver</th>
                  <th className="px-4 py-3 text-right font-medium">Saldo acumulat</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {data.linies.map((l, i) => (
                  <tr key={i}>
                    <td className="px-4 py-2.5 text-zinc-600">{fmtDate(l.date)}</td>
                    <td className="px-4 py-2.5 text-zinc-700">#{l.entry_number} — {l.description}</td>
                    <td className="px-4 py-2.5 text-right text-zinc-900">{parseFloat(l.debit) > 0 ? fmtEur(l.debit) : ''}</td>
                    <td className="px-4 py-2.5 text-right text-zinc-900">{parseFloat(l.credit) > 0 ? fmtEur(l.credit) : ''}</td>
                    <td className="px-4 py-2.5 text-right font-semibold text-zinc-900">{fmtEur(l.saldo_acumulat)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-zinc-50 border-t border-zinc-200">
                <tr>
                  <td colSpan={4} className="px-4 py-3 text-right font-semibold text-zinc-700">Saldo final</td>
                  <td className="px-4 py-3 text-right font-bold text-zinc-900">{fmtEur(data.saldo_final)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function BalancColumna({ titol, linies, total }) {
  return (
    <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
      <div className="px-4 py-2.5 bg-zinc-50 border-b border-zinc-200 text-sm font-semibold text-zinc-700">{titol}</div>
      {linies.length === 0 ? (
        <div className="p-6 text-center text-zinc-400 text-xs">Cap saldo</div>
      ) : (
        <table className="w-full text-sm">
          <tbody className="divide-y divide-zinc-100">
            {linies.map(l => (
              <tr key={l.compte_code}>
                <td className="px-4 py-2 font-mono text-xs text-zinc-400 w-16">{l.compte_code}</td>
                <td className="px-4 py-2 text-zinc-700">{l.compte_name}</td>
                <td className="px-4 py-2 text-right text-zinc-900">{fmtEur(l.saldo)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot className="bg-zinc-50 border-t border-zinc-200">
            <tr>
              <td colSpan={2} className="px-4 py-2.5 text-right font-semibold text-zinc-700">Total</td>
              <td className="px-4 py-2.5 text-right font-bold text-zinc-900">{fmtEur(total)}</td>
            </tr>
          </tfoot>
        </table>
      )}
    </div>
  );
}

function BalancTab({ year, mes }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    authFetch(`/admin/balanc-situacio/${year}/${mes}`).then(r => r.json()).then(d => { setData(d); setLoading(false); });
  }, [year, mes]);

  if (loading) return <div className="p-12 text-center text-zinc-400 text-sm">Carregant...</div>;
  if (!data) return null;

  return (
    <div className="space-y-3">
      <div className={`inline-flex items-center gap-2 text-sm px-3 py-1.5 rounded-lg border ${data.quadrat ? 'bg-green-50 text-green-700 border-green-200' : 'bg-red-50 text-red-700 border-red-200'}`}>
        {data.quadrat ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
        {data.quadrat ? 'Quadra' : 'No quadra'} — Actiu {fmtEur(data.total_actiu)} / Passiu + Patrimoni net {fmtEur(data.total_passiu_patrimoni_net)}
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <BalancColumna titol="Actiu" linies={data.actiu} total={data.total_actiu} />
        <div className="space-y-4">
          <BalancColumna titol="Passiu" linies={data.passiu} total={data.passiu.reduce((s, l) => s + parseFloat(l.saldo), 0)} />
          <BalancColumna titol="Patrimoni net" linies={data.patrimoni_net} total={data.patrimoni_net.reduce((s, l) => s + parseFloat(l.saldo), 0)} />
        </div>
      </div>
    </div>
  );
}

function PygTab({ year, mes }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    authFetch(`/admin/compte-resultats/${year}/${mes}`).then(r => r.json()).then(d => { setData(d); setLoading(false); });
  }, [year, mes]);

  if (loading) return <div className="p-12 text-center text-zinc-400 text-sm">Carregant...</div>;
  if (!data) return null;

  const resultatPositiu = parseFloat(data.resultat) >= 0;

  return (
    <div className="space-y-3">
      <div className={`inline-flex items-center gap-2 text-sm px-3 py-1.5 rounded-lg border ${resultatPositiu ? 'bg-green-50 text-green-700 border-green-200' : 'bg-red-50 text-red-700 border-red-200'}`}>
        Resultat del mes: <span className="font-bold">{resultatPositiu ? '+' : ''}{fmtEur(data.resultat)}</span>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <BalancColumna titol="Ingressos" linies={data.ingressos.map(l => ({ compte_code: l.compte_code, compte_name: l.compte_name, saldo: l.total }))} total={data.total_ingressos} />
        <BalancColumna titol="Despeses" linies={data.despeses.map(l => ({ compte_code: l.compte_code, compte_name: l.compte_name, saldo: l.total }))} total={data.total_despeses} />
      </div>
    </div>
  );
}
