'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import { authFetch } from '../../lib/auth';
import { Button } from '../../../components/ui/button';
import { useSortFilter } from '../../../components/admin/table/useSortFilter';
import { SortableTh } from '../../../components/admin/table/SortableTh';
import { Plus, X, Upload, CheckCircle2, Link2, Eye } from 'lucide-react';

const ESTAT_CFG = {
  pendent: { label: 'Pendent', cls: 'bg-amber-100 text-amber-700' },
  conciliat: { label: 'Conciliat', cls: 'bg-green-100 text-green-700' },
  ignorat: { label: 'Ignorat', cls: 'bg-zinc-100 text-zinc-500' },
};

function fmtDate(d) {
  if (!d) return '—';
  return new Date(d + 'T00:00:00').toLocaleDateString('ca-ES', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

function fmtImport(v) {
  if (v == null) return '—';
  const n = parseFloat(v);
  return <span className={n >= 0 ? 'text-green-600 font-semibold' : 'text-red-600 font-semibold'}>{n >= 0 ? '+' : ''}{n.toFixed(2)} €</span>;
}

export default function BancPage() {
  const [comptes, setComptes] = useState([]);
  const [compteActiu, setCompteActiu] = useState(null);
  const [moviments, setMoviments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showNouCompte, setShowNouCompte] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [conciliant, setConciliant] = useState(null); // moviment seleccionat per conciliar
  const [despeses, setDespeses] = useState([]);

  async function loadComptes() {
    const r = await authFetch('/admin/comptes');
    const data = await r.json();
    setComptes(data);
    if (data.length > 0 && !compteActiu) setCompteActiu(data[0]);
  }

  async function loadMoviments(compteId) {
    if (!compteId) return;
    setLoading(true);
    const r = await authFetch(`/admin/banc/${compteId}/moviments`);
    setMoviments(await r.json());
    setLoading(false);
  }

  async function loadDespeses() {
    const r = await authFetch('/admin/despeses');
    setDespeses(await r.json());
  }

  useEffect(() => { loadComptes(); loadDespeses(); }, []);
  useEffect(() => { if (compteActiu) loadMoviments(compteActiu.id); }, [compteActiu]);

  const columns = useMemo(() => ({
    data_operacio: { sortValue: m => m.operation_date ?? '' },
    import_moviment: { sortValue: m => parseFloat(m.movement_amount) || 0 },
    saldo: { sortValue: m => m.balance != null ? parseFloat(m.balance) : null },
    estat: { sortValue: m => ESTAT_CFG[m.status]?.label || m.status || '', filterValue: m => ESTAT_CFG[m.status]?.label || m.status },
  }), []);

  const { rows: moviments_, sort, toggleSort, filters, setFilter, distinctValues } = useSortFilter(moviments, columns);

  async function conciliar(movimentId, payload) {
    const r = await authFetch(`/admin/banc/moviments/${movimentId}/conciliar`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
    if (r.ok) {
      setConciliant(null);
      loadMoviments(compteActiu.id);
      loadDespeses();
    }
  }

  // Càlcul saldo banc des dels moviments
  const saldoActual = moviments.length > 0 && moviments[0].balance != null
    ? parseFloat(moviments[0].balance)
    : null;

  const pendents = moviments.filter(m => m.status === 'pendent');
  const totalPendentIngressos = pendents.filter(m => parseFloat(m.movement_amount) > 0).reduce((s, m) => s + parseFloat(m.movement_amount), 0);
  const totalPendentDespeses = pendents.filter(m => parseFloat(m.movement_amount) < 0).reduce((s, m) => s + parseFloat(m.movement_amount), 0);

  return (
    <div className="space-y-5 max-w-6xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-zinc-900">Conciliació bancària</h2>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setShowNouCompte(true)}>
            <Plus size={15} /> Nou compte
          </Button>
          {compteActiu && (
            <Button onClick={() => setShowImport(true)}>
              <Upload size={15} /> Importar extracte
            </Button>
          )}
        </div>
      </div>

      {/* Selector de compte */}
      {comptes.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {comptes.map(c => (
            <button key={c.id} onClick={() => setCompteActiu(c)}
              className={`px-4 py-2 rounded-xl text-sm font-medium border transition-colors ${compteActiu?.id === c.id ? 'bg-zinc-900 text-white border-zinc-900' : 'bg-white text-zinc-700 border-zinc-200 hover:border-zinc-400'}`}>
              {c.name}
              {c.iban && <span className="ml-2 text-xs opacity-60">{c.iban.slice(-6)}</span>}
            </button>
          ))}
        </div>
      )}

      {comptes.length === 0 ? (
        <div className="bg-white rounded-2xl border border-zinc-200 p-12 text-center">
          <p className="text-zinc-400 text-sm mb-4">No hi ha cap compte bancari configurat</p>
          <Button onClick={() => setShowNouCompte(true)}><Plus size={15} /> Afegir compte</Button>
        </div>
      ) : (
        <>
          {/* Resum saldos pendents */}
          <div className="grid grid-cols-3 gap-3">
            {saldoActual != null && (
              <div className="bg-white border border-zinc-200 rounded-xl p-4">
                <div className="text-xs text-zinc-500 mb-1">Saldo últim extracte</div>
                <div className={`text-xl font-bold ${saldoActual >= 0 ? 'text-zinc-900' : 'text-red-600'}`}>{saldoActual.toFixed(2)} €</div>
              </div>
            )}
            <div className="bg-green-50 border border-green-200 rounded-xl p-4">
              <div className="text-xs text-green-600 mb-1">Ingressos per conciliar</div>
              <div className="text-xl font-bold text-green-700">+{totalPendentIngressos.toFixed(2)} €</div>
            </div>
            <div className="bg-red-50 border border-red-200 rounded-xl p-4">
              <div className="text-xs text-red-600 mb-1">Despeses per conciliar</div>
              <div className="text-xl font-bold text-red-700">{totalPendentDespeses.toFixed(2)} €</div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-sm text-zinc-400">{moviments_.length} moviments</span>
          </div>

          {/* Taula de moviments */}
          <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
            {loading ? (
              <div className="p-12 text-center text-zinc-400 text-sm">Carregant...</div>
            ) : moviments_.length === 0 ? (
              <div className="p-12 text-center text-zinc-400 text-sm">
                Cap moviment. Importa un extracte bancari per començar.
              </div>
            ) : (
              <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
                  <tr>
                    <SortableTh label="Data" sortKey="data_operacio" sort={sort} onSort={toggleSort} />
                    <th className="px-4 py-3 text-left font-medium">Concepte</th>
                    <SortableTh label="Import" sortKey="import_moviment" sort={sort} onSort={toggleSort} align="right" />
                    <SortableTh label="Saldo" sortKey="saldo" sort={sort} onSort={toggleSort} align="right" />
                    <SortableTh label="Estat" sortKey="estat" sort={sort} onSort={toggleSort} align="center"
                      filterOptions={distinctValues.estat} selected={filters.estat} onFilterChange={setFilter} />
                    <th className="px-4 py-3 text-left font-medium">Vinculat a</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {moviments_.map(m => (
                    <tr key={m.id} className="hover:bg-zinc-50 transition-colors">
                      <td className="px-4 py-3 text-zinc-500 whitespace-nowrap">{fmtDate(m.operation_date)}</td>
                      <td className="px-4 py-3 text-zinc-700 max-w-xs truncate" title={m.concept}>{m.concept}</td>
                      <td className="px-4 py-3 text-right">{fmtImport(m.movement_amount)}</td>
                      <td className="px-4 py-3 text-right text-zinc-400 text-xs">{m.balance != null ? parseFloat(m.balance).toFixed(2) + ' €' : '—'}</td>
                      <td className="px-4 py-3 text-center">
                        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${ESTAT_CFG[m.status]?.cls}`}>
                          {ESTAT_CFG[m.status]?.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-zinc-500">
                        {m.despesa_proveidor ? (
                          <span className="flex items-center gap-1"><Link2 size={11} className="text-green-500" /> {m.despesa_proveidor} — {m.despesa_concepte}</span>
                        ) : m.order_id ? (
                          <span className="flex items-center gap-1"><Link2 size={11} className="text-blue-500" /> Comanda web</span>
                        ) : m.venta_externa_id ? (
                          <span className="flex items-center gap-1"><Link2 size={11} className="text-zinc-500" /> Venda externa</span>
                        ) : '—'}
                      </td>
                      <td className="px-4 py-3">
                        {m.status === 'pendent' && (
                          <button onClick={() => setConciliant(m)}
                            className="text-xs font-medium text-amber-600 hover:text-amber-800 border border-amber-200 rounded-lg px-2 py-1 hover:bg-amber-50 transition-colors">
                            Conciliar
                          </button>
                        )}
                        {m.status === 'conciliat' && (
                          <button onClick={() => conciliar(m.id, { status: 'pendent', despesa_id: null, order_id: null, venta_externa_id: null })}
                            className="text-xs text-zinc-400 hover:text-zinc-600 transition-colors">
                            Desfer
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            )}
          </div>
        </>
      )}

      {showNouCompte && (
        <NouCompteModal
          onClose={() => setShowNouCompte(false)}
          onSaved={() => { setShowNouCompte(false); loadComptes(); }}
        />
      )}
      {showImport && compteActiu && (
        <ImportModal
          compte={compteActiu}
          onClose={() => setShowImport(false)}
          onSaved={() => { setShowImport(false); loadMoviments(compteActiu.id); }}
        />
      )}
      {conciliant && (
        <ConciliarModal
          moviment={conciliant}
          despeses={despeses.filter(d => d.payment_status !== 'pagat')}
          onClose={() => setConciliant(null)}
          onConciliar={(payload) => conciliar(conciliant.id, payload)}
        />
      )}
    </div>
  );
}

function NouCompteModal({ onClose, onSaved }) {
  const [nom, setNom] = useState('');
  const [iban, setIban] = useState('');
  const [entitat, setEntitat] = useState('');
  const [saldoInicial, setSaldoInicial] = useState('0');
  const [dataSaldo, setDataSaldo] = useState('');
  const [saving, setSaving] = useState(false);

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    await authFetch('/admin/comptes', {
      method: 'POST',
      body: JSON.stringify({ name: nom, iban: iban || null, bank: entitat || null, opening_balance: parseFloat(saldoInicial), opening_balance_date: dataSaldo || null }),
    });
    setSaving(false);
    onSaved();
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
          <h3 className="font-bold text-zinc-900">Nou compte bancari</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600"><X size={18} /></button>
        </div>
        <form onSubmit={save} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">Nom *</label>
            <input value={nom} onChange={e => setNom(e.target.value)} required placeholder="CaixaBank compte corrent"
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">Entitat</label>
            <input value={entitat} onChange={e => setEntitat(e.target.value)} placeholder="CaixaBank, BBVA..."
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">IBAN</label>
            <input value={iban} onChange={e => setIban(e.target.value)} placeholder="ES76 0049..."
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">Saldo inicial (€)</label>
              <input type="number" step="0.01" value={saldoInicial} onChange={e => setSaldoInicial(e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">Data saldo inicial</label>
              <input type="date" value={dataSaldo} onChange={e => setDataSaldo(e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="secondary" onClick={onClose}>Cancel·lar</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Desant...' : 'Crear compte'}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}

function ImportModal({ compte, onClose, onSaved }) {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const fileRef = useRef(null);

  async function importar(e) {
    e.preventDefault();
    if (!file) return;
    setSaving(true);
    setError('');
    const form = new FormData();
    form.append('fitxer', file);
    const r = await authFetch(`/admin/banc/${compte.id}/import`, { method: 'POST', body: form, headers: {} });
    setSaving(false);
    if (r.ok) { setResult(await r.json()); }
    else { setError((await r.json()).detail || 'Error important'); }
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
          <h3 className="font-bold text-zinc-900">Importar extracte — {compte.name}</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600"><X size={18} /></button>
        </div>
        <div className="p-6 space-y-4">
          {!result ? (
            <form onSubmit={importar} className="space-y-4">
              <div className="border-2 border-dashed border-zinc-200 rounded-xl p-6 text-center cursor-pointer hover:border-zinc-400 transition-colors"
                onClick={() => fileRef.current?.click()}>
                <Upload size={24} className="mx-auto text-zinc-400 mb-2" />
                <p className="text-sm font-medium text-zinc-700">{file ? file.name : 'Selecciona fitxer .n43 o .csv'}</p>
                <p className="text-xs text-zinc-400 mt-1">Format N43 (AEB 43) o CSV genèric</p>
                <input ref={fileRef} type="file" accept=".n43,.txt,.csv" className="hidden"
                  onChange={e => setFile(e.target.files[0])} />
              </div>
              {error && <p className="text-red-500 text-xs">{error}</p>}
              <div className="flex justify-end gap-3">
                <Button type="button" variant="secondary" onClick={onClose}>Cancel·lar</Button>
                <Button type="submit" disabled={!file || saving}>{saving ? 'Important...' : 'Importar'}</Button>
              </div>
            </form>
          ) : (
            <div className="text-center space-y-3">
              <CheckCircle2 size={40} className="mx-auto text-green-500" />
              <p className="font-semibold text-zinc-900">{result.importats} moviments nous importats</p>
              <p className="text-sm text-zinc-500">{result.total_fitxer} al fitxer · {result.duplicats_ignorats} duplicats ignorats</p>
              <Button onClick={onSaved} className="w-full">Veure moviments</Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ConciliarModal({ moviment, despeses, onClose, onConciliar }) {
  const [tipus, setTipus] = useState('despesa'); // despesa | ignorar
  const [despesaId, setDespesaId] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);

  const isIngres = parseFloat(moviment.movement_amount) > 0;
  // Per a ingressos, conciliar amb venda o ignorar; per a despeses, amb despesa o ignorar

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    if (tipus === 'ignorar') {
      await onConciliar({ status: 'ignorat', reconciliation_notes: notes || null });
    } else {
      await onConciliar({
        status: 'conciliat',
        despesa_id: despesaId || null,
        reconciliation_notes: notes || null,
      });
    }
    setSaving(false);
  }

  return (
    <div className="fixed inset-0 bg-black/60 z-[60] flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
          <h3 className="font-bold text-zinc-900">Conciliar moviment</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600"><X size={18} /></button>
        </div>
        <form onSubmit={save} className="p-6 space-y-4">
          {/* Info moviment */}
          <div className="bg-zinc-50 rounded-xl p-3 text-sm space-y-1">
            <div className="flex justify-between">
              <span className="text-zinc-500">{new Date(moviment.operation_date + 'T00:00:00').toLocaleDateString('ca-ES')}</span>
              <span className={parseFloat(moviment.movement_amount) >= 0 ? 'text-green-600 font-bold' : 'text-red-600 font-bold'}>
                {parseFloat(moviment.movement_amount) >= 0 ? '+' : ''}{parseFloat(moviment.movement_amount).toFixed(2)} €
              </span>
            </div>
            <p className="text-zinc-700 font-medium truncate">{moviment.concept}</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-2">Tipus de conciliació</label>
            <div className="flex gap-2">
              {!isIngres && (
                <button type="button" onClick={() => setTipus('despesa')}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-colors ${tipus === 'despesa' ? 'bg-zinc-900 text-white border-zinc-900' : 'bg-white text-zinc-700 border-zinc-200'}`}>
                  Vincular a despesa
                </button>
              )}
              <button type="button" onClick={() => setTipus('ignorar')}
                className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-colors ${tipus === 'ignorar' ? 'bg-zinc-900 text-white border-zinc-900' : 'bg-white text-zinc-700 border-zinc-200'}`}>
                Ignorar (transferència pròpia)
              </button>
            </div>
          </div>

          {tipus === 'despesa' && (
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">Despesa pendent</label>
              <select value={despesaId} onChange={e => setDespesaId(e.target.value)} required
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white">
                <option value="">Selecciona una despesa...</option>
                {despeses.map(d => (
                  <option key={d.id} value={d.id}>
                    {d.supplier_name} — {d.concept} — {parseFloat(d.total).toFixed(2)} €
                    {d.due_date ? ` (vcmt. ${d.due_date})` : ''}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">Notes (opcional)</label>
            <input value={notes} onChange={e => setNotes(e.target.value)} placeholder="Factura de juny, transferència nòmina..."
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>

          <div className="flex gap-3 pt-1">
            <Button type="button" variant="secondary" className="flex-1" onClick={onClose}>Cancel·lar</Button>
            <Button type="submit" className="flex-1" disabled={saving || (tipus === 'despesa' && !despesaId)}>
              {saving ? 'Conciliant...' : 'Confirmar'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
