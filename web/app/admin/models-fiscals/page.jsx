'use client';

import { useState, useEffect, useMemo } from 'react';
import { authFetch } from '../../lib/auth';
import { AlertTriangle } from 'lucide-react';
import { useT } from '../../lib/i18n';

function fmtEur(v) {
  if (v == null) return '—';
  return parseFloat(v).toFixed(2) + ' €';
}

const NOW = new Date();

function Casella({ num, label, value, sign }) {
  return (
    <div className="bg-zinc-50 border border-zinc-200 rounded-lg p-3">
      <div className="text-[10px] font-mono text-zinc-400 mb-0.5">Casella {num}</div>
      <div className="text-xs text-zinc-500 mb-1">{label}</div>
      <div className="text-base font-semibold text-zinc-900">{sign}{fmtEur(value)}</div>
    </div>
  );
}

function ForaAbast({ items, t }) {
  if (!items?.length) return null;
  return (
    <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs">
      <AlertTriangle size={14} className="text-amber-500 mt-0.5 flex-shrink-0" />
      <div className="text-amber-800">
        <span className="font-semibold">{t('models_fiscals.fora_abast', 'Fora d’abast d’aquest informe')}:</span> {items.join(' · ')}
      </div>
    </div>
  );
}

export default function ModelsFiscalsPage() {
  const t = useT();

  const TRIMESTRES = useMemo(() => [
    { label: t('iva.quarter.q1', '1r Trimestre (Gen–Mar)'), value: 1 },
    { label: t('iva.quarter.q2', '2n Trimestre (Abr–Jun)'), value: 2 },
    { label: t('iva.quarter.q3', '3r Trimestre (Jul–Set)'), value: 3 },
    { label: t('iva.quarter.q4', '4t Trimestre (Oct–Des)'), value: 4 },
  ], [t]);

  const PERIODES_202 = useMemo(() => [
    { label: t('models_fiscals.202.abril', 'Abril'), value: 1 },
    { label: t('models_fiscals.202.octubre', 'Octubre'), value: 2 },
    { label: t('models_fiscals.202.desembre', 'Desembre'), value: 3 },
  ], [t]);

  const MODELS = [
    { key: '303', label: 'Model 303', sub: t('models_fiscals.303.sub', 'IVA trimestral') },
    { key: '390', label: 'Model 390', sub: t('models_fiscals.390.sub', 'Resum anual IVA') },
    { key: '130', label: 'Model 130', sub: t('models_fiscals.130.sub', 'Pagament fraccionat IRPF · Autònoms') },
    { key: '200', label: 'Model 200', sub: t('models_fiscals.200.sub', 'Impost de Societats · SL') },
    { key: '202', label: 'Model 202', sub: t('models_fiscals.202.sub', 'Pagament fraccionat IS · SL') },
    { key: '111', label: 'Model 111', sub: t('models_fiscals.111.sub', 'Retencions professionals') },
    { key: '115', label: 'Model 115', sub: t('models_fiscals.115.sub', 'Retenció lloguer') },
    { key: '190', label: 'Model 190', sub: t('models_fiscals.190.sub', 'Resum anual retencions professionals') },
    { key: '180', label: 'Model 180', sub: t('models_fiscals.180.sub', 'Resum anual retenció lloguer') },
  ];

  const ANUALS = ['390', '190', '180'];

  const [model, setModel] = useState('303');
  const [year, setYear] = useState(NOW.getFullYear());
  const [trim, setTrim] = useState(Math.max(1, Math.floor(NOW.getMonth() / 3) + 1));
  const [reduccio5pct, setReduccio5pct] = useState(false);
  const [tipusPct, setTipusPct] = useState('');
  const [pagamentsFraccionats, setPagamentsFraccionats] = useState('0');
  const [periode202, setPeriode202] = useState(1);
  const [cuotaAnterior202, setCuotaAnterior202] = useState('');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (model === '200' && !tipusPct) { setData(null); return; }
    if (model === '202' && !cuotaAnterior202) { setData(null); return; }

    setLoading(true);
    let url;
    if (ANUALS.includes(model)) url = `/admin/aeat/${model}/${year}`;
    else if (model === '200') url = `/admin/aeat/200/${year}?tipus_pct=${tipusPct}&pagaments_fraccionats_satisfets=${pagamentsFraccionats || '0'}`;
    else if (model === '202') url = `/admin/aeat/202/${year}/${periode202}?cuota_integra_exercici_anterior=${cuotaAnterior202}`;
    else url = `/admin/aeat/${model}/${year}/${trim}`;
    if (model === '130') url += `?aplicar_reduccio_5pct=${reduccio5pct}`;

    authFetch(url).then(r => (r.ok ? r.json() : null)).then(d => { setData(d); setLoading(false); });
  }, [model, year, trim, reduccio5pct, tipusPct, pagamentsFraccionats, periode202, cuotaAnterior202]);

  return (
    <div className="space-y-5 max-w-4xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold text-zinc-900">{t('nav.models_fiscals', 'Models AEAT')}</h2>
        <p className="text-sm text-zinc-500 mt-1">
          {t('models_fiscals.subtitle', 'Caselles per copiar a la seu electrònica o passar a la gestoria — cap d’aquests informes es presenta telemàticament des d’aquí.')}
        </p>
      </div>

      <div className="flex gap-1 bg-zinc-100 p-1 rounded-xl w-fit">
        {MODELS.map(m => (
          <button key={m.key} onClick={() => setModel(m.key)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${model === m.key ? 'bg-white shadow-sm text-zinc-900' : 'text-zinc-600 hover:text-zinc-900'}`}>
            {m.label}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <select value={year} onChange={e => setYear(Number(e.target.value))}
          className="border border-zinc-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-zinc-900">
          {[2023, 2024, 2025, 2026].map(y => <option key={y}>{y}</option>)}
        </select>
        {!['390', '190', '180', '200', '202'].includes(model) && (
          <div className="flex gap-2">
            {TRIMESTRES.map(tr => (
              <button key={tr.value} onClick={() => setTrim(tr.value)}
                className={`px-4 py-1.5 rounded-lg text-sm border transition-colors ${trim === tr.value ? 'bg-zinc-900 text-white border-zinc-900' : 'bg-white text-zinc-600 border-zinc-200 hover:border-zinc-400'}`}>
                {tr.value}T
              </button>
            ))}
          </div>
        )}
        {model === '202' && (
          <div className="flex gap-2">
            {PERIODES_202.map(p => (
              <button key={p.value} onClick={() => setPeriode202(p.value)}
                className={`px-4 py-1.5 rounded-lg text-sm border transition-colors ${periode202 === p.value ? 'bg-zinc-900 text-white border-zinc-900' : 'bg-white text-zinc-600 border-zinc-200 hover:border-zinc-400'}`}>
                {p.label}
              </button>
            ))}
          </div>
        )}
        {model === '130' && (
          <label className="flex items-center gap-1.5 text-sm text-zinc-600 cursor-pointer select-none">
            <input type="checkbox" checked={reduccio5pct} onChange={e => setReduccio5pct(e.target.checked)}
              className="rounded border-zinc-300 text-zinc-900 focus:ring-zinc-900" />
            {t('models_fiscals.130.reduccio_toggle', 'Aplicar reducció 5% (estimació directa simplificada)')}
          </label>
        )}
        <span className="text-sm text-zinc-400">{MODELS.find(m => m.key === model)?.sub}</span>
      </div>

      {model === '200' && (
        <div className="flex items-end gap-4 flex-wrap bg-zinc-50 border border-zinc-200 rounded-xl p-4">
          <div>
            <label className="block text-xs text-zinc-500 mb-1">{t('models_fiscals.200.tipus_pct', 'Tipus impositiu *')}</label>
            <select value={tipusPct} onChange={e => setTipusPct(e.target.value)}
              className="border border-zinc-300 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-zinc-900">
              <option value="">{t('models_fiscals.200.tipus_pct_choose', "— Tria'n un —")}</option>
              <option value="25.00">{t('models_fiscals.200.tipus_general', 'General 25%')}</option>
              <option value="15.00">{t('models_fiscals.200.tipus_nova_creacio', 'Reduït 15% (entitat de nova creació)')}</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-zinc-500 mb-1">{t('models_fiscals.200.pagaments_fraccionats', 'Pagaments fraccionats (202) ja satisfets')}</label>
            <input type="number" step="0.01" value={pagamentsFraccionats} onChange={e => setPagamentsFraccionats(e.target.value)}
              className="border border-zinc-300 rounded-lg px-3 py-1.5 text-sm w-40 focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
        </div>
      )}

      {model === '202' && (
        <div className="flex items-end gap-4 flex-wrap bg-zinc-50 border border-zinc-200 rounded-xl p-4">
          <div>
            <label className="block text-xs text-zinc-500 mb-1">{t('models_fiscals.202.cuota_anterior', "Quota íntegra de l'exercici anterior *")}</label>
            <input type="number" step="0.01" value={cuotaAnterior202} onChange={e => setCuotaAnterior202(e.target.value)}
              placeholder="0.00"
              className="border border-zinc-300 rounded-lg px-3 py-1.5 text-sm w-48 focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
        </div>
      )}

      {loading ? (
        <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading', 'Carregant...')}</div>
      ) : !data ? (
        <div className="p-12 text-center text-zinc-400 text-sm">
          {model === '200' && !tipusPct ? t('models_fiscals.200.tria_tipus', 'Tria un tipus impositiu per calcular.')
            : model === '202' && !cuotaAnterior202 ? t('models_fiscals.202.introdueix_cuota', "Introdueix la quota de l'exercici anterior per calcular.")
            : t('iva.no_data', 'Sense dades')}
        </div>
      ) : model === '303' ? (
        <Model303View data={data} t={t} />
      ) : model === '390' ? (
        <Model390View data={data} t={t} />
      ) : model === '130' ? (
        <Model130View data={data} t={t} />
      ) : model === '200' ? (
        <Model200View data={data} t={t} />
      ) : model === '202' ? (
        <Model202View data={data} t={t} />
      ) : model === '190' || model === '180' ? (
        <ModelRetencioAnualView data={data} t={t} />
      ) : (
        <ModelRetencioView data={data} t={t} />
      )}
    </div>
  );
}

function Model303View({ data, t }) {
  return (
    <div className="space-y-4">
      {data.nota_rebu && (
        <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-xl p-4">
          <AlertTriangle size={18} className="text-amber-500 mt-0.5 flex-shrink-0" />
          <p className="text-sm text-amber-800">
            {t('iva.rebu_warning_body', "Hi ha vendes de discos de 2a mà (REBU) en aquest trimestre. Sota el règim especial de béns usats, l'IVA s'aplica només al marge de benefici. Consulta el teu gestor per al càlcul correcte del model 303.")}
          </p>
        </div>
      )}

      <div>
        <div className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-2">{t('models_fiscals.303.repercutit', 'IVA repercutit')}</div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {data.repercutit_general && <Casella num="01-03" label={`General (${data.repercutit_general.pct}%)`} value={data.repercutit_general.cuota} sign="+" />}
          {data.repercutit_reduit && <Casella num="04-06" label={`Reduït (${data.repercutit_reduit.pct}%)`} value={data.repercutit_reduit.cuota} sign="+" />}
          {data.repercutit_superreduit && <Casella num="07-09" label={`Superreduït (${data.repercutit_superreduit.pct}%)`} value={data.repercutit_superreduit.cuota} sign="+" />}
          <Casella num="27" label={t('models_fiscals.303.casella_27', 'Quota meritada total')} value={data.casella_27_cuota_meritada} sign="+" />
        </div>
      </div>

      <div>
        <div className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-2">{t('models_fiscals.303.suportat', 'IVA suportat')}</div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <Casella num="28" label={t('models_fiscals.303.casella_28', 'Base corrent')} value={data.casella_28_base_corrent} sign="" />
          <Casella num="29" label={t('models_fiscals.303.casella_29', 'Quota corrent')} value={data.casella_29_cuota_corrent} sign="–" />
          <Casella num="30" label={t('models_fiscals.303.casella_30', "Base béns d'inversió")} value={data.casella_30_base_inversio} sign="" />
          <Casella num="31" label={t('models_fiscals.303.casella_31', "Quota béns d'inversió")} value={data.casella_31_cuota_inversio} sign="–" />
          <Casella num="45" label={t('models_fiscals.303.casella_45', 'Total a deduir')} value={data.casella_45_total_a_deduir} sign="–" />
        </div>
      </div>

      <div className={`rounded-xl p-4 border ${parseFloat(data.casella_64_resultat_liquidacio) >= 0 ? 'bg-orange-50 border-orange-200' : 'bg-emerald-50 border-emerald-200'}`}>
        <div className="text-xs text-zinc-500 mb-1">{t('models_fiscals.303.casella_64', 'Casella 64 · Resultat de la liquidació')}</div>
        <div className="text-xl font-bold text-zinc-900">{fmtEur(data.casella_64_resultat_liquidacio)}</div>
      </div>

      <ForaAbast items={data.fora_abast} t={t} />
    </div>
  );
}

function Model390View({ data, t }) {
  return (
    <div className="space-y-4">
      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-zinc-50 text-xs text-zinc-500">
            <tr>
              <th className="px-5 py-2 text-left font-medium">{t('models_fiscals.390.trimestre', 'Trimestre')}</th>
              <th className="px-5 py-2 text-right font-medium">{t('models_fiscals.303.casella_27', 'Quota meritada')}</th>
              <th className="px-5 py-2 text-right font-medium">{t('models_fiscals.303.casella_45', 'Total a deduir')}</th>
              <th className="px-5 py-2 text-right font-medium">{t('iva.result', 'Resultat')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {data.trimestres.map(tr => (
              <tr key={tr.trimestre} className="hover:bg-zinc-50">
                <td className="px-5 py-2.5 font-medium text-zinc-700">{tr.trimestre}T</td>
                <td className="px-5 py-2.5 text-right text-zinc-600">+{fmtEur(tr.casella_27_cuota_meritada)}</td>
                <td className="px-5 py-2.5 text-right text-zinc-600">–{fmtEur(tr.casella_45_total_a_deduir)}</td>
                <td className="px-5 py-2.5 text-right font-semibold text-zinc-900">{fmtEur(tr.resultat)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="bg-zinc-50 font-semibold text-sm border-t border-zinc-200">
              <td className="px-5 py-3 text-zinc-700">{t('models_fiscals.390.total_anual', 'Total anual')}</td>
              <td className="px-5 py-3 text-right text-zinc-700">+{fmtEur(data.casella_27_cuota_meritada_anual)}</td>
              <td className="px-5 py-3 text-right text-zinc-700">–{fmtEur(data.casella_45_total_a_deduir_anual)}</td>
              <td className="px-5 py-3 text-right text-zinc-900">{fmtEur(data.resultat_anual)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      {data.nota_rebu && (
        <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-xl p-4">
          <AlertTriangle size={18} className="text-amber-500 mt-0.5 flex-shrink-0" />
          <p className="text-sm text-amber-800">
            {t('models_fiscals.390.rebu_warning', "Algun trimestre de l'any inclou vendes REBU (règim de béns usats). Consulta el teu gestor per al càlcul correcte.")}
          </p>
        </div>
      )}
      <ForaAbast items={data.fora_abast} t={t} />
    </div>
  );
}

function Model130View({ data, t }) {
  return (
    <div className="space-y-4">
      {data.forma_juridica_nota && (
        <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-xl p-4">
          <AlertTriangle size={18} className="text-amber-500 mt-0.5 flex-shrink-0" />
          <p className="text-sm text-amber-800">{data.forma_juridica_nota}</p>
        </div>
      )}

      <div>
        <div className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-2">
          {t('models_fiscals.130.acumulat', "Acumulat des de l'1 de gener")}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <Casella num="01" label={t('models_fiscals.130.casella_01', 'Ingressos computables')} value={data.casella_01_ingressos_acumulats} sign="+" />
          <Casella num="02" label={t('models_fiscals.130.casella_02', 'Despeses deduïbles')} value={data.casella_02_despeses_acumulades} sign="–" />
          <Casella num="03" label={t('models_fiscals.130.casella_03', 'Rendiment net')} value={data.casella_03_rendiment_net} sign="" />
        </div>
      </div>

      {data.reduccio_5pct_aplicada && (
        <div className="grid grid-cols-2 gap-3">
          <Casella num="—" label={t('models_fiscals.130.reduccio', 'Reducció 5% (topada 2.000€/any)')} value={data.reduccio_5pct_import} sign="–" />
          <Casella num="—" label={t('models_fiscals.130.rendiment_reduit', 'Rendiment net reduït')} value={data.rendiment_net_reduit} sign="" />
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <div className="bg-zinc-50 border border-zinc-200 rounded-lg p-3">
          <div className="text-[10px] font-mono text-zinc-400 mb-0.5">Casella 04</div>
          <div className="text-xs text-zinc-500 mb-1">{t('models_fiscals.130.casella_04', 'Percentatge')}</div>
          <div className="text-base font-semibold text-zinc-900">{parseFloat(data.casella_04_pct).toFixed(0)}%</div>
        </div>
        <Casella num="05" label={t('models_fiscals.130.casella_05', 'Import (03 × 20%)')} value={data.casella_05_import} sign="+" />
        <Casella num="07" label={t('models_fiscals.130.casella_07', 'Pagaments fraccionats anteriors')} value={data.casella_07_pagaments_anteriors} sign="–" />
      </div>

      <div className={`rounded-xl p-4 border ${parseFloat(data.resultat) > 0 ? 'bg-orange-50 border-orange-200' : 'bg-zinc-50 border-zinc-200'}`}>
        <div className="text-xs text-zinc-500 mb-1">{t('models_fiscals.130.resultat', 'Resultat · A ingressar aquest trimestre')}</div>
        <div className="text-xl font-bold text-zinc-900">{fmtEur(data.resultat)}</div>
      </div>

      <ForaAbast items={data.fora_abast} t={t} />
    </div>
  );
}

function Model200View({ data, t }) {
  return (
    <div className="space-y-4">
      {data.forma_juridica_nota && (
        <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-xl p-4">
          <AlertTriangle size={18} className="text-amber-500 mt-0.5 flex-shrink-0" />
          <p className="text-sm text-amber-800">{data.forma_juridica_nota}</p>
        </div>
      )}

      <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-xl p-3 text-xs text-red-800">
        <AlertTriangle size={14} className="text-red-500 mt-0.5 flex-shrink-0" />
        {t('models_fiscals.200.disclaimer', 'Estimació de suport, no un càlcul fiscal complet: assumeix zero ajustos extracomptables. No presentar sense revisar-ho amb la gestoria.')}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <Casella num="—" label={t('models_fiscals.200.resultat_comptable', 'Resultat comptable')} value={data.resultat_comptable} sign="" />
        <Casella num="—" label={t('models_fiscals.200.ajustos', 'Ajustos extracomptables')} value={data.ajustos_extracomptables} sign="" />
        <Casella num="—" label={t('models_fiscals.200.base_imposable', 'Base imposable')} value={data.base_imposable} sign="" />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <div className="bg-zinc-50 border border-zinc-200 rounded-lg p-3">
          <div className="text-xs text-zinc-500 mb-1">{t('models_fiscals.200.tipus_pct', 'Tipus impositiu')}</div>
          <div className="text-base font-semibold text-zinc-900">{parseFloat(data.tipus_pct).toFixed(0)}%</div>
        </div>
        <Casella num="—" label={t('models_fiscals.200.quota_integra', 'Quota íntegra')} value={data.quota_integra} sign="" />
        <Casella num="—" label={t('models_fiscals.200.pagaments_fraccionats', 'Pagaments fraccionats satisfets')} value={data.pagaments_fraccionats_satisfets} sign="–" />
      </div>

      <div className={`rounded-xl p-4 border ${parseFloat(data.resultat) >= 0 ? 'bg-orange-50 border-orange-200' : 'bg-emerald-50 border-emerald-200'}`}>
        <div className="text-xs text-zinc-500 mb-1">
          {parseFloat(data.resultat) >= 0 ? t('models_fiscals.200.resultat_a_ingressar', 'Resultat · A ingressar') : t('models_fiscals.200.resultat_a_retornar', 'Resultat · A retornar')}
        </div>
        <div className="text-xl font-bold text-zinc-900">{fmtEur(Math.abs(parseFloat(data.resultat)))}</div>
      </div>

      <ForaAbast items={data.fora_abast} t={t} />
    </div>
  );
}

function Model202View({ data, t }) {
  return (
    <div className="space-y-4">
      {data.forma_juridica_nota && (
        <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-xl p-4">
          <AlertTriangle size={18} className="text-amber-500 mt-0.5 flex-shrink-0" />
          <p className="text-sm text-amber-800">{data.forma_juridica_nota}</p>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <Casella num="—" label={t('models_fiscals.202.cuota_anterior', "Quota íntegra exercici anterior")} value={data.cuota_integra_exercici_anterior} sign="" />
        <div className="bg-zinc-50 border border-zinc-200 rounded-lg p-3">
          <div className="text-xs text-zinc-500 mb-1">{t('models_fiscals.202.pct', 'Percentatge')}</div>
          <div className="text-base font-semibold text-zinc-900">{parseFloat(data.pct).toFixed(0)}%</div>
        </div>
      </div>

      <div className="rounded-xl p-4 border bg-orange-50 border-orange-200">
        <div className="text-xs text-zinc-500 mb-1">{t('models_fiscals.202.import', 'Import a ingressar')} · {data.periode_nom}</div>
        <div className="text-xl font-bold text-zinc-900">{fmtEur(data.import_pagament)}</div>
      </div>

      <ForaAbast items={data.fora_abast} t={t} />
    </div>
  );
}

function ModelRetencioAnualView({ data, t }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-zinc-50 border border-zinc-200 rounded-xl p-4">
          <div className="text-xs text-zinc-500 mb-1">{t('models_fiscals.retencio.perceptors', 'Nº perceptors')}</div>
          <div className="text-xl font-bold text-zinc-900">{data.num_perceptors}</div>
        </div>
        <div className="bg-zinc-50 border border-zinc-200 rounded-xl p-4">
          <div className="text-xs text-zinc-500 mb-1">{t('models_fiscals.retencio.base', 'Base total')}</div>
          <div className="text-xl font-bold text-zinc-900">{fmtEur(data.base_total)}</div>
        </div>
        <div className="bg-orange-50 border border-orange-200 rounded-xl p-4">
          <div className="text-xs text-orange-600 mb-1">{t('models_fiscals.retencio.total', 'Retenció a ingressar')}</div>
          <div className="text-xl font-bold text-orange-700">{fmtEur(data.retencio_total)}</div>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-zinc-50 text-xs text-zinc-500">
            <tr>
              <th className="px-5 py-2 text-left font-medium">{t('models_fiscals.390.trimestre', 'Trimestre')}</th>
              <th className="px-5 py-2 text-right font-medium">{t('despeses.taxable_base', 'Base imposable')}</th>
              <th className="px-5 py-2 text-right font-medium">{t('models_fiscals.retencio.import', 'Retenció')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {data.trimestres.map(tr => (
              <tr key={tr.trimestre} className="hover:bg-zinc-50">
                <td className="px-5 py-2.5 font-medium text-zinc-700">{tr.trimestre}T</td>
                <td className="px-5 py-2.5 text-right text-zinc-600">{fmtEur(tr.base_total)}</td>
                <td className="px-5 py-2.5 text-right font-medium text-orange-700">{fmtEur(tr.retencio_total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-zinc-400">
        {t('models_fiscals.190_180.nota_trimestres', 'Els totals per trimestre poden sumar més que el total anual si un mateix proveïdor apareix en diversos trimestres — el nombre de perceptors de dalt és el recompte correcte, sobre tot l’any.')}
      </p>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-zinc-50 text-xs text-zinc-500">
            <tr>
              <th className="px-5 py-2 text-left font-medium">{t('nav.proveidors', 'Proveïdor')}</th>
              <th className="px-5 py-2 text-left font-medium">NIF</th>
              <th className="px-5 py-2 text-right font-medium">{t('despeses.taxable_base', 'Base imposable')}</th>
              <th className="px-5 py-2 text-right font-medium">{t('models_fiscals.retencio.import', 'Retenció')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {data.desglossat.length === 0 ? (
              <tr><td colSpan={4} className="px-5 py-4 text-zinc-400 text-center text-xs">{t('iva.no_data', 'Sense dades')}</td></tr>
            ) : data.desglossat.map((d, i) => (
              <tr key={i} className="hover:bg-zinc-50">
                <td className="px-5 py-2.5 text-zinc-700">{d.nom}</td>
                <td className="px-5 py-2.5 text-zinc-500 font-mono text-xs">{d.nif || '—'}</td>
                <td className="px-5 py-2.5 text-right text-zinc-600">{fmtEur(d.base)}</td>
                <td className="px-5 py-2.5 text-right font-medium text-orange-700">{fmtEur(d.retencio)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ForaAbast items={data.fora_abast} t={t} />
    </div>
  );
}

function ModelRetencioView({ data, t }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-zinc-50 border border-zinc-200 rounded-xl p-4">
          <div className="text-xs text-zinc-500 mb-1">{t('models_fiscals.retencio.perceptors', 'Nº perceptors')}</div>
          <div className="text-xl font-bold text-zinc-900">{data.num_perceptors}</div>
        </div>
        <div className="bg-zinc-50 border border-zinc-200 rounded-xl p-4">
          <div className="text-xs text-zinc-500 mb-1">{t('models_fiscals.retencio.base', 'Base total')}</div>
          <div className="text-xl font-bold text-zinc-900">{fmtEur(data.base_total)}</div>
        </div>
        <div className="bg-orange-50 border border-orange-200 rounded-xl p-4">
          <div className="text-xs text-orange-600 mb-1">{t('models_fiscals.retencio.total', 'Retenció a ingressar')}</div>
          <div className="text-xl font-bold text-orange-700">{fmtEur(data.retencio_total)}</div>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-zinc-50 text-xs text-zinc-500">
            <tr>
              <th className="px-5 py-2 text-left font-medium">{t('nav.proveidors', 'Proveïdor')}</th>
              <th className="px-5 py-2 text-left font-medium">NIF</th>
              <th className="px-5 py-2 text-right font-medium">{t('despeses.taxable_base', 'Base imposable')}</th>
              <th className="px-5 py-2 text-right font-medium">{t('models_fiscals.retencio.import', 'Retenció')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {data.desglossat.length === 0 ? (
              <tr><td colSpan={4} className="px-5 py-4 text-zinc-400 text-center text-xs">{t('iva.no_data', 'Sense dades')}</td></tr>
            ) : data.desglossat.map((d, i) => (
              <tr key={i} className="hover:bg-zinc-50">
                <td className="px-5 py-2.5 text-zinc-700">{d.nom}</td>
                <td className="px-5 py-2.5 text-zinc-500 font-mono text-xs">{d.nif || '—'}</td>
                <td className="px-5 py-2.5 text-right text-zinc-600">{fmtEur(d.base)}</td>
                <td className="px-5 py-2.5 text-right font-medium text-orange-700">{fmtEur(d.retencio)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ForaAbast items={data.fora_abast} t={t} />
    </div>
  );
}
