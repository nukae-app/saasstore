'use client';

import { useEffect, useMemo, useState } from 'react';
import { authFetch } from '../../lib/auth';
import { Button } from '../../../components/ui/button';
import { useSortFilter } from '../../../components/admin/table/useSortFilter';
import { SortableTh } from '../../../components/admin/table/SortableTh';
import { Plus, X, PlayCircle } from 'lucide-react';
import { useT } from '../../lib/i18n';

function fmtDate(d) {
  if (!d) return '—';
  return new Date(d + 'T00:00:00').toLocaleDateString('ca-ES', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

function fmtEur(v) {
  return v != null ? parseFloat(v).toFixed(2) + ' €' : '—';
}

export default function ActiusPage() {
  const t = useT();
  const [actius, setActius] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [showAmortitzacio, setShowAmortitzacio] = useState(false);

  const CATEGORIES = useMemo(() => [
    { value: 'maquinaria', label: t('actius.category.maquinaria', 'Maquinària') },
    { value: 'mobiliari', label: t('actius.category.mobiliari', 'Mobiliari') },
    { value: 'equips_informatics', label: t('actius.category.equips_informatics', 'Equips informàtics') },
    { value: 'elements_transport', label: t('actius.category.elements_transport', 'Elements de transport') },
    { value: 'altres', label: t('actius.category.altres', 'Altres') },
  ], [t]);

  async function loadAll() {
    setLoading(true);
    const r = await authFetch('/admin/actius');
    setActius(await r.json());
    setLoading(false);
  }
  useEffect(() => { loadAll(); }, []);

  const columns = useMemo(() => ({
    nom: { sortValue: a => a.name.toLowerCase() },
    categoria: {
      sortValue: a => CATEGORIES.find(c => c.value === a.category)?.label || a.category,
      filterValue: a => CATEGORIES.find(c => c.value === a.category)?.label || a.category,
    },
    data_adquisicio: { sortValue: a => a.acquisition_date },
    cost: { sortValue: a => parseFloat(a.acquisition_cost) || 0 },
    valor_comptable: { sortValue: a => parseFloat(a.book_value) || 0 },
  }), [CATEGORIES]);

  const { rows: llista, sort, toggleSort, filters, setFilter, distinctValues } = useSortFilter(actius, columns);

  return (
    <div className="space-y-5 max-w-6xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-zinc-900">{t('actius.title', 'Actius fixos')}</h2>
          <p className="text-sm text-zinc-500 mt-1">{t('actius.subtitle', 'Immobilitzat material i amortitzacions.')}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setShowAmortitzacio(true)}>
            <PlayCircle size={16} /> {t('actius.generate_depreciation', 'Generar amortitzacions')}
          </Button>
          <Button onClick={() => setShowModal(true)}>
            <Plus size={16} /> {t('actius.new', 'Nou actiu')}
          </Button>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading', 'Carregant...')}</div>
        ) : llista.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('actius.empty', "Cap actiu donat d'alta encara")}</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
                <tr>
                  <SortableTh label={t('common.name', 'Nom')} sortKey="nom" sort={sort} onSort={toggleSort} />
                  <SortableTh label={t('actius.col.category', 'Categoria')} sortKey="categoria" sort={sort} onSort={toggleSort}
                    filterOptions={distinctValues.categoria} selected={filters.categoria} onFilterChange={setFilter} />
                  <SortableTh label={t('actius.col.acquisition', 'Adquisició')} sortKey="data_adquisicio" sort={sort} onSort={toggleSort} />
                  <SortableTh label={t('actius.col.cost', 'Cost')} sortKey="cost" sort={sort} onSort={toggleSort} align="right" />
                  <th className="px-4 py-3 text-right font-medium">{t('actius.col.depreciated', 'Amortitzat')}</th>
                  <SortableTh label={t('actius.col.book_value', 'Valor comptable')} sortKey="valor_comptable" sort={sort} onSort={toggleSort} align="right" />
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {llista.map(a => (
                  <tr key={a.id} className={a.disposal_date ? 'opacity-50' : ''}>
                    <td className="px-4 py-3 font-medium text-zinc-900">{a.name}</td>
                    <td className="px-4 py-3 text-zinc-500 text-xs">{CATEGORIES.find(c => c.value === a.category)?.label || a.category}</td>
                    <td className="px-4 py-3 text-zinc-600">{fmtDate(a.acquisition_date)}</td>
                    <td className="px-4 py-3 text-right text-zinc-900">{fmtEur(a.acquisition_cost)}</td>
                    <td className="px-4 py-3 text-right text-zinc-500">{fmtEur(a.accumulated_depreciation)}</td>
                    <td className="px-4 py-3 text-right font-semibold text-zinc-900">{fmtEur(a.book_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showModal && (
        <ActiuModal categories={CATEGORIES} onClose={() => setShowModal(false)} onSaved={() => { setShowModal(false); loadAll(); }} />
      )}
      {showAmortitzacio && (
        <AmortitzacioModal onDone={() => { setShowAmortitzacio(false); loadAll(); }} />
      )}
    </div>
  );
}

function ActiuModal({ categories, onClose, onSaved }) {
  const t = useT();
  const today = new Date().toISOString().slice(0, 10);
  const [name, setName] = useState('');
  const [category, setCategory] = useState('equips_informatics');
  const [acquisitionDate, setAcquisitionDate] = useState(today);
  const [cost, setCost] = useState('');
  const [vat, setVat] = useState('');
  const [supplier, setSupplier] = useState('');
  const [pct, setPct] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    const payload = {
      name,
      category,
      acquisition_date: acquisitionDate,
      acquisition_cost: parseFloat(cost),
      vat_amount: parseFloat(vat || '0'),
      supplier_name: supplier || null,
      annual_depreciation_pct: parseFloat(pct),
      notes: notes || null,
    };
    const r = await authFetch('/admin/actius', { method: 'POST', body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json()).detail || t('common.error_saving', 'Error desant'));
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">{t('actius.new', 'Nou actiu')}</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 p-1 rounded-lg hover:bg-zinc-100"><X size={20} /></button>
        </div>
        <form onSubmit={save} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('common.name', 'Nom')} *</label>
            <input value={name} onChange={e => setName(e.target.value)} required
              placeholder={t('actius.name_placeholder', 'Ordinador TPV, Furgoneta de repartiment...')}
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('actius.col.category', 'Categoria')} *</label>
              <select value={category} onChange={e => setCategory(e.target.value)} required
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white">
                {categories.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('actius.acquisition_date', "Data d'adquisició")} *</label>
              <input type="date" value={acquisitionDate} onChange={e => setAcquisitionDate(e.target.value)} required
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
          </div>
          <div className="border border-zinc-200 rounded-xl p-4 space-y-3">
            <div className="text-sm font-semibold text-zinc-700">{t('actius.cost_and_vat', 'Cost i IVA')}</div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-zinc-500 mb-1">{t('actius.cost_base', 'Cost (base, sense IVA)')} *</label>
                <input type="number" step="0.01" value={cost} onChange={e => setCost(e.target.value)} required
                  className="w-full border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900" />
              </div>
              <div>
                <label className="block text-xs text-zinc-500 mb-1">{t('actius.vat_supported', 'IVA suportat')}</label>
                <input type="number" step="0.01" value={vat} onChange={e => setVat(e.target.value)}
                  className="w-full border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900" />
              </div>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('actius.pct_label', '% amortització anual (lineal)')} *</label>
            <input type="number" step="0.01" value={pct} onChange={e => setPct(e.target.value)} required
              placeholder={t('actius.pct_placeholder', "Consulta les taules d'Hisenda o la teva gestoria — no és un valor que puguem endevinar")}
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('actius.supplier', 'Proveïdor')}</label>
            <input value={supplier} onChange={e => setSupplier(e.target.value)}
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('common.notes', 'Notes')}</label>
            <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={2}
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 resize-none" />
          </div>
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel', "Cancel·lar")}</Button>
            <Button type="submit" disabled={saving}>{saving ? t('common.saving', 'Desant...') : t('actius.create', 'Crear actiu')}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}

function AmortitzacioModal({ onDone }) {
  const t = useT();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [mes, setMes] = useState(now.getMonth() + 1);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  async function run() {
    setRunning(true);
    setError('');
    const r = await authFetch(`/admin/amortitzacions/${year}/${mes}/generar`, { method: 'POST' });
    setRunning(false);
    if (r.ok) setResult(await r.json());
    else setError((await r.json()).detail || t('actius.error_generating', 'Error generant'));
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">{t('actius.generate_depreciation', 'Generar amortitzacions')}</h3>
          <button onClick={onDone} className="text-zinc-400 hover:text-zinc-600 p-1 rounded-lg hover:bg-zinc-100"><X size={20} /></button>
        </div>
        <div className="p-6 space-y-4">
          <p className="text-sm text-zinc-500">
            {t('actius.generate_help', "Genera la quota d'amortització d'aquest mes per a tots els actius vigents. És idempotent: si ja s'havia generat aquest mes, no duplica res.")}
          </p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-zinc-500 mb-1">{t('common.year', 'Any')}</label>
              <input type="number" value={year} onChange={e => setYear(parseInt(e.target.value, 10))}
                className="w-full border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900" />
            </div>
            <div>
              <label className="block text-xs text-zinc-500 mb-1">{t('common.month', 'Mes')}</label>
              <select value={mes} onChange={e => setMes(parseInt(e.target.value, 10))}
                className="w-full border border-zinc-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900 bg-white">
                {Array.from({ length: 12 }, (_, i) => i + 1).map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
          </div>

          {result && (
            <div className="bg-zinc-50 border border-zinc-200 rounded-xl p-3 text-sm space-y-1">
              <p className="font-medium text-zinc-800">{result.entrades_generades.length} {t('actius.generated', 'amortitzacions generades')}</p>
              {result.actius_saltats.length > 0 && (
                <p className="text-zinc-500 text-xs">{t('actius.skipped', 'Saltats (ja fets o no vigents)')}: {result.actius_saltats.join(', ')}</p>
              )}
            </div>
          )}
          {error && <p className="text-red-500 text-xs">{error}</p>}

          <div className="flex justify-end gap-3">
            {/* onDone, no onClose: si ja s'ha generat alguna amortització cal
                recarregar la llista d'actius perquè reflecteixi el nou
                import amortitzat — tancar sense recarregar deixaria la
                taula desactualitzada fins al proper refresc manual. */}
            <Button type="button" variant="secondary" onClick={onDone}>{t('common.close', 'Tancar')}</Button>
            <Button type="button" onClick={run} disabled={running}>{running ? t('actius.generating', 'Generant...') : t('actius.generate', 'Generar')}</Button>
          </div>
        </div>
      </div>
    </div>
  );
}
