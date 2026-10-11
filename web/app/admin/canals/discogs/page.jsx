'use client';

// Centro de control de ventas online en Discogs (Catàleg › Sync Discogs). Una pantalla con pestañas:
// Resum, Listings, Sincronització (carga inicial), Comandes, Preus, Alertes y Configuració.
// Todo se sirve desde la caché local; Discogs solo se consulta al sincronizar o al actuar.
// Los pedidos de Discogs siguen siendo los mismos de "Vendes web". Ver docs/PLAN_CANAL_DISCOGS.md.

import { Suspense, useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useT } from '../../../lib/i18n';
import MIcon from '../../../../components/ui/m-icon';
import { CH, INV, PHASES, api } from './shared';
import ResumTab from './ResumTab';
import ListingsTab from './ListingsTab';
import SyncTab from './SyncTab';
import VincularTab from './VincularTab';
import ProvaTab from './ProvaTab';
import OrdersTab from './OrdersTab';
import PricesTab from './PricesTab';
import AlertsTab from './AlertsTab';
import SettingsTab from './SettingsTab';

const TABS = [
  { key: 'resum', label: 'Resum', icon: 'space_dashboard' },
  { key: 'listings', label: 'Listings', icon: 'list_alt' },
  { key: 'vincular', label: 'Vincular', icon: 'link' },
  { key: 'sync', label: 'Sincronització', icon: 'sync' },
  { key: 'comandes', label: 'Comandes', icon: 'shopping_bag' },
  { key: 'preus', label: 'Preus', icon: 'price_change' },
  { key: 'alertes', label: 'Alertes', icon: 'notifications' },
  { key: 'config', label: 'Configuració', icon: 'settings' },
  { key: 'prova', label: 'Prova API', icon: 'science' },
];
// Pestaña que ya muestra el progreso de cada tipo de trabajo (el aviso global no se repite allí)
const TAB_OF_MODE = {
  dry_run: 'sync', apply: 'sync', reconcile: 'listings', pricing_preview: 'preus', audit: 'alertes', discogs_backup: 'config',
};
const MODE_LABEL = {
  dry_run: 'Simulació de càrrega', apply: 'Càrrega inicial', reconcile: 'Reconciliació amb Discogs',
  pricing_preview: 'Simulació de preus', audit: 'Auditoria', discogs_backup: 'Còpia de Discogs',
};

function AccountCard({ t, account }) {
  if (!account) return null;
  return (
    <div className="bg-card rounded-2xl border border-outline-variant shadow-sm p-5 flex flex-wrap items-center gap-x-8 gap-y-3">
      <div>
        <p className="text-xs text-secondary-foreground">{t('discogs.canal.account', 'Compte de Discogs')}</p>
        {!account.configured ? (
          <p className="text-sm font-medium text-red-600">{t('discogs.canal.no_token', 'Sense token configurat')}</p>
        ) : account.username ? (
          <p className="text-sm font-medium text-on-surface">{account.username}</p>
        ) : (
          <p className="text-sm font-medium text-red-600">{account.error}</p>
        )}
      </div>
      <div>
        <p className="text-xs text-secondary-foreground">{t('discogs.canal.mode', 'Mode')}</p>
        <span className={`inline-block text-xs font-medium px-2 py-0.5 rounded-full ${account.solo_lectura ? 'bg-amber-100 text-amber-800' : 'bg-green-100 text-green-800'}`}>
          {account.solo_lectura ? t('discogs.canal.read_only', 'Només lectura') : t('discogs.canal.read_write', 'Lectura i escriptura')}
        </span>
      </div>
      <div>
        <p className="text-xs text-secondary-foreground">{t('discogs.canal.adoption', 'Càrrega inicial')}</p>
        <span className={`inline-block text-xs font-medium px-2 py-0.5 rounded-full ${account.adopcio_feta ? 'bg-green-100 text-green-800' : 'bg-surface-container-high text-secondary-foreground'}`}>
          {account.adopcio_feta ? t('discogs.canal.adoption_done', 'Feta') : t('discogs.canal.adoption_pending', 'Pendent')}
        </span>
      </div>
      <p className="text-xs text-secondary-foreground max-w-md">
        {t('discogs.canal.read_only_note', 'Aquesta pantalla només baixa dades de Discogs: el mode només lectura no l\'afecta.')}{' '}
        <Link href="/admin/configuracio" className="text-primary underline">{t('discogs.canal.go_config', 'Canviar a Configuració')}</Link>
      </p>
    </div>
  );
}


function JobBanner({ job, onGo }) {
  const pct = job.total > 0 ? Math.min(100, Math.round((job.done / job.total) * 100)) : null;
  return (
    <button type="button" onClick={onGo} className="w-full text-left bg-blue-50 border border-blue-200 text-blue-900 rounded-xl px-4 py-2 text-sm flex items-center gap-3">
      <MIcon name="progress_activity" size={16} className="animate-spin" />
      <span className="font-medium">{MODE_LABEL[job.mode] || job.mode}</span>
      <span className="text-blue-800/80">{PHASES[job.phase] || 'A la cua…'}{job.total > 0 ? ` (${job.done}/${job.total})` : ''}</span>
      {pct !== null && <span className="ml-auto">{pct}%</span>}
    </button>
  );
}

function CentreDiscogs() {
  const t = useT();
  const router = useRouter();
  const params = useSearchParams();
  const tab = TABS.some((x) => x.key === params.get('tab')) ? params.get('tab') : 'resum';

  const [account, setAccount] = useState(null);
  const [estat, setEstat] = useState(null);
  const [alertCount, setAlertCount] = useState(0);
  const [presets, setPresets] = useState({});

  const loadAccount = useCallback(async () => {
    const r = await api('/admin/secrets/discogs-account');
    if (r.ok) setAccount(r.data);
  }, []);
  const loadEstat = useCallback(async () => {
    const r = await api(`${INV}/jobs/current`);
    if (r.ok) setEstat(r.data);
    else if (r.status === 404) setEstat({ disabled: true });
  }, []);
  const loadAlerts = useCallback(async () => {
    const r = await api(`${CH}/alerts?status=open&limit=1`);
    if (r.ok) setAlertCount(Object.values(r.data.open || {}).reduce((a, b) => a + b, 0));
  }, []);

  useEffect(() => { loadAccount(); loadEstat(); loadAlerts(); }, [loadAccount, loadEstat, loadAlerts]);

  const job = estat?.job || null;
  const running = !!job && ['queued', 'running'].includes(job.status);
  useEffect(() => {
    if (!running) return undefined;
    const id = setInterval(loadEstat, 2000);
    return () => clearInterval(id);
  }, [running, loadEstat]);
  // Al acabar un trabajo pueden cambiar las alertas, el modo/adopción y los datos de las pestañas.
  useEffect(() => { loadAlerts(); }, [job?.id, job?.status, loadAlerts]);

  function goTab(key, preset) {
    if (preset) setPresets(preset);
    router.replace(`?tab=${key}`, { scroll: false });
  }

  if (estat === null) return <div className="p-12 text-center text-secondary-foreground text-sm">{t('common.loading')}</div>;
  if (estat.disabled) {
    return (
      <div className="max-w-3xl mx-auto bg-card rounded-2xl border border-outline-variant p-6 text-sm text-secondary-foreground">
        {t('discogs.canal.disabled', 'La sincronització amb Discogs està desactivada.')}{' '}
        <Link href="/admin/configuracio" className="text-primary underline">{t('nav.configuracio', 'Configuració')}</Link>
      </div>
    );
  }

  const common = { t, account, estat, reload: loadEstat, reloadAccount: loadAccount, goTab };
  return (
    <div className="space-y-5 max-w-6xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold text-on-surface">{t('discogs.canal.title', 'Discogs · centre de control')}</h2>
        <p className="text-sm text-secondary-foreground mt-1 max-w-3xl">
          {t('discogs.canal.subtitle', 'Estat, accions i sincronització del que vens a Discogs. La font de veritat d\'estoc i preus és l\'app; les comandes de Discogs també apareixen a Vendes web.')}
        </p>
      </div>

      <AccountCard t={t} account={account} />
      {running && TAB_OF_MODE[job.mode] !== tab && <JobBanner job={job} onGo={() => goTab(TAB_OF_MODE[job.mode] || 'sync')} />}

      <div className="flex gap-1 bg-surface-container-high p-1 rounded-xl w-fit flex-wrap">
        {TABS.map((x) => (
          <button key={x.key} type="button" onClick={() => goTab(x.key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${tab === x.key ? 'bg-card text-on-surface shadow-sm font-medium' : 'text-secondary-foreground hover:text-on-surface'}`}>
            <MIcon name={x.icon} size={15} />
            {t(`discogs.tab.${x.key}`, x.label)}
            {x.key === 'alertes' && alertCount > 0 && (
              <span className="ml-1 bg-red-600 text-white text-[10px] leading-none rounded-full px-1.5 py-0.5">{alertCount}</span>
            )}
          </button>
        ))}
      </div>

      {tab === 'resum' && <ResumTab {...common} />}
      {tab === 'listings' && <ListingsTab key={JSON.stringify(presets)} {...common} initial={presets} />}
      {tab === 'vincular' && <VincularTab {...common} />}
      {tab === 'sync' && <SyncTab {...common} />}
      {tab === 'comandes' && <OrdersTab {...common} />}
      {tab === 'preus' && <PricesTab {...common} />}
      {tab === 'alertes' && <AlertsTab {...common} />}
      {tab === 'config' && <SettingsTab {...common} />}
      {tab === 'prova' && <ProvaTab {...common} />}
    </div>
  );
}

export default function DiscogsCanalPage() {
  // useSearchParams exige un límite de Suspense en Next.js.
  return (
    <Suspense fallback={<div className="p-12 text-center text-secondary-foreground text-sm">…</div>}>
      <CentreDiscogs />
    </Suspense>
  );
}
