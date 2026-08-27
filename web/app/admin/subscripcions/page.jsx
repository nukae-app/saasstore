'use client';

import { useEffect, useMemo, useState } from 'react';
import { authFetch } from '../../lib/auth';
import { useT } from '../../lib/i18n';
import { Button } from '../../../components/ui/button';
import { useSortFilter } from '../../../components/admin/table/useSortFilter';
import { SortableTh } from '../../../components/admin/table/SortableTh';
import { Check, Loader2, RefreshCw, X } from 'lucide-react';

const ESTAT_FALLBACK = {
  pendent_pagament: 'Pendent de pagament', activa: 'Activa', pausada: 'Pausada', cancel_lada: 'Cancel·lada',
};
const ESTAT_COLOR = {
  pendent_pagament: 'bg-amber-100 text-amber-700', activa: 'bg-emerald-100 text-emerald-700',
  pausada: 'bg-zinc-100 text-zinc-500', cancel_lada: 'bg-red-100 text-red-600',
};
function estatLabel(t, estat) {
  return t(`subscriptions.status.${estat}`, ESTAT_FALLBACK[estat] ?? estat);
}

export default function SubscripcionsPage() {
  const t = useT();
  const [tab, setTab] = useState('cicle'); // cicle | subscriptors | catalog | informes | configuracio

  return (
    <div className="space-y-5 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-zinc-900">{t('subscriptions.title', 'Club del disc')}</h2>
      </div>

      <div className="flex gap-1 bg-zinc-100 p-1 rounded-xl w-fit">
        {[
          ['cicle', t('subscriptions.tab.cycle', 'Cicle actual')], ['subscriptors', t('subscriptions.tab.subscribers', 'Subscriptors')],
          ['catalog', t('catalog.title')], ['informes', t('subscriptions.tab.reports', 'Informes')], ['configuracio', t('subscriptions.tab.config', 'Configuració')],
        ].map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${tab === k ? 'bg-white shadow-sm text-zinc-900' : 'text-zinc-600 hover:text-zinc-900'}`}>
            {l}
          </button>
        ))}
      </div>

      {tab === 'cicle' && <CiclePanel />}
      {tab === 'subscriptors' && <SubscriptorsPanel />}
      {tab === 'catalog' && <CatalogPanel />}
      {tab === 'informes' && <InformesPanel />}
      {tab === 'configuracio' && <ConfiguracioPanel />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Cicle: cobraments pendents -> proposar -> revisar -> confirmar per enviament
// ---------------------------------------------------------------------------

function CiclePanel() {
  const t = useT();
  const [pendents, setPendents] = useState([]);
  const [enviaments, setEnviaments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [proposant, setProposant] = useState(false);
  const [confirmantTot, setConfirmantTot] = useState(false);
  const [reintentant, setReintentant] = useState(null); // cobrament_id en curs, o null

  async function load() {
    setLoading(true);
    try {
      const [rp, ra] = await Promise.all([
        authFetch('/admin/subscripcions/cobraments-pendents'),
        authFetch('/admin/subscripcions/assignacions'),
      ]);
      setPendents(await rp.json());
      setEnviaments(await ra.json());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function proposar() {
    setProposant(true);
    try {
      const r = await authFetch('/admin/subscripcions/proposar', { method: 'POST' });
      const d = await r.json();
      if (d.errors?.length) {
        alert(t('subscriptions.cycle.propose_result', '{n} generats, {errors} amb error (revisa el registre del servidor).')
          .replace('{n}', d.enviaments_proposats).replace('{errors}', d.errors.length));
      }
      await load();
    } finally {
      setProposant(false);
    }
  }

  async function ometre(assignacioId) {
    await authFetch(`/admin/subscripcions/assignacions/${assignacioId}`, {
      method: 'PATCH', body: JSON.stringify({ ometre: true }),
    });
    load();
  }

  async function reintentarEnviament(cobramentId) {
    setReintentant(cobramentId);
    try {
      const r = await authFetch(`/admin/subscripcions/cobraments/${cobramentId}/reintentar`, { method: 'POST' });
      const d = await r.json();
      if (d.trobats === 0) alert(t('subscriptions.cycle.no_match_yet', 'Encara no hi ha cap disc a la safata que hi encaixi.'));
      await load();
    } finally {
      setReintentant(null);
    }
  }

  async function confirmarEnviament(cobramentId) {
    const r = await authFetch(`/admin/subscripcions/cobraments/${cobramentId}/confirmar`, { method: 'POST' });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      alert(d.detail || t('subscriptions.cycle.confirm_error', 'No s\'ha pogut confirmar'));
      return;
    }
    load();
  }

  async function confirmarTotes() {
    const llestos = enviaments.filter(e => e.discos.some(d => d.item)).length;
    if (!confirm(t('subscriptions.cycle.confirm_all_hint', 'Confirmar els {n} enviaments amb algun disc trobat? Es generarà la venda de cadascun.').replace('{n}', llestos))) return;
    setConfirmantTot(true);
    try {
      const r = await authFetch('/admin/subscripcions/cobraments/confirmar-totes', { method: 'POST' });
      const d = await r.json();
      if (d.errors?.length) alert(t('subscriptions.cycle.confirm_all_result', '{n} confirmats, {errors} amb error (revisa\'ls)').replace('{n}', d.confirmades).replace('{errors}', d.errors.length));
      await load();
    } finally {
      setConfirmantTot(false);
    }
  }

  if (loading) return <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading')}</div>;

  return (
    <div className="space-y-5">
      {pendents.length > 0 && (
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-5 flex items-center justify-between">
          <div>
            <p className="font-semibold text-zinc-900">
              {pendents.length} {pendents.length !== 1
                ? t('subscriptions.cycle.new_shipments_plural', 'enviaments nous per generar')
                : t('subscriptions.cycle.new_shipments_singular', 'enviament nou per generar')}
            </p>
            <p className="text-xs text-zinc-500 mt-0.5">{t('subscriptions.cycle.new_shipments_hint', "Ja s'han cobrat; falta triar quins exemplars de la safata envia cadascú.")}</p>
          </div>
          <Button size="sm" onClick={proposar} disabled={proposant}>
            {proposant ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            {proposant ? t('subscriptions.cycle.generating', 'Generant...') : t('subscriptions.cycle.generate_proposal', 'Generar proposta')}
          </Button>
        </div>
      )}

      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-zinc-900">{t('subscriptions.cycle.shipments_to_manage', 'Enviaments per gestionar')} ({enviaments.length})</h3>
        {enviaments.length > 0 && (
          <Button size="sm" onClick={confirmarTotes} disabled={confirmantTot}>
            {confirmantTot ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
            {t('subscriptions.cycle.confirm_ready', 'Confirmar els llestos')}
          </Button>
        )}
      </div>

      {enviaments.length === 0 ? (
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-12 text-center text-zinc-400 text-sm">
          {t('subscriptions.cycle.no_pending_shipments', 'Cap enviament pendent de gestionar. Si n\'hi ha de nous a dalt, prem "Generar proposta".')}
        </div>
      ) : (
        <div className="space-y-4">
          {enviaments.map(env => {
            const trobats = env.discos.filter(d => d.item).length;
            const senseMatch = env.discos.length - trobats;
            return (
              <div key={env.cobrament_id} className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
                <div className="px-5 py-3 flex items-center justify-between border-b border-zinc-100 flex-wrap gap-2">
                  <div>
                    <span className="font-medium text-zinc-900">{env.email}</span>
                    <span className="text-xs text-zinc-400 ml-2">
                      {trobats}/{env.discos.length} {t('subscriptions.cycle.records_found', 'discs trobats')} · {env.import_cobrat} €
                    </span>
                  </div>
                  <div className="flex gap-2">
                    {senseMatch > 0 && (
                      <button onClick={() => reintentarEnviament(env.cobrament_id)} disabled={reintentant === env.cobrament_id}
                        className="flex items-center gap-1.5 border border-zinc-200 text-zinc-600 px-3 py-1.5 rounded-lg text-sm hover:bg-zinc-50 transition-colors disabled:opacity-60">
                        {reintentant === env.cobrament_id ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
                        {t('subscriptions.cycle.retry', 'Reintentar')} ({senseMatch})
                      </button>
                    )}
                    <Button size="sm" onClick={() => confirmarEnviament(env.cobrament_id)} disabled={trobats === 0}>
                      <Check size={14} /> {t('subscriptions.cycle.confirm_shipment', 'Confirmar enviament')}
                    </Button>
                  </div>
                </div>
                <div className="divide-y divide-zinc-100">
                  {env.discos.map(d => (
                    <div key={d.assignacio_id} className="px-5 py-3 flex items-center justify-between">
                      {d.item ? (
                        <div className="flex items-center gap-4 text-sm">
                          <span className="text-zinc-900">{d.item.artista} — {d.item.titulo}</span>
                          {d.item.condicion === 'nou' && (
                            <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-green-100 text-green-800">
                              {t('common.condition.new')}
                            </span>
                          )}
                          <span className="text-zinc-500">{d.item.precio} € <span className="text-xs text-zinc-400">({d.item.marge_pct}%)</span></span>
                          <span className="text-zinc-400 text-xs">{d.item.dies_estoc ?? '—'} {t('subscriptions.cycle.days_in_stock', 'dies en estoc')}</span>
                        </div>
                      ) : (
                        <span className="text-amber-600 text-xs font-medium">
                          {t('subscriptions.cycle.no_match_line', 'Sense cap disc de la safata que hi encaixi — afegeix-ne al tab Catàleg i prem "Reintentar"')}
                        </span>
                      )}
                      <button onClick={() => ometre(d.assignacio_id)}
                        className="p-1.5 rounded-lg text-zinc-400 hover:text-red-600 hover:bg-red-50 transition-colors" title={t('subscriptions.cycle.skip_record', 'Ometre aquest disc')}>
                        <X size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Subscriptors
// ---------------------------------------------------------------------------

const LABEL_PERIODICITAT_FALLBACK = { 1: 'mensual', 2: 'cada 2 mesos', 3: 'cada 3 mesos', 6: 'cada 6 mesos', 12: 'anual' };
function periodicitatLabel(t, mesos) {
  return t(`subscriptions.periodicity.${mesos}`, LABEL_PERIODICITAT_FALLBACK[mesos] ?? t('subscriptions.periodicity.every_n_months', 'cada {n} mesos').replace('{n}', mesos));
}

function SubscriptorsPanel() {
  const t = useT();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [obertId, setObertId] = useState(null);

  useEffect(() => {
    authFetch('/admin/subscripcions').then(r => r.json()).then(d => { setRows(d); setLoading(false); });
  }, []);

  const columns = useMemo(() => ({
    client: { sortValue: s => (s.nom || s.email || '').toLowerCase(), filterValue: s => s.nom || s.email },
    periodicitat: {
      sortValue: s => s.periodicitat_mesos,
      filterValue: s => periodicitatLabel(t, s.periodicitat_mesos),
    },
    estat: { sortValue: s => estatLabel(t, s.estat), filterValue: s => estatLabel(t, s.estat) },
    proxima_facturacio: { sortValue: s => s.proxima_facturacio ?? '' },
    ultim_disc_rebut: { sortValue: s => s.ultim_disc_rebut ?? '' },
  }), [t]);

  const { rows: subscriptors, sort, toggleSort, filters, setFilter, distinctValues } = useSortFilter(rows, columns);

  if (loading) return <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading')}</div>;

  return (
    <>
      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {rows.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('subscriptions.no_subscribers', 'Encara no hi ha cap subscriptor.')}</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
              <tr>
                <SortableTh label={t('subscriptions.col.client', 'Client')} sortKey="client" sort={sort} onSort={toggleSort}
                  filterOptions={distinctValues.client} selected={filters.client} onFilterChange={setFilter} />
                <SortableTh label={t('subscriptions.col.subscription', 'Subscripció')} sortKey="periodicitat" sort={sort} onSort={toggleSort}
                  filterOptions={distinctValues.periodicitat} selected={filters.periodicitat} onFilterChange={setFilter} />
                <SortableTh label={t('purchases.col.status', 'Estat')} sortKey="estat" sort={sort} onSort={toggleSort}
                  filterOptions={distinctValues.estat} selected={filters.estat} onFilterChange={setFilter} />
                <SortableTh label={t('subscriptions.col.next_billing', 'Pròxima facturació')} sortKey="proxima_facturacio" sort={sort} onSort={toggleSort} />
                <SortableTh label={t('subscriptions.col.last_record_received', 'Últim disc rebut')} sortKey="ultim_disc_rebut" sort={sort} onSort={toggleSort} />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {subscriptors.map(s => (
                <tr key={s.id} onClick={() => setObertId(s.id)}
                  className="hover:bg-zinc-50 transition-colors cursor-pointer">
                  <td className="px-4 py-3">
                    <div className="text-zinc-900">{s.nom || s.email}</div>
                    <div className="text-xs text-zinc-400">{s.email}</div>
                  </td>
                  <td className="px-4 py-3 text-zinc-600">
                    {s.quantitat} {s.quantitat !== 1 ? t('purchases.record_plural', 'discos') : t('purchases.record_singular', 'disc')} · {periodicitatLabel(t, s.periodicitat_mesos)} · {s.preu_periode} €
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${ESTAT_COLOR[s.estat] || 'bg-zinc-100 text-zinc-500'}`}>
                      {estatLabel(t, s.estat)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-zinc-600">{s.proxima_facturacio}</td>
                  <td className="px-4 py-3 text-zinc-600">{s.ultim_disc_rebut || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {obertId && <SubscriptorDetailModal subscripcioId={obertId} onClose={() => setObertId(null)} />}
    </>
  );
}

function SubscriptorDetailModal({ subscripcioId, onClose }) {
  const t = useT();
  const [detall, setDetall] = useState(null);

  useEffect(() => {
    authFetch(`/admin/subscripcions/${subscripcioId}`).then(r => r.json()).then(setDetall);
  }, [subscripcioId]);

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[85vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        {!detall ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading')}</div>
        ) : (
          <>
            <div className="px-6 py-4 border-b border-zinc-200 flex items-start justify-between">
              <div>
                <h3 className="text-lg font-bold text-zinc-900">{detall.nom || detall.email}</h3>
                <p className="text-sm text-zinc-500">{detall.email}</p>
              </div>
              <button onClick={onClose} className="text-zinc-400 hover:text-zinc-700 p-1">
                <X size={18} />
              </button>
            </div>

            <div className="p-6 space-y-5">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-xs text-zinc-400">{t('subscriptions.col.subscription', 'Subscripció')}</p>
                  <p className="text-zinc-900">
                    {detall.quantitat} {detall.quantitat !== 1 ? t('purchases.record_plural', 'discos') : t('purchases.record_singular', 'disc')} · {periodicitatLabel(t, detall.periodicitat_mesos)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-zinc-400">{t('subscriptions.price_per_shipment', 'Preu per enviament')}</p>
                  <p className="text-zinc-900">{detall.preu_periode} €</p>
                </div>
                <div>
                  <p className="text-xs text-zinc-400">{t('purchases.col.status', 'Estat')}</p>
                  <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${ESTAT_COLOR[detall.estat] || 'bg-zinc-100 text-zinc-500'}`}>
                    {estatLabel(t, detall.estat)}
                  </span>
                </div>
                <div>
                  <p className="text-xs text-zinc-400">{t('subscriptions.col.next_billing', 'Pròxima facturació')}</p>
                  <p className="text-zinc-900">{detall.proxima_facturacio}</p>
                </div>
              </div>

              <div>
                <p className="text-xs text-zinc-400 mb-1.5">{t('subscriptions.music_taste', 'Gustos musicals')}</p>
                {detall.generes_preferits.length === 0 ? (
                  <p className="text-sm text-zinc-400">{t('subscriptions.no_preference', 'Sense preferència (qualsevol gènere)')}</p>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {detall.generes_preferits.map(g => (
                      <span key={g} className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold bg-zinc-900 text-white">
                        {g}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {detall.adreca && (
                <div>
                  <p className="text-xs text-zinc-400 mb-1">{t('subscriptions.shipping_address', "Adreça d'enviament")}</p>
                  <p className="text-sm text-zinc-700">
                    {detall.adreca.recipient_name} — {detall.adreca.address_line1}
                    {detall.adreca.address_line2 ? `, ${detall.adreca.address_line2}` : ''}, {detall.adreca.postal_code} {detall.adreca.city}
                  </p>
                </div>
              )}

              <div>
                <p className="text-xs text-zinc-400 mb-1.5">{t('subscriptions.records_sent', 'Discos enviats')} ({detall.discos_rebuts.length})</p>
                {detall.discos_rebuts.length === 0 ? (
                  <p className="text-sm text-zinc-400">{t('subscriptions.no_records_received', 'Encara no ha rebut cap disc.')}</p>
                ) : (
                  <ul className="divide-y divide-zinc-100 border border-zinc-100 rounded-xl overflow-hidden">
                    {detall.discos_rebuts.map(d => (
                      <li key={`${d.release_id}-${d.confirmada_at}`} className="px-3 py-2 flex items-center gap-3 text-sm">
                        {d.imagen_url ? (
                          <img src={d.imagen_url} alt="" className="w-8 h-8 rounded object-cover" />
                        ) : (
                          <div className="w-8 h-8 rounded bg-zinc-100" />
                        )}
                        <span className="text-zinc-700 flex-1">{d.artista} — {d.titulo}</span>
                        <span className="text-xs text-zinc-400">{d.confirmada_at?.slice(0, 10)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Catàleg: la safata d'exemplars elegibles per subscripció
// ---------------------------------------------------------------------------

function CatalogPanel() {
  const t = useT();
  const [items, setItems] = useState([]);
  const [seccions, setSeccions] = useState([]);
  const [generes, setGeneres] = useState([]);
  const [loading, setLoading] = useState(true);
  const [nomesPool, setNomesPool] = useState(false);
  const [seccioId, setSeccioId] = useState('');
  const [genere, setGenere] = useState('');
  const [ordre, setOrdre] = useState('antiguitat');
  const [margeMin, setMargeMin] = useState('');
  const [margeMax, setMargeMax] = useState('');
  const [limitAuto, setLimitAuto] = useState(50);
  const [seleccionant, setSeleccionant] = useState(false);

  function filterParams() {
    const params = new URLSearchParams();
    if (seccioId) params.set('seccio_id', seccioId);
    if (genere) params.set('genere', genere);
    if (margeMin) params.set('marge_min_pct', margeMin);
    if (margeMax) params.set('marge_max_pct', margeMax);
    return params;
  }

  async function load() {
    setLoading(true);
    const params = filterParams();
    params.set('ordre', ordre);
    if (nomesPool) params.set('nomes_pool', 'true');
    const r = await authFetch(`/admin/subscripcions/catalog?${params}`);
    setItems(await r.json());
    setLoading(false);
  }

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [nomesPool, seccioId, genere, ordre, margeMin, margeMax]);
  useEffect(() => { authFetch('/admin/seccions').then(r => r.json()).then(setSeccions); }, []);
  useEffect(() => { fetch('/api/subscripcions/generes').then(r => r.json()).then(setGeneres); }, []);

  async function togglePool(item) {
    setItems(list => list.map(i => i.item_id === item.item_id ? { ...i, subscripcio_pool: !i.subscripcio_pool } : i));
    await authFetch(`/admin/subscripcions/catalog/${item.item_id}`, {
      method: 'PATCH', body: JSON.stringify({ subscripcio_pool: !item.subscripcio_pool }),
    });
  }

  async function seleccionarAutomaticament() {
    setSeleccionant(true);
    try {
      const body = { limit: Number(limitAuto) || 50 };
      if (seccioId) body.seccio_id = Number(seccioId);
      if (genere) body.genere = genere;
      if (margeMin) body.marge_min_pct = Number(margeMin);
      if (margeMax) body.marge_max_pct = Number(margeMax);
      const r = await authFetch('/admin/subscripcions/catalog/seleccio-automatica', {
        method: 'POST', body: JSON.stringify(body),
      });
      const d = await r.json();
      alert(t('subscriptions.catalog.auto_select_result', '{n} discos afegits a la safata segons els filtres actuals.').replace('{n}', d.afegits));
      await load();
    } finally {
      setSeleccionant(false);
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-500 max-w-2xl">
        {t('subscriptions.catalog.hint', "Tria quins exemplars concrets poden enviar-se per subscripció (la safata). Marge i antiguitat només filtren aquesta llista per ajudar-te a decidir — l'assignació automàtica només tria entre els discos que aquí marquis.")}
      </p>

      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1.5 text-sm text-zinc-600 bg-white border border-zinc-200 rounded-xl px-3 py-2">
          <input type="checkbox" checked={nomesPool} onChange={e => setNomesPool(e.target.checked)} />
          {t('subscriptions.catalog.pool_only', 'Només la safata')}
        </label>
        <select value={seccioId} onChange={e => setSeccioId(e.target.value)}
          className="border border-zinc-200 rounded-xl px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-zinc-900">
          <option value="">{t('subscriptions.catalog.section_all', 'Cubeta: totes')}</option>
          {seccions.map(s => <option key={s.id} value={s.id}>{s.name_ca}</option>)}
        </select>
        <select value={genere} onChange={e => setGenere(e.target.value)}
          className="border border-zinc-200 rounded-xl px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-zinc-900">
          <option value="">{t('subscriptions.catalog.genre_all', 'Gènere: tots')}</option>
          {generes.map(g => <option key={g} value={g}>{g}</option>)}
        </select>
        <input type="number" placeholder={t('subscriptions.catalog.margin_min_ph', 'Marge mín. %')} value={margeMin} onChange={e => setMargeMin(e.target.value)}
          className="w-28 border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
        <input type="number" placeholder={t('subscriptions.catalog.margin_max_ph', 'Marge màx. %')} value={margeMax} onChange={e => setMargeMax(e.target.value)}
          className="w-28 border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
        <select value={ordre} onChange={e => setOrdre(e.target.value)}
          className="border border-zinc-200 rounded-xl px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-zinc-900">
          <option value="antiguitat">{t('subscriptions.catalog.sort_age', 'Ordenar per antiguitat')}</option>
          <option value="marge">{t('subscriptions.catalog.sort_price', 'Ordenar per preu')}</option>
        </select>
      </div>

      <div className="bg-zinc-50 border border-zinc-200 rounded-xl p-4 flex flex-wrap items-center gap-3">
        <p className="text-sm text-zinc-600 flex-1 min-w-[200px]">
          {t('subscriptions.catalog.auto_select_hint', "Afegeix a la safata, en massa, els discos que compleixin els filtres d'aquí dalt (els més antics primer). Després pots afegir o treure'n individualment.")}
        </p>
        <label className="flex items-center gap-1.5 text-sm text-zinc-600">
          {t('subscriptions.catalog.max', 'Màxim')}
          <input type="number" min="1" value={limitAuto} onChange={e => setLimitAuto(e.target.value)}
            className="w-20 border border-zinc-200 rounded-lg px-2 py-1.5 text-sm" />
        </label>
        <Button size="sm" onClick={seleccionarAutomaticament} disabled={seleccionant}>
          {seleccionant ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          {t('subscriptions.catalog.auto_select', 'Selecciona automàticament')}
        </Button>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading')}</div>
        ) : items.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('subscriptions.catalog.no_records', 'Cap disc disponible amb aquests filtres.')}</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
              <tr>
                <th className="px-4 py-3 text-left font-medium">{t('tpv.col.record')}</th>
                <th className="px-4 py-3 text-left font-medium">{t('common.condition')}</th>
                <th className="px-4 py-3 text-left font-medium">{t('subscriptions.catalog.col.genre', 'Gènere')}</th>
                <th className="px-4 py-3 text-left font-medium">{t('common.price')}</th>
                <th className="px-4 py-3 text-left font-medium">{t('subscriptions.catalog.col.margin_pct', 'Marge %')}</th>
                <th className="px-4 py-3 text-left font-medium">{t('subscriptions.catalog.col.stock_days', 'Dies en estoc')}</th>
                <th className="px-4 py-3 text-center font-medium">{t('subscriptions.catalog.col.in_pool', 'A la safata')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {items.map(it => (
                <tr key={it.item_id} className="hover:bg-zinc-50 transition-colors">
                  <td className="px-4 py-3 text-zinc-900">{it.artista} — {it.titulo}</td>
                  <td className="px-4 py-3">
                    {it.condicion === 'nou' ? (
                      <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium bg-green-100 text-green-800">
                        {t('common.condition.new')} · {it.cantidad - it.cantidad_reservada}/{it.cantidad} {t('purchases.units_free', 'lliures')}
                      </span>
                    ) : (
                      <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-zinc-100 text-zinc-600">
                        {t('purchases.condition.used', 'Segona mà')}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-zinc-500 text-xs">{it.genero || '—'}</td>
                  <td className="px-4 py-3 text-zinc-600">{it.precio} €</td>
                  <td className="px-4 py-3 text-zinc-600">{it.marge_pct ?? '—'}%</td>
                  <td className="px-4 py-3 text-zinc-600">{it.dies_estoc ?? '—'}</td>
                  <td className="px-4 py-3 text-center">
                    <button onClick={() => togglePool(it)}
                      className={`w-8 h-4 rounded-full transition-colors relative ${it.subscripcio_pool ? 'bg-green-500' : 'bg-zinc-300'}`}>
                      <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white shadow transition-all ${it.subscripcio_pool ? 'left-4' : 'left-0.5'}`} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Informes mensuals
// ---------------------------------------------------------------------------

const ANYS_INFORME = [2023, 2024, 2025, 2026];
const NOW_INFORME = new Date();

function InformesPanel() {
  const t = useT();
  const [year, setYear] = useState(NOW_INFORME.getFullYear());
  const [mes, setMes] = useState(NOW_INFORME.getMonth() + 1);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    authFetch(`/admin/subscripcions/informe/${year}/${mes}`).then(r => r.json()).then(d => { setData(d); setLoading(false); });
  }, [year, mes]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <select value={year} onChange={e => setYear(Number(e.target.value))}
          className="border border-zinc-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-zinc-900">
          {ANYS_INFORME.map(y => <option key={y}>{y}</option>)}
        </select>
        <div className="flex flex-wrap gap-1.5">
          {Array.from({ length: 12 }, (_, i) => i + 1).map(n => (
            <button key={n} onClick={() => setMes(n)}
              className={`px-3 py-1 rounded-lg text-sm border transition-colors ${mes === n ? 'bg-zinc-900 text-white border-zinc-900' : 'bg-white text-zinc-600 border-zinc-200 hover:border-zinc-400'}`}>
              {t(`purchases.chart.month.${n - 1}`, '')}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading')}</div>
      ) : !data ? null : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
              <div className="text-xs text-emerald-600 mb-1">{t('subscriptions.report.active_subscribers', 'Subscriptors actius')}</div>
              <div className="text-xl font-bold text-emerald-700">{data.subscriptors_actius}</div>
            </div>
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
              <div className="text-xs text-blue-600 mb-1">{t('subscriptions.report.new_subscriptions', 'Noves subscripcions')}</div>
              <div className="text-xl font-bold text-blue-700">{data.noves_subscripcions}</div>
            </div>
            <div className="bg-red-50 border border-red-200 rounded-xl p-4">
              <div className="text-xs text-red-600 mb-1">{t('subscriptions.report.cancellations', 'Baixes')}</div>
              <div className="text-xl font-bold text-red-700">{data.baixes}</div>
            </div>
            <div className="bg-green-50 border border-green-200 rounded-xl p-4">
              <div className="text-xs text-green-600 mb-1">{t('subscriptions.report.charges_done', 'Cobraments fets')}</div>
              <div className="text-xl font-bold text-green-700">{data.cobraments_ok} · +{parseFloat(data.import_total).toFixed(2)} €</div>
            </div>
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <div className="text-xs text-amber-600 mb-1">{t('subscriptions.report.charges_failed', 'Cobraments fallits')}</div>
              <div className="text-xl font-bold text-amber-700">{data.cobraments_fallits}</div>
            </div>
            <div className="bg-zinc-50 border border-zinc-200 rounded-xl p-4">
              <div className="text-xs text-zinc-500 mb-1">{t('subscriptions.records_sent', 'Discos enviats')}</div>
              <div className="text-xl font-bold text-zinc-800">{data.discos_enviats}</div>
            </div>
          </div>

          {data.cobraments_fallits > 0 && (
            <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-xl px-4 py-2.5">
              {data.cobraments_fallits} {data.cobraments_fallits !== 1
                ? t('subscriptions.report.failed_renewals_plural', 'renovacions fallides')
                : t('subscriptions.report.failed_renewals_singular', 'renovació fallida')}
              {' '}{t('subscriptions.report.failed_renewals_hint', 'aquest mes — revisa el tab "Subscriptors" per si cal contactar el client (targeta caducada, etc.).')}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Configuració general
// ---------------------------------------------------------------------------

const PERIODICITATS_CANDIDATES = [1, 2, 3, 6, 12];
const QUANTITATS_CANDIDATES = [1, 2, 3, 4];

function ConfiguracioPanel() {
  const t = useT();
  const [config, setConfig] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function load() {
    const r = await authFetch('/admin/subscripcions/configuracio');
    setConfig(await r.json());
  }
  useEffect(() => { load(); }, []);

  function toggleList(camp, valor) {
    setConfig(c => {
      const actuals = c[camp] || [];
      const noves = actuals.includes(valor) ? actuals.filter(v => v !== valor) : [...actuals, valor].sort((a, b) => a - b);
      return { ...c, [camp]: noves };
    });
  }

  async function save() {
    setSaving(true);
    setSaved(false);
    try {
      const r = await authFetch('/admin/subscripcions/configuracio', { method: 'PATCH', body: JSON.stringify(config) });
      if (r.ok) { setConfig(await r.json()); setSaved(true); }
    } finally {
      setSaving(false);
    }
  }

  if (!config) return <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading')}</div>;

  return (
    <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6 space-y-5 max-w-lg">
      <div>
        <label className="block text-xs font-medium text-zinc-500 mb-1">{t('subscriptions.config.price_per_record', 'Preu per disc (€)')}</label>
        <input type="number" step="0.01" value={config.preu_per_disc}
          onChange={e => setConfig(c => ({ ...c, preu_per_disc: e.target.value }))}
          className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
        <p className="text-xs text-zinc-400 mt-1">{t('subscriptions.config.price_hint', 'El preu que paga el client és preu per disc × quantitat triada.')}</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-medium text-zinc-500 mb-1">{t('subscriptions.config.margin_min', 'Marge mín. del filtre (%)')}</label>
          <input type="number" step="0.01" value={config.marge_min_pct}
            onChange={e => setConfig(c => ({ ...c, marge_min_pct: e.target.value }))}
            className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
        </div>
        <div>
          <label className="block text-xs font-medium text-zinc-500 mb-1">{t('subscriptions.config.margin_max', 'Marge màx. del filtre (%)')}</label>
          <input type="number" step="0.01" value={config.marge_max_pct}
            onChange={e => setConfig(c => ({ ...c, marge_max_pct: e.target.value }))}
            className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
        </div>
      </div>
      <p className="text-xs text-zinc-400 -mt-3">
        {t('subscriptions.config.margin_hint', 'Valors per defecte del filtre de marge a la pestanya Catàleg — no exclouen res automàticament.')}
      </p>

      <div>
        <label className="block text-xs font-medium text-zinc-500 mb-2">{t('subscriptions.config.periodicities_label', 'Periodicitats que pot triar el client')}</label>
        <div className="flex flex-wrap gap-2">
          {PERIODICITATS_CANDIDATES.map(m => (
            <button key={m} type="button" onClick={() => toggleList('periodicitats_mesos_disponibles', m)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                config.periodicitats_mesos_disponibles.includes(m) ? 'bg-zinc-900 text-white border-transparent' : 'border-zinc-200 text-zinc-600 hover:bg-zinc-50'
              }`}>
              {m === 1 ? t('subscriptions.config.every_month', 'Cada mes') : t('subscriptions.config.every_n_months', 'Cada {n} mesos').replace('{n}', m)}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-zinc-500 mb-2">{t('subscriptions.config.quantities_label', 'Quantitats que pot triar el client')}</label>
        <div className="flex flex-wrap gap-2">
          {QUANTITATS_CANDIDATES.map(q => (
            <button key={q} type="button" onClick={() => toggleList('quantitats_disponibles', q)}
              className={`w-9 h-9 rounded-full text-xs font-medium border transition-colors ${
                config.quantitats_disponibles.includes(q) ? 'bg-zinc-900 text-white border-transparent' : 'border-zinc-200 text-zinc-600 hover:bg-zinc-50'
              }`}>
              {q}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3 pt-1">
        <Button size="sm" onClick={save} disabled={saving}>
          <Check size={14} /> {saving ? t('common.saving') : t('common.save')}
        </Button>
        {saved && !saving && <span className="text-xs text-green-600">{t('subscriptions.config.saved', 'Desat')}</span>}
      </div>
    </div>
  );
}
