'use client';

import { useState, useEffect } from 'react';
import { authFetch } from '../../lib/auth';
import { AlertTriangle } from 'lucide-react';

function fmtEur(v) {
  if (v == null) return '—';
  return parseFloat(v).toFixed(2) + ' €';
}

const CATEGORIA_LABELS = {
  vendes_web: 'Vendes web',
  vendes_mostrador: 'Vendes mostrador',
  vendes_discogs: 'Vendes Discogs',
  vendes_altres: 'Altres vendes',
  compres_material: 'Compres de material',
  subministraments: 'Subministraments',
  serveis_externs: 'Serveis externs',
  lloguers: 'Lloguers',
  personal: 'Personal',
  transport: 'Transport',
  marketing: 'Màrqueting',
  fiscal: 'Gestoria i fiscal',
  bancaris: 'Comissions bancàries',
  altres: 'Altres',
};

const TRIMESTRES = [
  { label: '1r Trimestre (Gen–Mar)', value: 1 },
  { label: '2n Trimestre (Abr–Jun)', value: 2 },
  { label: '3r Trimestre (Jul–Set)', value: 3 },
  { label: '4t Trimestre (Oct–Des)', value: 4 },
];

const NOW = new Date();

export default function IVAPage() {
  const [year, setYear] = useState(NOW.getFullYear());
  const [trim, setTrim] = useState(Math.max(1, Math.floor(NOW.getMonth() / 3) + 1));
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  async function loadData() {
    setLoading(true);
    try {
      const r = await authFetch(`/admin/iva/${year}/${trim}`);
      setData(await r.json());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadData(); }, [year, trim]);

  const ivaRepercutit = data?.iva_repercutit || [];
  const ivaSuportat = data?.iva_suportat || [];
  const totalRepercutit = data?.total_iva_repercutit || 0;
  const totalSuportat = data?.total_iva_suportat || 0;
  const resultat = data?.resultat_iva || 0;

  return (
    <div className="space-y-5 max-w-4xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-zinc-900">IVA</h2>
        <div className="text-xs text-zinc-400">Model 303 — previsió fiscal</div>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <select value={year} onChange={e => setYear(Number(e.target.value))}
          className="border border-zinc-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-zinc-900">
          {[2023, 2024, 2025, 2026].map(y => <option key={y}>{y}</option>)}
        </select>
        <div className="flex gap-2">
          {TRIMESTRES.map(t => (
            <button key={t.value} onClick={() => setTrim(t.value)}
              className={`px-4 py-1.5 rounded-lg text-sm border transition-colors ${trim === t.value ? 'bg-zinc-900 text-white border-zinc-900' : 'bg-white text-zinc-600 border-zinc-200 hover:border-zinc-400'}`}>
              {t.value}T
            </button>
          ))}
        </div>
        <span className="text-sm text-zinc-400">{TRIMESTRES.find(t => t.value === trim)?.label} {year}</span>
      </div>

      {loading ? (
        <div className="p-12 text-center text-zinc-400 text-sm">Carregant...</div>
      ) : !data ? null : (
        <div className="space-y-4">
          {data.nota_rebu && (
            <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-xl p-4">
              <AlertTriangle size={18} className="text-amber-500 mt-0.5 flex-shrink-0" />
              <div className="text-sm">
                <p className="font-semibold text-amber-800">Atenció: vendes REBU detectades</p>
                <p className="text-amber-700 mt-0.5">
                  Hi ha vendes de discos de 2a mà (REBU) en aquest trimestre. Sota el règim especial de béns usats,
                  l'IVA s'aplica només al marge de benefici. Consulta el teu gestor per al càlcul correcte del model 303.
                </p>
              </div>
            </div>
          )}

          {/* Resum */}
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-red-50 border border-red-200 rounded-xl p-4">
              <div className="text-xs text-red-600 mb-1">IVA repercutit (vendes)</div>
              <div className="text-xl font-bold text-red-700">+{fmtEur(totalRepercutit)}</div>
              <div className="text-xs text-red-400 mt-1">A ingressar</div>
            </div>
            <div className="bg-green-50 border border-green-200 rounded-xl p-4">
              <div className="text-xs text-green-600 mb-1">IVA suportat (compres)</div>
              <div className="text-xl font-bold text-green-700">–{fmtEur(totalSuportat)}</div>
              <div className="text-xs text-green-400 mt-1">Deduïble</div>
            </div>
            <div className={`border rounded-xl p-4 ${parseFloat(resultat) >= 0 ? 'bg-orange-50 border-orange-200' : 'bg-emerald-50 border-emerald-200'}`}>
              <div className={`text-xs mb-1 ${parseFloat(resultat) >= 0 ? 'text-orange-600' : 'text-emerald-600'}`}>Resultat IVA</div>
              <div className={`text-xl font-bold ${parseFloat(resultat) >= 0 ? 'text-orange-700' : 'text-emerald-700'}`}>
                {parseFloat(resultat) >= 0 ? 'A pagar' : 'A tornar'}
              </div>
              <div className={`text-lg font-bold ${parseFloat(resultat) >= 0 ? 'text-orange-700' : 'text-emerald-700'}`}>
                {fmtEur(Math.abs(parseFloat(resultat)))}
              </div>
            </div>
          </div>

          {/* IVA Repercutit */}
          <IVASection title="IVA repercutit — vendes" total={totalRepercutit} sign="+" colorClass="bg-red-50 border-red-100 text-red-800">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500">
                <tr>
                  <th className="px-5 py-2 text-left font-medium">Canal / Concepte</th>
                  <th className="px-5 py-2 text-right font-medium">Base imposable</th>
                  <th className="px-5 py-2 text-right font-medium">IVA %</th>
                  <th className="px-5 py-2 text-right font-medium">Quota IVA</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {ivaRepercutit.length === 0 ? (
                  <tr><td colSpan={4} className="px-5 py-4 text-zinc-400 text-center text-xs">Sense dades</td></tr>
                ) : ivaRepercutit.map((l, i) => (
                  <tr key={i} className="hover:bg-zinc-50">
                    <td className="px-5 py-2.5 text-zinc-700">{CATEGORIA_LABELS[l.categoria] || l.categoria}</td>
                    <td className="px-5 py-2.5 text-right text-zinc-600">{fmtEur(l.base)}</td>
                    <td className="px-5 py-2.5 text-right text-zinc-500">{parseFloat(l.iva_pct).toFixed(0)}%</td>
                    <td className="px-5 py-2.5 text-right font-medium text-red-600">+{fmtEur(l.iva_import)}</td>
                  </tr>
                ))}
                {ivaRepercutit.length > 0 && (
                  <tr className="bg-zinc-50 font-semibold text-xs">
                    <td className="px-5 py-2 text-zinc-500">Base total</td>
                    <td className="px-5 py-2 text-right text-zinc-700">{fmtEur(data.total_base_repercutit)}</td>
                    <td />
                    <td className="px-5 py-2 text-right text-red-700">+{fmtEur(totalRepercutit)}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </IVASection>

          {/* IVA Suportat */}
          <IVASection title="IVA suportat — despeses" total={totalSuportat} sign="–" colorClass="bg-green-50 border-green-100 text-green-800">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500">
                <tr>
                  <th className="px-5 py-2 text-left font-medium">Categoria</th>
                  <th className="px-5 py-2 text-right font-medium">Base imposable</th>
                  <th className="px-5 py-2 text-right font-medium">IVA %</th>
                  <th className="px-5 py-2 text-right font-medium">Quota IVA</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {ivaSuportat.length === 0 ? (
                  <tr><td colSpan={4} className="px-5 py-4 text-zinc-400 text-center text-xs">Sense dades</td></tr>
                ) : ivaSuportat.map((l, i) => (
                  <tr key={i} className="hover:bg-zinc-50">
                    <td className="px-5 py-2.5 text-zinc-700">{CATEGORIA_LABELS[l.categoria] || l.categoria}</td>
                    <td className="px-5 py-2.5 text-right text-zinc-600">{fmtEur(l.base)}</td>
                    <td className="px-5 py-2.5 text-right text-zinc-500">{parseFloat(l.iva_pct).toFixed(0)}%</td>
                    <td className="px-5 py-2.5 text-right font-medium text-green-600">–{fmtEur(l.iva_import)}</td>
                  </tr>
                ))}
                {ivaSuportat.length > 0 && (
                  <tr className="bg-zinc-50 font-semibold text-xs">
                    <td className="px-5 py-2 text-zinc-500">Base total</td>
                    <td className="px-5 py-2 text-right text-zinc-700">{fmtEur(data.total_base_suportat)}</td>
                    <td />
                    <td className="px-5 py-2 text-right text-green-700">–{fmtEur(totalSuportat)}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </IVASection>

          {/* Resultat final */}
          <div className={`flex items-center justify-between px-5 py-4 rounded-2xl font-bold text-lg border-2 ${parseFloat(resultat) >= 0 ? 'border-orange-400 bg-orange-50 text-orange-800' : 'border-emerald-400 bg-emerald-50 text-emerald-800'}`}>
            <div>
              <div className="text-sm font-normal opacity-70 mb-0.5">
                Model 303 — {TRIMESTRES.find(t => t.value === trim)?.label} {year}
              </div>
              <div>{parseFloat(resultat) >= 0 ? 'A ingressar a Hisenda' : 'A tornar / compensar'}</div>
            </div>
            <div className="text-3xl">{fmtEur(Math.abs(parseFloat(resultat)))}</div>
          </div>
        </div>
      )}
    </div>
  );
}

function IVASection({ title, total, sign, colorClass, children }) {
  return (
    <div className="bg-white border border-zinc-200 rounded-2xl overflow-hidden shadow-sm">
      <div className={`flex items-center justify-between px-5 py-3 border-b ${colorClass}`}>
        <span className="font-semibold">{title}</span>
        <span className="font-bold">{sign}{total != null ? fmtEur(total) : '—'}</span>
      </div>
      {children}
    </div>
  );
}
