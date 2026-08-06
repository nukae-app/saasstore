'use client';

import { useState, useEffect, useMemo } from 'react';
import { authFetch } from '../../lib/auth';
import { Download, Save, Lock, RefreshCw } from 'lucide-react';
import { Button } from '../../../components/ui/button';

const CAMPS = [
  { key: 'targeta_21', label: 'Targeta 21%', auto: true },
  { key: 'targeta_4', label: 'Targeta 4%', auto: true },
  { key: 'efectiu_21', label: 'Efectiu 21%', auto: true },
  { key: 'efectiu_4', label: 'Efectiu 4%', auto: true },
  { key: 'bizum_21', label: 'Bizum 21%', auto: true },
  { key: 'bizum_4', label: 'Bizum 4%', auto: true },
  { key: 'paypal_21', label: 'Paypal 21%' },
  { key: 'paypal_4', label: 'Paypal 4%' },
  { key: 'transfer_21', label: 'Transfer 21%' },
  { key: 'bono_cultural', label: 'Bono cultural', auto: true },
];

const CAMPS_AUTO = CAMPS.filter((c) => c.auto).map((c) => c.key);

function fmtDia(iso) {
  const [, m, d] = iso.split('-');
  return `${d}-${m}-${iso.split('-')[0]}`;
}

function num(v) {
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : 0;
}

export default function CaixaDiaria({ year, mes }) {
  const [dies, setDies] = useState([]);
  const [periodeTancat, setPeriodeTancat] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [exporting, setExporting] = useState(null);
  const [omplint, setOmplint] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    authFetch(`/admin/caixa-diaria/${year}/${mes}`)
      .then((r) => r.json())
      .then((data) => {
        if (cancelled) return;
        setDies(data.dies.map((d) => ({ ...d })));
        setPeriodeTancat(data.periode_tancat);
        setDirty(false);
      })
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [year, mes]);

  function updateCamp(idx, camp, value) {
    setDies((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], [camp]: value };
      return next;
    });
    setDirty(true);
  }

  const totals = useMemo(() => {
    const t = Object.fromEntries(CAMPS.map((c) => [c.key, 0]));
    let totalMes = 0;
    for (const dia of dies) {
      for (const c of CAMPS) t[c.key] += num(dia[c.key]);
      totalMes += CAMPS.reduce((s, c) => s + num(dia[c.key]), 0);
    }
    return { ...t, total_mes: totalMes };
  }, [dies]);

  function totalDia(dia) {
    return CAMPS.reduce((s, c) => s + num(dia[c.key]), 0);
  }

  async function guardar() {
    setSaving(true);
    try {
      const payload = dies.map((d) => ({
        data: d.data,
        ...Object.fromEntries(CAMPS.map((c) => [c.key, num(d[c.key])])),
      }));
      const r = await authFetch(`/admin/caixa-diaria/${year}/${mes}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => null);
        alert(err?.detail || 'Error desant la caixa');
        return;
      }
      const data = await r.json();
      setDies(data.dies.map((d) => ({ ...d })));
      setDirty(false);
    } finally {
      setSaving(false);
    }
  }

  async function omplirAmbVendesReals() {
    setOmplint(true);
    try {
      const r = await authFetch(`/admin/caixa-diaria/${year}/${mes}/vendes-reals`);
      if (!r.ok) return;
      const reals = await r.json();
      const perDia = Object.fromEntries(reals.map((d) => [d.data, d]));
      const buida = Object.fromEntries(CAMPS_AUTO.map((k) => [k, 0]));
      setDies((prev) => prev.map((dia) => {
        const real = perDia[dia.data];
        if (!real) return { ...dia, ...buida };
        return { ...dia, ...Object.fromEntries(CAMPS_AUTO.map((k) => [k, real[k] ?? 0])) };
      }));
      setDirty(true);
    } finally {
      setOmplint(false);
    }
  }

  async function exportar(tipus) {
    setExporting(tipus);
    try {
      const r = await authFetch(`/admin/caixa-diaria/${year}/${mes}/${tipus}`);
      if (!r.ok) return;
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `caixa_${year}_${String(mes).padStart(2, '0')}.${tipus === 'excel' ? 'xlsx' : 'pdf'}`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(null);
    }
  }

  if (loading) return <div className="p-12 text-center text-zinc-400 text-sm">Carregant...</div>;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          {periodeTancat && (
            <span className="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg bg-green-50 text-green-700 border border-green-200">
              <Lock size={13} /> Període tancat — no editable
            </span>
          )}
          {dirty && !periodeTancat && (
            <span className="text-xs text-amber-600">Canvis sense desar</span>
          )}
          {!periodeTancat && (
            <span className="text-xs text-zinc-400">
              <span className="inline-block w-2 h-2 rounded-sm bg-blue-100 border border-blue-200 align-[1px] mr-1" />
              Targeta / Efectiu / Bizum / Bono cultural es poden omplir automàticament — Paypal i Transfer, a mà
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!periodeTancat && (
            <Button variant="secondary" size="sm" disabled={omplint}
              onClick={omplirAmbVendesReals} className="flex items-center gap-1.5"
              title="Recalcula Targeta, Efectiu, Bizum i Bono cultural a partir de les vendes web (Redsys) i de mostrador (TPV). Paypal i Transfer no es registren enlloc: cal seguir omplint-los a mà.">
              <RefreshCw size={14} /> {omplint ? 'Calculant...' : 'Omplir amb vendes reals'}
            </Button>
          )}
          <Button variant="secondary" size="sm" disabled={exporting === 'excel'}
            onClick={() => exportar('excel')} className="flex items-center gap-1.5">
            <Download size={14} /> Excel
          </Button>
          <Button variant="secondary" size="sm" disabled={exporting === 'pdf'}
            onClick={() => exportar('pdf')} className="flex items-center gap-1.5">
            <Download size={14} /> PDF
          </Button>
          {!periodeTancat && (
            <Button size="sm" disabled={saving || !dirty} onClick={guardar} className="flex items-center gap-1.5">
              <Save size={14} /> {saving ? 'Desant...' : 'Desar'}
            </Button>
          )}
        </div>
      </div>

      <div className="bg-white border border-zinc-200 rounded-2xl overflow-x-auto shadow-sm">
        <table className="text-sm border-collapse">
          <thead>
            <tr className="bg-blue-700 text-white">
              <th className="px-2 py-2 text-xs font-semibold sticky left-0 bg-blue-700 whitespace-nowrap">DIA</th>
              {CAMPS.map((c) => (
                <th key={c.key} className={`px-2 py-2 text-xs font-semibold whitespace-nowrap ${c.auto ? 'bg-blue-800' : ''}`}>
                  {c.label}
                </th>
              ))}
              <th className="px-2 py-2 text-xs font-semibold whitespace-nowrap">Total dia</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {dies.map((dia, idx) => (
              <tr key={dia.data} className="hover:bg-zinc-50">
                <td className="px-2 py-1 text-xs text-zinc-600 sticky left-0 bg-white whitespace-nowrap">
                  {fmtDia(dia.data)}
                </td>
                {CAMPS.map((c) => (
                  <td key={c.key} className={`px-1 py-1 ${c.auto ? 'bg-blue-50/50' : ''}`}>
                    <input
                      type="number"
                      step="0.01"
                      disabled={periodeTancat}
                      value={num(dia[c.key]) === 0 ? '' : dia[c.key]}
                      onChange={(e) => updateCamp(idx, c.key, e.target.value)}
                      className="w-20 text-right text-xs border border-zinc-200 rounded px-1.5 py-1 focus:outline-none focus:ring-1 focus:ring-zinc-900 disabled:bg-zinc-50 disabled:text-zinc-400"
                      placeholder="0"
                    />
                  </td>
                ))}
                <td className="px-2 py-1 text-right text-xs font-medium text-zinc-700 whitespace-nowrap">
                  {totalDia(dia).toFixed(2)} €
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="bg-cyan-400 text-zinc-900 font-bold">
              <td className="px-2 py-2 text-xs sticky left-0 bg-cyan-400">TOTAL</td>
              {CAMPS.map((c) => (
                <td key={c.key} className="px-2 py-2 text-xs text-right whitespace-nowrap">
                  {totals[c.key].toFixed(2)}
                </td>
              ))}
              <td className="px-2 py-2 text-xs text-right whitespace-nowrap">{totals.total_mes.toFixed(2)} €</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
