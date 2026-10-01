'use client';

// Pestaña Sincronització: carga inicial Discogs -> app (simulación y aplicar) + historial de ejecuciones.
// Primera carga: Discogs manda; después manda la app. Vea docs/PLAN_CANAL_DISCOGS.md §7.

import { useState, useEffect, useCallback } from 'react';
import { authFetch } from '../../../lib/auth';
import { Button } from '../../../../components/ui/button';
import MIcon from '../../../../components/ui/m-icon';
import {
  INV, DAY_MS, RUN_KIND, RUN_STATUS, fmtDate, ProgressPanel, JobError, Results, ErrorBox,
} from './shared';

export default function SyncTab({ t, account, estat, reload, reloadAccount }) {
  const [error, setError] = useState('');
  const [starting, setStarting] = useState(false);
  const [runs, setRuns] = useState([]);
  const [viewRun, setViewRun] = useState(null);

  const job = estat?.job || null;
  const running = !!job && ['queued', 'running'].includes(job.status);
  const isInventory = !!job && ['dry_run', 'apply'].includes(job.mode);

  const loadRuns = useCallback(async () => {
    const r = await authFetch(`${INV}/runs`);
    if (r.ok) setRuns(await r.json());
  }, []);
  // L'historial es refresca en canviar l'estat del treball actual (nou, acabat...).
  useEffect(() => { loadRuns(); }, [loadRuns, job?.id, job?.status]);
  // Quan una execució real acaba, l'estat d'adopció del compte canvia.
  useEffect(() => {
    if (job?.mode === 'apply' && job?.status === 'done') reloadAccount();
  }, [job?.id, job?.status, job?.mode, reloadAccount]);

  async function start(mode, extra = {}) {
    setError('');
    setStarting(true);
    try {
      const r = await authFetch(`${INV}/jobs`, { method: 'POST', body: JSON.stringify({ mode, ...extra }) });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) setError(body.detail || t('discogs.canal.start_error', 'No s\'ha pogut iniciar la sincronització.'));
      else reload();
    } finally {
      setStarting(false);
    }
  }

  const simulacio = estat?.ultima_simulacio;
  const simulacioRecent = !!simulacio && Date.now() - new Date(simulacio.finished_at).getTime() < DAY_MS;
  const adopcioFeta = !!account?.adopcio_feta;

  return (
    <div className="space-y-5">
      <p className="text-sm text-secondary-foreground max-w-3xl">
        {t('discogs.canal.intro', 'Primera càrrega: Discogs mana. Es compara l\'inventari de Discogs amb la botiga i es crea, s\'actualitza el preu o es retira el que calgui. Primer es fa una simulació que no guarda res; revisa-la i només llavors aplica-la. A partir d\'aquí, la font de veritat és l\'app.')}
      </p>
      <ErrorBox>{error}</ErrorBox>

      <StepSimulation
        t={t} running={running} starting={starting} job={isInventory ? job : null} adopcioFeta={adopcioFeta}
        onStart={() => start('dry_run')}
      />

      {isInventory && job.status === 'error' && <JobError t={t} job={job} />}
      {isInventory && running && <ProgressPanel t={t} job={job} />}

      {isInventory && job.status === 'done' && job.mode === 'dry_run' && (
        <>
          <Summary t={t} summary={job.summary} title={t('discogs.canal.sim_result', 'Resultat de la simulació (res s\'ha guardat)')} />
          <Results t={t} jobId={job.id} />
        </>
      )}
      {isInventory && job.status === 'done' && job.mode === 'apply' && (
        <>
          <Summary t={t} summary={job.summary} title={t('discogs.canal.apply_result', 'Sincronització aplicada')} applied />
          <Results t={t} jobId={job.id} />
        </>
      )}

      {!adopcioFeta && simulacioRecent && !running && (
        <ApplyPanel t={t} simulacio={simulacio} starting={starting} onApply={(force) => start('apply', { force })} />
      )}

      <HistoryPanel t={t} runs={runs} viewId={viewRun?.id} onView={setViewRun} />
      {viewRun && (
        <>
          {viewRun.summary && ['inventory_dry_run', 'inventory_apply'].includes(viewRun.kind) && (
            <Summary
              t={t} summary={viewRun.summary} applied={viewRun.kind === 'inventory_apply'}
              title={`${t('discogs.canal.history_report', 'Informe de l\'execució')} · ${fmtDate(viewRun.created_at)}`}
            />
          )}
          <Results t={t} jobId={viewRun.id} />
        </>
      )}
    </div>
  );
}

function StepSimulation({ t, running, starting, job, adopcioFeta, onStart }) {
  return (
    <div className="bg-card rounded-2xl border border-outline-variant shadow-sm p-5 flex items-center justify-between gap-4 flex-wrap">
      <div>
        <p className="text-sm font-semibold text-on-surface">{t('discogs.canal.step1', '1. Simulació')}</p>
        <p className="text-xs text-secondary-foreground mt-1 max-w-xl">
          {adopcioFeta
            ? t('discogs.canal.step1_done_hint', 'La càrrega inicial ja està feta. Pots tornar a simular per veure diferències, però no es pot tornar a aplicar.')
            : t('discogs.canal.step1_hint', 'Descarrega l\'inventari de Discogs i calcula què canviaria, sense modificar res. Pot trigar uns minuts.')}
        </p>
      </div>
      <Button onClick={onStart} disabled={running || starting}>
        <MIcon name={running ? 'progress_activity' : 'search'} size={16} className={running ? 'animate-spin' : ''} />
        {running ? t('discogs.canal.running', 'En marxa…') : job?.mode === 'dry_run' && job.status === 'done'
          ? t('discogs.canal.repeat', 'Tornar a simular')
          : t('discogs.canal.analyze', 'Analitzar Discogs')}
      </Button>
    </div>
  );
}

function Summary({ t, summary, title, applied = false }) {
  if (!summary) return null;
  const tiles = [
    { k: 'creats', label: t('discogs.canal.tile_create', 'A crear'), cls: 'text-green-700' },
    { k: 'sumats', label: t('discogs.canal.tile_sum', 'A sumar a línia nou'), cls: 'text-green-700' },
    { k: 'actualitzats', label: t('discogs.canal.tile_update', 'Preus/dates a actualitzar'), cls: 'text-blue-700' },
    { k: 'retirats', label: t('discogs.canal.tile_retire', 'A retirar'), cls: 'text-amber-700' },
    { k: 'errors', label: t('discogs.canal.tile_errors', 'Errors'), cls: 'text-red-700' },
  ];
  return (
    <div className="bg-card rounded-2xl border border-outline-variant shadow-sm p-5 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <p className="text-sm font-semibold text-on-surface">{title}</p>
        <p className="text-xs text-secondary-foreground">
          {summary.listings} {t('discogs.canal.listings_found', 'listings a Discogs')} · {summary.compte_discogs}
        </p>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {tiles.map(({ k, label, cls }) => (
          <div key={k} className="rounded-xl bg-surface-container-high px-4 py-3">
            <p className={`text-2xl font-bold ${cls}`}>{summary[k]}</p>
            <p className="text-xs text-secondary-foreground mt-1">{label}</p>
          </div>
        ))}
      </div>
      {summary.avisos?.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 rounded-xl px-4 py-3 text-sm space-y-1">
          {summary.avisos.map((a, i) => <p key={i}>⚠ {a}</p>)}
        </div>
      )}
      {applied && summary.adopcio_marcada && (
        <p className="text-sm text-green-700">{t('discogs.canal.adoption_marked', 'Càrrega inicial marcada com a feta: a partir d\'ara l\'app és la font de veritat.')}</p>
      )}
    </div>
  );
}

function ApplyPanel({ t, simulacio, starting, onApply }) {
  const s = simulacio.summary || {};
  const needsForce = (s.avisos || []).length > 0;
  const [backup, setBackup] = useState(false);
  const [force, setForce] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const ready = backup && (!needsForce || force);

  return (
    <div className="bg-card rounded-2xl border border-red-200 shadow-sm p-5 space-y-4">
      <div>
        <p className="text-sm font-semibold text-on-surface">{t('discogs.canal.step2', '2. Aplicar a la botiga')}</p>
        <p className="text-xs text-secondary-foreground mt-1 max-w-2xl">
          {t('discogs.canal.step2_hint', 'Executa de veritat el que ha mostrat l\'última simulació: modifica la base de dades de la botiga. No escriu res a Discogs. Només es pot fer una vegada: després l\'app és la font de veritat.')}
        </p>
      </div>
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" checked={backup} onChange={(e) => setBackup(e.target.checked)} className="mt-0.5" />
        <span>{t('discogs.canal.backup_check', 'He fet una còpia de seguretat de l\'inventari de Discogs i de la base de dades.')}</span>
      </label>
      {needsForce && (
        <label className="flex items-start gap-2 text-sm text-amber-800">
          <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} className="mt-0.5" />
          <span>{t('discogs.canal.force_check', 'Entenc els avisos de la simulació i vull continuar igualment.')}</span>
        </label>
      )}
      {!confirming ? (
        <Button disabled={!ready || starting} onClick={() => setConfirming(true)}>
          <MIcon name="sync" size={16} /> {t('discogs.canal.apply', 'Aplicar sincronització')}
        </Button>
      ) : (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 space-y-3">
          <p className="text-sm text-red-800">
            {t('discogs.canal.confirm_text', 'Es crearan {c}, se sumaran {s}, s\'actualitzaran {u} i es retiraran {r} ítems.')
              .replace('{c}', s.creats ?? 0).replace('{s}', s.sumats ?? 0)
              .replace('{u}', s.actualitzats ?? 0).replace('{r}', s.retirats ?? 0)}
          </p>
          <div className="flex gap-2">
            <Button disabled={starting} onClick={() => onApply(force)}>
              {t('discogs.canal.confirm_apply', 'Sí, aplica-ho')}
            </Button>
            <Button variant="secondary" onClick={() => setConfirming(false)}>{t('common.cancel', 'Cancel·la')}</Button>
          </div>
        </div>
      )}
    </div>
  );
}

function runSummary(s) {
  if (s.mode === 'reconcile') return `${s.publicats} publicats · ${s.actualitzats} preus · ${s.retirats} retirats · ${s.errors} errors`;
  if (s.mode === 'audit') return `${s.orfes} orfes · ${s.no_a_discogs} ja no hi són · ${s.preus} de preu`;
  if (s.mode === 'pricing_preview') return `${s.puja} pugen · ${s.baixa} baixen · ${s.igual} igual · ${s.sense_suggeriment} sense suggeriment`;
  return `${s.creats} creats · ${s.sumats} sumats · ${s.actualitzats} actualitzats · ${s.retirats} retirats · ${s.errors} errors`;
}

function HistoryPanel({ t, runs, viewId, onView }) {
  if (!runs || runs.length === 0) return null;
  return (
    <div className="bg-card rounded-2xl border border-outline-variant shadow-sm overflow-hidden">
      <p className="px-5 pt-4 pb-2 text-sm font-semibold text-on-surface">{t('discogs.canal.history', 'Historial')}</p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-xs text-secondary-foreground border-b border-outline-variant">
            <tr>
              <th className="px-5 py-2 text-left font-medium">{t('discogs.canal.col_date', 'Data')}</th>
              <th className="px-3 py-2 text-left font-medium">{t('discogs.canal.col_type', 'Tipus')}</th>
              <th className="px-3 py-2 text-left font-medium">{t('discogs.canal.col_status', 'Estat')}</th>
              <th className="px-3 py-2 text-left font-medium">{t('discogs.canal.col_result', 'Resultat')}</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => {
              const st = RUN_STATUS[r.status] || RUN_STATUS.queued;
              const s = r.summary;
              return (
                <tr key={r.id} className="border-b border-outline-variant last:border-0">
                  <td className="px-5 py-2 text-secondary-foreground">{fmtDate(r.created_at)}</td>
                  <td className="px-3 py-2">{RUN_KIND[r.kind] || r.kind}</td>
                  <td className="px-3 py-2">
                    <span className={`inline-block text-xs font-medium px-2 py-0.5 rounded-full ${st.cls}`}>{st.label}</span>
                  </td>
                  <td className="px-3 py-2 text-xs text-secondary-foreground">
                    {r.error
                      ? r.error
                      : s ? runSummary(s) : '—'}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {r.status === 'done' && r.rows_count > 0 && (
                      <Button variant="secondary" size="sm" onClick={() => onView(viewId === r.id ? null : r)}>
                        {viewId === r.id ? t('discogs.canal.hide', 'Amaga') : t('discogs.canal.view_report', 'Veure informe')}
                      </Button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

