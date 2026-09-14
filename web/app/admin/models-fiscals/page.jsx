'use client';

import { useState, useEffect, useMemo } from 'react';
import { authFetch } from '../../lib/auth';
import { Button } from '../../../components/ui/button';
import MIcon from '../../../components/ui/m-icon';
import { useT } from '../../lib/i18n';

function fmtEur(v) {
  if (v == null) return '—';
  return parseFloat(v).toFixed(2) + ' €';
}

const NOW = new Date();

function Casella({ num, label, value, sign }) {
  return (
    <div className="bg-surface-container-high border border-outline-variant rounded-lg p-3">
      <div className="text-[10px] font-mono text-secondary-foreground mb-0.5">Casella {num}</div>
      <div className="text-xs text-secondary-foreground mb-1">{label}</div>
      <div className="text-base font-semibold text-on-surface">{sign}{fmtEur(value)}</div>
    </div>
  );
}

function ForaAbast({ items, t }) {
  if (!items?.length) return null;
  return (
    <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs">
      <MIcon name="warning" size={14} className="text-amber-500 mt-0.5 flex-shrink-0" />
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
        <h2 className="text-2xl font-bold text-on-surface">{t('nav.models_fiscals', 'Models AEAT')}</h2>
        <p className="text-sm text-secondary-foreground mt-1">
          {t('models_fiscals.subtitle', 'Caselles per copiar a la seu electrònica o passar a la gestoria — cap d’aquests informes es presenta telemàticament des d’aquí.')}
        </p>
      </div>

      <div className="flex gap-1 bg-surface-container-high p-1 rounded-xl w-fit">
        {MODELS.map(m => (
          <button key={m.key} onClick={() => setModel(m.key)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${model === m.key ? 'bg-card shadow-sm text-on-surface' : 'text-on-surface-variant hover:text-on-surface'}`}>
            {m.label}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <select value={year} onChange={e => setYear(Number(e.target.value))}
          className="border border-outline-variant rounded-lg px-3 py-1.5 text-sm bg-card focus:outline-none focus:ring-2 focus:ring-primary">
          {[2023, 2024, 2025, 2026].map(y => <option key={y}>{y}</option>)}
        </select>
        {!['390', '190', '180', '200', '202'].includes(model) && (
          <div className="flex gap-2">
            {TRIMESTRES.map(tr => (
              <button key={tr.value} onClick={() => setTrim(tr.value)}
                className={`px-4 py-1.5 rounded-lg text-sm border transition-colors ${trim === tr.value ? 'bg-primary text-white border-primary' : 'bg-card text-on-surface-variant border-outline-variant hover:border-outline'}`}>
                {tr.value}T
              </button>
            ))}
          </div>
        )}
        {model === '202' && (
          <div className="flex gap-2">
            {PERIODES_202.map(p => (
              <button key={p.value} onClick={() => setPeriode202(p.value)}
                className={`px-4 py-1.5 rounded-lg text-sm border transition-colors ${periode202 === p.value ? 'bg-primary text-white border-primary' : 'bg-card text-on-surface-variant border-outline-variant hover:border-outline'}`}>
                {p.label}
              </button>
            ))}
          </div>
        )}
        {model === '130' && (
          <label className="flex items-center gap-1.5 text-sm text-on-surface-variant cursor-pointer select-none">
            <input type="checkbox" checked={reduccio5pct} onChange={e => setReduccio5pct(e.target.checked)}
              className="rounded border-outline-variant text-on-surface focus:ring-primary" />
            {t('models_fiscals.130.reduccio_toggle', 'Aplicar reducció 5% (estimació directa simplificada)')}
          </label>
        )}
        <span className="text-sm text-secondary-foreground">{MODELS.find(m => m.key === model)?.sub}</span>
      </div>

      {model === '200' && (
        <div className="flex items-end gap-4 flex-wrap bg-surface-container-high border border-outline-variant rounded-xl p-4">
          <div>
            <label className="block text-xs text-secondary-foreground mb-1">{t('models_fiscals.200.tipus_pct', 'Tipus impositiu *')}</label>
            <select value={tipusPct} onChange={e => setTipusPct(e.target.value)}
              className="border border-outline-variant rounded-lg px-3 py-1.5 text-sm bg-card focus:outline-none focus:ring-2 focus:ring-primary">
              <option value="">{t('models_fiscals.200.tipus_pct_choose', "— Tria'n un —")}</option>
              <option value="25.00">{t('models_fiscals.200.tipus_general', 'General 25%')}</option>
              <option value="15.00">{t('models_fiscals.200.tipus_nova_creacio', 'Reduït 15% (entitat de nova creació)')}</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-secondary-foreground mb-1">{t('models_fiscals.200.pagaments_fraccionats', 'Pagaments fraccionats (202) ja satisfets')}</label>
            <input type="number" step="0.01" value={pagamentsFraccionats} onChange={e => setPagamentsFraccionats(e.target.value)}
              className="border border-outline-variant rounded-lg px-3 py-1.5 text-sm w-40 focus:outline-none focus:ring-2 focus:ring-primary" />
          </div>
        </div>
      )}

      {model === '202' && (
        <div className="flex items-end gap-4 flex-wrap bg-surface-container-high border border-outline-variant rounded-xl p-4">
          <div>
            <label className="block text-xs text-secondary-foreground mb-1">{t('models_fiscals.202.cuota_anterior', "Quota íntegra de l'exercici anterior *")}</label>
            <input type="number" step="0.01" value={cuotaAnterior202} onChange={e => setCuotaAnterior202(e.target.value)}
              placeholder="0.00"
              className="border border-outline-variant rounded-lg px-3 py-1.5 text-sm w-48 focus:outline-none focus:ring-2 focus:ring-primary" />
          </div>
        </div>
      )}

      {loading ? (
        <div className="p-12 text-center text-secondary-foreground text-sm">{t('common.loading', 'Carregant...')}</div>
      ) : !data ? (
        <div className="p-12 text-center text-secondary-foreground text-sm">
          {model === '200' && !tipusPct ? t('models_fiscals.200.tria_tipus', 'Tria un tipus impositiu per calcular.')
            : model === '202' && !cuotaAnterior202 ? t('models_fiscals.202.introdueix_cuota', "Introdueix la quota de l'exercici anterior per calcular.")
            : t('iva.no_data', 'Sense dades')}
        </div>
      ) : model === '303' ? (
        <Model303View data={data} t={t} year={year} trimestre={trim} />
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

const TIPUS_DECLARACIO_303 = [
  { value: 'I', label: "I — Ingrés" },
  { value: 'D', label: "D — Devolució" },
  { value: 'N', label: "N — Sense activitat / resultat 0" },
  { value: 'C', label: "C — Sol·licitud de compensació" },
  { value: 'G', label: "G — Compte corrent tributària (deute)" },
  { value: 'V', label: "V — Compte corrent tributària (devolució)" },
  { value: 'U', label: "U — Domiciliació de l'ingrés" },
  { value: 'X', label: "X — Devolució per transferència a l'estranger" },
];

function Model303View({ data, t, year, trimestre }) {
  const [showFitxer, setShowFitxer] = useState(false);
  const hasRecc = parseFloat(data.casella_62_devengat_recc || 0) !== 0
    || parseFloat(data.casella_63_cuota_recc || 0) !== 0
    || parseFloat(data.casella_74_base_recc_suportat || 0) !== 0
    || parseFloat(data.casella_75_cuota_recc_suportat || 0) !== 0;
  const hasImportDiferit = parseFloat(data.casella_77_iva_importacio_diferit || 0) !== 0;
  const hasCompensacio = parseFloat(data.casella_110_compensacio_pendent_anterior || 0) !== 0;

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setShowFitxer(true)}>
          <MIcon name="download" size={16} /> {t('models_fiscals.303.generar_fitxer', 'Generar fitxer AEAT')}
        </Button>
      </div>

      {data.nota_rebu && (
        <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-xl p-4">
          <MIcon name="warning" size={18} className="text-amber-500 mt-0.5 flex-shrink-0" />
          <p className="text-sm text-amber-800">
            {t('iva.rebu_warning_body', "Hi ha vendes de discos de 2a mà (REBU) en aquest trimestre. Sota el règim especial de béns usats, l'IVA s'aplica només al marge de benefici. Consulta el teu gestor per al càlcul correcte del model 303.")}
          </p>
        </div>
      )}

      <div>
        <div className="text-xs font-semibold text-secondary-foreground uppercase tracking-wide mb-2">{t('models_fiscals.303.repercutit', 'IVA repercutit')}</div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {data.repercutit_general && <Casella num="01-03" label={`General (${data.repercutit_general.pct}%)`} value={data.repercutit_general.cuota} sign="+" />}
          {data.repercutit_reduit && <Casella num="04-06" label={`Reduït (${data.repercutit_reduit.pct}%)`} value={data.repercutit_reduit.cuota} sign="+" />}
          {data.repercutit_superreduit && <Casella num="07-09" label={`Superreduït (${data.repercutit_superreduit.pct}%)`} value={data.repercutit_superreduit.cuota} sign="+" />}
          <Casella num="27" label={t('models_fiscals.303.casella_27', 'Quota meritada total')} value={data.casella_27_cuota_meritada} sign="+" />
        </div>
      </div>

      <div>
        <div className="text-xs font-semibold text-secondary-foreground uppercase tracking-wide mb-2">{t('models_fiscals.303.suportat', 'IVA suportat')}</div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <Casella num="28" label={t('models_fiscals.303.casella_28', 'Base corrent')} value={data.casella_28_base_corrent} sign="" />
          <Casella num="29" label={t('models_fiscals.303.casella_29', 'Quota corrent')} value={data.casella_29_cuota_corrent} sign="–" />
          <Casella num="30" label={t('models_fiscals.303.casella_30', "Base béns d'inversió")} value={data.casella_30_base_inversio} sign="" />
          <Casella num="31" label={t('models_fiscals.303.casella_31', "Quota béns d'inversió")} value={data.casella_31_cuota_inversio} sign="–" />
          <Casella num="45" label={t('models_fiscals.303.casella_45', 'Total a deduir')} value={data.casella_45_total_a_deduir} sign="–" />
        </div>
      </div>

      {hasRecc && (
        <div>
          <div className="text-xs font-semibold text-secondary-foreground uppercase tracking-wide mb-2">{t('models_fiscals.303.recc', 'Criteri de caixa (RECC) — informatiu')}</div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Casella num="62" label={t('models_fiscals.303.casella_62', 'Meritat base')} value={data.casella_62_devengat_recc} sign="+" />
            <Casella num="63" label={t('models_fiscals.303.casella_63', 'Meritat quota')} value={data.casella_63_cuota_recc} sign="+" />
            <Casella num="74" label={t('models_fiscals.303.casella_74', 'Suportat base')} value={data.casella_74_base_recc_suportat} sign="" />
            <Casella num="75" label={t('models_fiscals.303.casella_75', 'Suportat quota')} value={data.casella_75_cuota_recc_suportat} sign="–" />
          </div>
        </div>
      )}

      {hasImportDiferit && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <Casella num="77" label={t('models_fiscals.303.casella_77', 'IVA importació diferit')} value={data.casella_77_iva_importacio_diferit} sign="" />
        </div>
      )}

      {hasCompensacio && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <Casella num="110" label={t('models_fiscals.303.casella_110', "Compensació pendent d'exercicis anteriors")} value={data.casella_110_compensacio_pendent_anterior} sign="" />
        </div>
      )}

      <div className={`rounded-xl p-4 border ${parseFloat(data.casella_64_resultat_liquidacio) >= 0 ? 'bg-orange-50 border-orange-200' : 'bg-emerald-50 border-emerald-200'}`}>
        <div className="text-xs text-secondary-foreground mb-1">{t('models_fiscals.303.casella_64', 'Casella 64 · Resultat de la liquidació')}</div>
        <div className="text-xl font-bold text-on-surface">{fmtEur(data.casella_64_resultat_liquidacio)}</div>
      </div>

      <ForaAbast items={data.fora_abast} t={t} />

      {showFitxer && (
        <GenerarFitxer303Modal
          year={year} trimestre={trimestre}
          casella110={parseFloat(data.casella_110_compensacio_pendent_anterior || 0)}
          onClose={() => setShowFitxer(false)}
        />
      )}
    </div>
  );
}

function GenerarFitxer303Modal({ year, trimestre, casella110, onClose }) {
  const t = useT();
  const [tipoDeclaracion, setTipoDeclaracion] = useState('I');
  const [esComplementaria, setEsComplementaria] = useState(false);
  const [numeroJustificantAnterior, setNumeroJustificantAnterior] = useState('');
  const [importCompensacioAplicada, setImportCompensacioAplicada] = useState('0.00');
  const [cnaeCode, setCnaeCode] = useState('');
  const [ibanDevolucio, setIbanDevolucio] = useState('');
  const [bicDevolucio, setBicDevolucio] = useState('');
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');

  async function generar(e) {
    e.preventDefault();
    setGenerating(true);
    setError('');
    const payload = {
      tipo_declaracion: tipoDeclaracion,
      es_complementaria: esComplementaria,
      numero_justificante_anterior: esComplementaria ? (numeroJustificantAnterior || null) : null,
      import_compensacio_aplicada: parseFloat(importCompensacioAplicada || '0'),
      cnae_code: cnaeCode || null,
      iban_devolucio: ibanDevolucio || null,
      bic_devolucio: bicDevolucio || null,
    };
    const r = await authFetch(`/admin/aeat/303/${year}/${trimestre}/fitxer`, { method: 'POST', body: JSON.stringify(payload) });
    if (r.ok) {
      const blob = await r.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `303_${year}_${trimestre}T.txt`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      setGenerating(false);
      onClose();
    } else {
      setGenerating(false);
      setError((await r.json()).detail || t('common.error_saving', 'Error generant el fitxer'));
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-card rounded-2xl shadow-2xl w-full max-w-md max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b border-outline-variant">
          <h3 className="text-lg font-bold text-on-surface">{t('models_fiscals.303.generar_fitxer_title', 'Generar fitxer Model 303')} — {trimestre}T {year}</h3>
          <button onClick={onClose} className="text-secondary-foreground hover:text-on-surface-variant p-1 rounded-lg hover:bg-surface-container-high"><MIcon name="close" size={20} /></button>
        </div>
        <form onSubmit={generar} className="p-6 space-y-4">
          <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-800">
            <MIcon name="warning" size={14} className="text-amber-500 mt-0.5 flex-shrink-0" />
            {t('models_fiscals.303.fitxer_warning', "Fitxer no verificat contra una presentació real — prova'l amb el validador de la Seu Electrònica abans de confiar-hi en producció.")}
          </div>
          <div>
            <label className="block text-sm font-medium text-on-surface-variant mb-1">{t('models_fiscals.303.tipo_declaracion', 'Tipus de declaració')} *</label>
            <select value={tipoDeclaracion} onChange={e => setTipoDeclaracion(e.target.value)}
              className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm bg-card focus:outline-none focus:ring-2 focus:ring-primary">
              {TIPUS_DECLARACIO_303.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm text-on-surface-variant">
            <input type="checkbox" checked={esComplementaria} onChange={e => setEsComplementaria(e.target.checked)} />
            {t('models_fiscals.303.es_complementaria', 'És una declaració complementària')}
          </label>
          {esComplementaria && (
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1">{t('models_fiscals.303.numero_justificant_anterior', 'Nº justificant de la declaració anterior')}</label>
              <input value={numeroJustificantAnterior} onChange={e => setNumeroJustificantAnterior(e.target.value)}
                className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
            </div>
          )}
          {casella110 > 0 && (
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1">{t('models_fiscals.303.compensacio_aplicada', 'Import de compensació a aplicar')} (€)</label>
              <input type="number" step="0.01" min="0" max={casella110} value={importCompensacioAplicada} onChange={e => setImportCompensacioAplicada(e.target.value)}
                className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
              <p className="text-xs text-secondary-foreground mt-1">{t('models_fiscals.303.compensacio_disponible', 'Disponible')}: {fmtEur(casella110)}</p>
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-on-surface-variant mb-1">{t('models_fiscals.303.cnae', 'Codi CNAE')} <span className="text-secondary-foreground font-normal">({t('models_fiscals.303.cnae_hint', 'obligatori només si hi ha prorrata especial configurada')})</span></label>
            <input value={cnaeCode} onChange={e => setCnaeCode(e.target.value)} placeholder="476"
              className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1">{t('models_fiscals.303.iban', 'IBAN devolució/domiciliació')}</label>
              <input value={ibanDevolucio} onChange={e => setIbanDevolucio(e.target.value)} placeholder="ES..."
                className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
            </div>
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1">BIC</label>
              <input value={bicDevolucio} onChange={e => setBicDevolucio(e.target.value)}
                className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
            </div>
          </div>
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel', "Cancel·lar")}</Button>
            <Button type="submit" disabled={generating}>{generating ? t('common.saving', 'Generant...') : t('models_fiscals.303.descarregar', 'Descarregar fitxer')}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Model390View({ data, t }) {
  return (
    <div className="space-y-4">
      <div className="bg-card rounded-2xl border border-outline-variant shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-surface-container-high text-xs text-secondary-foreground">
            <tr>
              <th className="px-5 py-2 text-left font-medium">{t('models_fiscals.390.trimestre', 'Trimestre')}</th>
              <th className="px-5 py-2 text-right font-medium">{t('models_fiscals.303.casella_27', 'Quota meritada')}</th>
              <th className="px-5 py-2 text-right font-medium">{t('models_fiscals.303.casella_45', 'Total a deduir')}</th>
              <th className="px-5 py-2 text-right font-medium">{t('iva.result', 'Resultat')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant">
            {data.trimestres.map(tr => (
              <tr key={tr.trimestre} className="hover:bg-surface-container-high">
                <td className="px-5 py-2.5 font-medium text-on-surface-variant">{tr.trimestre}T</td>
                <td className="px-5 py-2.5 text-right text-on-surface-variant">+{fmtEur(tr.casella_27_cuota_meritada)}</td>
                <td className="px-5 py-2.5 text-right text-on-surface-variant">–{fmtEur(tr.casella_45_total_a_deduir)}</td>
                <td className="px-5 py-2.5 text-right font-semibold text-on-surface">{fmtEur(tr.resultat)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="bg-surface-container-high font-semibold text-sm border-t border-outline-variant">
              <td className="px-5 py-3 text-on-surface-variant">{t('models_fiscals.390.total_anual', 'Total anual')}</td>
              <td className="px-5 py-3 text-right text-on-surface-variant">+{fmtEur(data.casella_27_cuota_meritada_anual)}</td>
              <td className="px-5 py-3 text-right text-on-surface-variant">–{fmtEur(data.casella_45_total_a_deduir_anual)}</td>
              <td className="px-5 py-3 text-right text-on-surface">{fmtEur(data.resultat_anual)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      {data.nota_rebu && (
        <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-xl p-4">
          <MIcon name="warning" size={18} className="text-amber-500 mt-0.5 flex-shrink-0" />
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
          <MIcon name="warning" size={18} className="text-amber-500 mt-0.5 flex-shrink-0" />
          <p className="text-sm text-amber-800">{data.forma_juridica_nota}</p>
        </div>
      )}

      <div>
        <div className="text-xs font-semibold text-secondary-foreground uppercase tracking-wide mb-2">
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
        <div className="bg-surface-container-high border border-outline-variant rounded-lg p-3">
          <div className="text-[10px] font-mono text-secondary-foreground mb-0.5">Casella 04</div>
          <div className="text-xs text-secondary-foreground mb-1">{t('models_fiscals.130.casella_04', 'Percentatge')}</div>
          <div className="text-base font-semibold text-on-surface">{parseFloat(data.casella_04_pct).toFixed(0)}%</div>
        </div>
        <Casella num="05" label={t('models_fiscals.130.casella_05', 'Import (03 × 20%)')} value={data.casella_05_import} sign="+" />
        <Casella num="07" label={t('models_fiscals.130.casella_07', 'Pagaments fraccionats anteriors')} value={data.casella_07_pagaments_anteriors} sign="–" />
      </div>

      <div className={`rounded-xl p-4 border ${parseFloat(data.resultat) > 0 ? 'bg-orange-50 border-orange-200' : 'bg-surface-container-high border-outline-variant'}`}>
        <div className="text-xs text-secondary-foreground mb-1">{t('models_fiscals.130.resultat', 'Resultat · A ingressar aquest trimestre')}</div>
        <div className="text-xl font-bold text-on-surface">{fmtEur(data.resultat)}</div>
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
          <MIcon name="warning" size={18} className="text-amber-500 mt-0.5 flex-shrink-0" />
          <p className="text-sm text-amber-800">{data.forma_juridica_nota}</p>
        </div>
      )}

      <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-xl p-3 text-xs text-red-800">
        <MIcon name="warning" size={14} className="text-red-500 mt-0.5 flex-shrink-0" />
        {t('models_fiscals.200.disclaimer', 'Estimació de suport, no un càlcul fiscal complet: assumeix zero ajustos extracomptables. No presentar sense revisar-ho amb la gestoria.')}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <Casella num="—" label={t('models_fiscals.200.resultat_comptable', 'Resultat comptable')} value={data.resultat_comptable} sign="" />
        <Casella num="—" label={t('models_fiscals.200.ajustos', 'Ajustos extracomptables')} value={data.ajustos_extracomptables} sign="" />
        <Casella num="—" label={t('models_fiscals.200.base_imposable', 'Base imposable')} value={data.base_imposable} sign="" />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <div className="bg-surface-container-high border border-outline-variant rounded-lg p-3">
          <div className="text-xs text-secondary-foreground mb-1">{t('models_fiscals.200.tipus_pct', 'Tipus impositiu')}</div>
          <div className="text-base font-semibold text-on-surface">{parseFloat(data.tipus_pct).toFixed(0)}%</div>
        </div>
        <Casella num="—" label={t('models_fiscals.200.quota_integra', 'Quota íntegra')} value={data.quota_integra} sign="" />
        <Casella num="—" label={t('models_fiscals.200.pagaments_fraccionats', 'Pagaments fraccionats satisfets')} value={data.pagaments_fraccionats_satisfets} sign="–" />
      </div>

      <div className={`rounded-xl p-4 border ${parseFloat(data.resultat) >= 0 ? 'bg-orange-50 border-orange-200' : 'bg-emerald-50 border-emerald-200'}`}>
        <div className="text-xs text-secondary-foreground mb-1">
          {parseFloat(data.resultat) >= 0 ? t('models_fiscals.200.resultat_a_ingressar', 'Resultat · A ingressar') : t('models_fiscals.200.resultat_a_retornar', 'Resultat · A retornar')}
        </div>
        <div className="text-xl font-bold text-on-surface">{fmtEur(Math.abs(parseFloat(data.resultat)))}</div>
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
          <MIcon name="warning" size={18} className="text-amber-500 mt-0.5 flex-shrink-0" />
          <p className="text-sm text-amber-800">{data.forma_juridica_nota}</p>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <Casella num="—" label={t('models_fiscals.202.cuota_anterior', "Quota íntegra exercici anterior")} value={data.cuota_integra_exercici_anterior} sign="" />
        <div className="bg-surface-container-high border border-outline-variant rounded-lg p-3">
          <div className="text-xs text-secondary-foreground mb-1">{t('models_fiscals.202.pct', 'Percentatge')}</div>
          <div className="text-base font-semibold text-on-surface">{parseFloat(data.pct).toFixed(0)}%</div>
        </div>
      </div>

      <div className="rounded-xl p-4 border bg-orange-50 border-orange-200">
        <div className="text-xs text-secondary-foreground mb-1">{t('models_fiscals.202.import', 'Import a ingressar')} · {data.periode_nom}</div>
        <div className="text-xl font-bold text-on-surface">{fmtEur(data.import_pagament)}</div>
      </div>

      <ForaAbast items={data.fora_abast} t={t} />
    </div>
  );
}

function ModelRetencioAnualView({ data, t }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-surface-container-high border border-outline-variant rounded-xl p-4">
          <div className="text-xs text-secondary-foreground mb-1">{t('models_fiscals.retencio.perceptors', 'Nº perceptors')}</div>
          <div className="text-xl font-bold text-on-surface">{data.num_perceptors}</div>
        </div>
        <div className="bg-surface-container-high border border-outline-variant rounded-xl p-4">
          <div className="text-xs text-secondary-foreground mb-1">{t('models_fiscals.retencio.base', 'Base total')}</div>
          <div className="text-xl font-bold text-on-surface">{fmtEur(data.base_total)}</div>
        </div>
        <div className="bg-orange-50 border border-orange-200 rounded-xl p-4">
          <div className="text-xs text-orange-600 mb-1">{t('models_fiscals.retencio.total', 'Retenció a ingressar')}</div>
          <div className="text-xl font-bold text-orange-700">{fmtEur(data.retencio_total)}</div>
        </div>
      </div>

      <div className="bg-card rounded-2xl border border-outline-variant shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-surface-container-high text-xs text-secondary-foreground">
            <tr>
              <th className="px-5 py-2 text-left font-medium">{t('models_fiscals.390.trimestre', 'Trimestre')}</th>
              <th className="px-5 py-2 text-right font-medium">{t('despeses.taxable_base', 'Base imposable')}</th>
              <th className="px-5 py-2 text-right font-medium">{t('models_fiscals.retencio.import', 'Retenció')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant">
            {data.trimestres.map(tr => (
              <tr key={tr.trimestre} className="hover:bg-surface-container-high">
                <td className="px-5 py-2.5 font-medium text-on-surface-variant">{tr.trimestre}T</td>
                <td className="px-5 py-2.5 text-right text-on-surface-variant">{fmtEur(tr.base_total)}</td>
                <td className="px-5 py-2.5 text-right font-medium text-orange-700">{fmtEur(tr.retencio_total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-secondary-foreground">
        {t('models_fiscals.190_180.nota_trimestres', 'Els totals per trimestre poden sumar més que el total anual si un mateix proveïdor apareix en diversos trimestres — el nombre de perceptors de dalt és el recompte correcte, sobre tot l’any.')}
      </p>

      <div className="bg-card rounded-2xl border border-outline-variant shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-surface-container-high text-xs text-secondary-foreground">
            <tr>
              <th className="px-5 py-2 text-left font-medium">{t('nav.proveidors', 'Proveïdor')}</th>
              <th className="px-5 py-2 text-left font-medium">NIF</th>
              <th className="px-5 py-2 text-right font-medium">{t('despeses.taxable_base', 'Base imposable')}</th>
              <th className="px-5 py-2 text-right font-medium">{t('models_fiscals.retencio.import', 'Retenció')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant">
            {data.desglossat.length === 0 ? (
              <tr><td colSpan={4} className="px-5 py-4 text-secondary-foreground text-center text-xs">{t('iva.no_data', 'Sense dades')}</td></tr>
            ) : data.desglossat.map((d, i) => (
              <tr key={i} className="hover:bg-surface-container-high">
                <td className="px-5 py-2.5 text-on-surface-variant">{d.nom}</td>
                <td className="px-5 py-2.5 text-secondary-foreground font-mono text-xs">{d.nif || '—'}</td>
                <td className="px-5 py-2.5 text-right text-on-surface-variant">{fmtEur(d.base)}</td>
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
        <div className="bg-surface-container-high border border-outline-variant rounded-xl p-4">
          <div className="text-xs text-secondary-foreground mb-1">{t('models_fiscals.retencio.perceptors', 'Nº perceptors')}</div>
          <div className="text-xl font-bold text-on-surface">{data.num_perceptors}</div>
        </div>
        <div className="bg-surface-container-high border border-outline-variant rounded-xl p-4">
          <div className="text-xs text-secondary-foreground mb-1">{t('models_fiscals.retencio.base', 'Base total')}</div>
          <div className="text-xl font-bold text-on-surface">{fmtEur(data.base_total)}</div>
        </div>
        <div className="bg-orange-50 border border-orange-200 rounded-xl p-4">
          <div className="text-xs text-orange-600 mb-1">{t('models_fiscals.retencio.total', 'Retenció a ingressar')}</div>
          <div className="text-xl font-bold text-orange-700">{fmtEur(data.retencio_total)}</div>
        </div>
      </div>

      <div className="bg-card rounded-2xl border border-outline-variant shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-surface-container-high text-xs text-secondary-foreground">
            <tr>
              <th className="px-5 py-2 text-left font-medium">{t('nav.proveidors', 'Proveïdor')}</th>
              <th className="px-5 py-2 text-left font-medium">NIF</th>
              <th className="px-5 py-2 text-right font-medium">{t('despeses.taxable_base', 'Base imposable')}</th>
              <th className="px-5 py-2 text-right font-medium">{t('models_fiscals.retencio.import', 'Retenció')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant">
            {data.desglossat.length === 0 ? (
              <tr><td colSpan={4} className="px-5 py-4 text-secondary-foreground text-center text-xs">{t('iva.no_data', 'Sense dades')}</td></tr>
            ) : data.desglossat.map((d, i) => (
              <tr key={i} className="hover:bg-surface-container-high">
                <td className="px-5 py-2.5 text-on-surface-variant">{d.nom}</td>
                <td className="px-5 py-2.5 text-secondary-foreground font-mono text-xs">{d.nif || '—'}</td>
                <td className="px-5 py-2.5 text-right text-on-surface-variant">{fmtEur(d.base)}</td>
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
