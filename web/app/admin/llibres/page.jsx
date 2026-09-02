'use client';

import { useEffect, useMemo, useState } from 'react';
import { authFetch } from '../../lib/auth';
import { Button } from '../../../components/ui/button';
import { Download, CheckCircle2, AlertTriangle, Plus, Trash2, X } from 'lucide-react';
import { useT } from '../../lib/i18n';

const MESOS_FALLBACK = ['Gener', 'Febrer', 'Març', 'Abril', 'Maig', 'Juny', 'Juliol', 'Agost', 'Setembre', 'Octubre', 'Novembre', 'Desembre'];
const NOW = new Date();
const ANYS = [2024, 2025, 2026, 2027];

function fmtEur(v) {
  return v != null ? parseFloat(v).toFixed(2) + ' €' : '—';
}
function fmtDate(d) {
  if (!d) return '—';
  return new Date(d + 'T00:00:00').toLocaleDateString('ca-ES', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

export default function LlibresPage() {
  const t = useT();
  const [tab, setTab] = useState('diari');
  const [year, setYear] = useState(NOW.getFullYear());
  const [mes, setMes] = useState(NOW.getMonth() + 1);

  const TABS = [
    ['diari', t('llibres.tab.diari', 'Diari')],
    ['major', t('llibres.tab.major', 'Major')],
    ['balanc', t('llibres.tab.balanc', 'Balanç de situació')],
    ['pyg', t('llibres.tab.pyg', 'Compte de resultats')],
  ];

  return (
    <div className="space-y-5 max-w-6xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold text-zinc-900">{t('llibres.title', 'Llibres comptables')}</h2>
        <p className="text-sm text-zinc-500 mt-1">
          {t('llibres.subtitle', 'Derivats de la partida doble — net d\'IVA, a diferència de "Resultat" i "IVA".')}
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
            {MESOS_FALLBACK.map((m, i) => {
              const n = i + 1;
              return (
                <button key={n} onClick={() => setMes(n)}
                  className={`px-3 py-1 rounded-lg text-sm border transition-colors ${mes === n ? 'bg-zinc-900 text-white border-zinc-900' : 'bg-white text-zinc-600 border-zinc-200 hover:border-zinc-400'}`}>
                  {t(`resultat.month.${i}`, m).slice(0, 3)}
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
  const t = useT();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [deleting, setDeleting] = useState(null);

  function loadData() {
    setLoading(true);
    authFetch(`/admin/llibre-diari/${year}/${mes}`).then(r => r.json()).then(d => { setData(d); setLoading(false); });
  }
  useEffect(loadData, [year, mes]);

  async function esborrar(id) {
    setDeleting(id);
    try {
      const r = await authFetch(`/admin/assentaments/${id}`, { method: 'DELETE' });
      if (r.ok) loadData();
    } finally {
      setDeleting(null);
    }
  }

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

  if (loading) return <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading', 'Carregant...')}</div>;

  return (
    <div className="space-y-3">
      <div className="flex justify-end gap-2">
        <Button variant="secondary" size="sm" disabled={exporting} onClick={exportarCsv} className="flex items-center gap-1.5">
          <Download size={14} /> {exporting ? t('llibres.exporting', 'Exportant...') : `${t('llibres.export_csv', 'Exportar CSV')} (${t('llibres.full_year', 'any {year} complet').replace('{year}', year)})`}
        </Button>
        <Button size="sm" onClick={() => setShowModal(true)} className="flex items-center gap-1.5">
          <Plus size={14} /> {t('llibres.new_manual_entry', 'Nou assentament manual')}
        </Button>
      </div>

      {!data?.assentaments?.length ? (
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-12 text-center text-zinc-400 text-sm">
          {t('llibres.no_entries_month', 'Cap assentament aquest mes')}
        </div>
      ) : (
        <div className="space-y-3">
          {data.assentaments.map(a => (
            <div key={a.id} className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
              <div className="flex items-center justify-between px-4 py-2.5 bg-zinc-50 border-b border-zinc-200">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs text-zinc-400">#{a.entry_number}</span>
                  <span className="text-sm font-medium text-zinc-800">{a.description}</span>
                  {a.source_type === 'manual' && (
                    <span className="text-[10px] font-medium uppercase tracking-wide text-amber-600 bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5">
                      {t('llibres.manual_badge', 'Manual')}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-zinc-500">{fmtDate(a.date)}</span>
                  {a.source_type === 'manual' && (
                    <button onClick={() => esborrar(a.id)} disabled={deleting === a.id}
                      className="text-zinc-400 hover:text-red-600 p-1 rounded hover:bg-red-50 transition-colors" title={t('llibres.delete_entry', 'Esborrar assentament')}>
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
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

      {showModal && (
        <ManualEntryModal defaultDate={`${year}-${String(mes).padStart(2, '0')}-01`}
          onClose={() => setShowModal(false)} onSaved={() => { setShowModal(false); loadData(); }} />
      )}
    </div>
  );
}

function ManualEntryModal({ defaultDate, onClose, onSaved }) {
  const t = useT();
  const [comptes, setComptes] = useState([]);
  const [date, setDate] = useState(defaultDate);
  const [description, setDescription] = useState('');
  const [linies, setLinies] = useState([{ compte_code: '', debit: '', credit: '' }, { compte_code: '', debit: '', credit: '' }]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => { authFetch('/admin/comptes-comptables').then(r => r.json()).then(setComptes); }, []);

  const totalDebit = linies.reduce((s, l) => s + (parseFloat(l.debit) || 0), 0);
  const totalCredit = linies.reduce((s, l) => s + (parseFloat(l.credit) || 0), 0);
  const quadra = totalDebit > 0 && Math.abs(totalDebit - totalCredit) < 0.005;

  function updateLinia(i, camp, valor) {
    setLinies(ls => ls.map((l, idx) => (idx === i ? { ...l, [camp]: valor } : l)));
  }
  function afegirLinia() {
    setLinies(ls => [...ls, { compte_code: '', debit: '', credit: '' }]);
  }
  function treureLinia(i) {
    setLinies(ls => ls.filter((_, idx) => idx !== i));
  }

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    const payload = {
      date, description,
      apunts: linies
        .filter(l => l.compte_code && (parseFloat(l.debit) > 0 || parseFloat(l.credit) > 0))
        .map(l => ({ compte_code: l.compte_code, debit: parseFloat(l.debit || '0'), credit: parseFloat(l.credit || '0') })),
    };
    const r = await authFetch('/admin/assentaments/manual', { method: 'POST', body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json()).detail || t('common.error_saving', 'Error desant'));
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">{t('llibres.new_manual_entry', 'Nou assentament manual')}</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 p-1 rounded-lg hover:bg-zinc-100"><X size={20} /></button>
        </div>
        <form onSubmit={save} className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('common.date', 'Data')} *</label>
              <input type="date" value={date} onChange={e => setDate(e.target.value)} required
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('llibres.concept', 'Concepte')} *</label>
              <input value={description} onChange={e => setDescription(e.target.value)} required
                placeholder={t('llibres.concept_placeholder', "Ajust d'inventari, correcció...")}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
          </div>

          <div className="border border-zinc-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">{t('llibres.account', 'Compte')}</th>
                  <th className="px-3 py-2 text-right font-medium w-28">{t('llibres.debit', 'Debe')}</th>
                  <th className="px-3 py-2 text-right font-medium w-28">{t('llibres.credit', 'Haver')}</th>
                  <th className="w-8" />
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {linies.map((l, i) => (
                  <tr key={i}>
                    <td className="px-2 py-1.5">
                      <select value={l.compte_code} onChange={e => updateLinia(i, 'compte_code', e.target.value)}
                        className="w-full border border-zinc-200 rounded px-2 py-1 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-zinc-900">
                        <option value="">—</option>
                        {comptes.map(c => <option key={c.id} value={c.code}>{c.code} — {c.name}</option>)}
                      </select>
                    </td>
                    <td className="px-2 py-1.5">
                      <input type="number" step="0.01" value={l.debit} onChange={e => updateLinia(i, 'debit', e.target.value)}
                        className="w-full border border-zinc-200 rounded px-2 py-1 text-sm text-right focus:outline-none focus:ring-1 focus:ring-zinc-900" />
                    </td>
                    <td className="px-2 py-1.5">
                      <input type="number" step="0.01" value={l.credit} onChange={e => updateLinia(i, 'credit', e.target.value)}
                        className="w-full border border-zinc-200 rounded px-2 py-1 text-sm text-right focus:outline-none focus:ring-1 focus:ring-zinc-900" />
                    </td>
                    <td className="px-1">
                      {linies.length > 2 && (
                        <button type="button" onClick={() => treureLinia(i)} className="text-zinc-300 hover:text-red-500"><X size={14} /></button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-zinc-50 border-t border-zinc-200">
                <tr>
                  <td className="px-3 py-2">
                    <button type="button" onClick={afegirLinia} className="text-xs text-zinc-500 hover:text-zinc-800 font-medium">+ {t('llibres.add_line', 'Afegir línia')}</button>
                  </td>
                  <td className="px-3 py-2 text-right font-medium text-zinc-700">{totalDebit.toFixed(2)} €</td>
                  <td className="px-3 py-2 text-right font-medium text-zinc-700">{totalCredit.toFixed(2)} €</td>
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>

          {!quadra && (
            <p className="text-xs text-amber-600">{t('llibres.must_balance', "L'assentament ha de quadrar (debe = haver) abans de desar-lo.")}</p>
          )}
          {error && <p className="text-red-500 text-xs">{error}</p>}

          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel', "Cancel·lar")}</Button>
            <Button type="submit" disabled={saving || !quadra}>{saving ? t('common.saving', 'Desant...') : t('llibres.create_entry', 'Crear assentament')}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}

function MajorTab({ year }) {
  const t = useT();
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
          <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading', 'Carregant...')}</div>
        ) : !data?.linies?.length ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('llibres.no_movements_year', 'Cap moviment aquest any per a aquest compte')}</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
                <tr>
                  <th className="px-4 py-3 text-left font-medium">{t('common.date', 'Data')}</th>
                  <th className="px-4 py-3 text-left font-medium">{t('llibres.entry', 'Assentament')}</th>
                  <th className="px-4 py-3 text-right font-medium">{t('llibres.debit', 'Debe')}</th>
                  <th className="px-4 py-3 text-right font-medium">{t('llibres.credit', 'Haver')}</th>
                  <th className="px-4 py-3 text-right font-medium">{t('llibres.running_balance', 'Saldo acumulat')}</th>
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
                  <td colSpan={4} className="px-4 py-3 text-right font-semibold text-zinc-700">{t('llibres.final_balance', 'Saldo final')}</td>
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

function BalancColumna({ titol, linies, total, emptyLabel }) {
  const t = useT();
  return (
    <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
      <div className="px-4 py-2.5 bg-zinc-50 border-b border-zinc-200 text-sm font-semibold text-zinc-700">{titol}</div>
      {linies.length === 0 ? (
        <div className="p-6 text-center text-zinc-400 text-xs">{emptyLabel || t('llibres.no_balance', 'Cap saldo')}</div>
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
              <td colSpan={2} className="px-4 py-2.5 text-right font-semibold text-zinc-700">{t('llibres.total', 'Total')}</td>
              <td className="px-4 py-2.5 text-right font-bold text-zinc-900">{fmtEur(total)}</td>
            </tr>
          </tfoot>
        </table>
      )}
    </div>
  );
}

function BalancTab({ year, mes }) {
  const t = useT();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    authFetch(`/admin/balanc-situacio/${year}/${mes}`).then(r => r.json()).then(d => { setData(d); setLoading(false); });
  }, [year, mes]);

  if (loading) return <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading', 'Carregant...')}</div>;
  if (!data) return null;

  return (
    <div className="space-y-3">
      <div className={`inline-flex items-center gap-2 text-sm px-3 py-1.5 rounded-lg border ${data.quadrat ? 'bg-green-50 text-green-700 border-green-200' : 'bg-red-50 text-red-700 border-red-200'}`}>
        {data.quadrat ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
        {data.quadrat ? t('llibres.balances', 'Quadra') : t('llibres.does_not_balance', 'No quadra')}
        {' — '}{t('llibres.assets', 'Actiu')} {fmtEur(data.total_actiu)} / {t('llibres.liabilities_equity', 'Passiu + Patrimoni net')} {fmtEur(data.total_passiu_patrimoni_net)}
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <BalancColumna titol={t('llibres.assets', 'Actiu')} linies={data.actiu} total={data.total_actiu} />
        <div className="space-y-4">
          <BalancColumna titol={t('llibres.liabilities', 'Passiu')} linies={data.passiu} total={data.passiu.reduce((s, l) => s + parseFloat(l.saldo), 0)} />
          <BalancColumna titol={t('llibres.equity', 'Patrimoni net')} linies={data.patrimoni_net} total={data.patrimoni_net.reduce((s, l) => s + parseFloat(l.saldo), 0)} />
        </div>
      </div>
    </div>
  );
}

function PygTab({ year, mes }) {
  const t = useT();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    authFetch(`/admin/compte-resultats/${year}/${mes}`).then(r => r.json()).then(d => { setData(d); setLoading(false); });
  }, [year, mes]);

  if (loading) return <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading', 'Carregant...')}</div>;
  if (!data) return null;

  const resultatPositiu = parseFloat(data.resultat) >= 0;

  return (
    <div className="space-y-3">
      <div className={`inline-flex items-center gap-2 text-sm px-3 py-1.5 rounded-lg border ${resultatPositiu ? 'bg-green-50 text-green-700 border-green-200' : 'bg-red-50 text-red-700 border-red-200'}`}>
        {t('llibres.result_of_month', 'Resultat del mes')}: <span className="font-bold">{resultatPositiu ? '+' : ''}{fmtEur(data.resultat)}</span>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <BalancColumna titol={t('resultat.income', 'Ingressos')} linies={data.ingressos.map(l => ({ compte_code: l.compte_code, compte_name: l.compte_name, saldo: l.total }))} total={data.total_ingressos} />
        <BalancColumna titol={t('llibres.expenses', 'Despeses')} linies={data.despeses.map(l => ({ compte_code: l.compte_code, compte_name: l.compte_name, saldo: l.total }))} total={data.total_despeses} />
      </div>
    </div>
  );
}
