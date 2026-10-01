'use client';

// Pestaña Resum: KPIs del canal (desde la caché local: no gasta llamadas de Discogs) y actividad reciente.

import { useState, useEffect } from 'react';
import { authFetch } from '../../../lib/auth';
import { Badge, CH, Panel, RUN_KIND, fmtDate, fmtPrice } from './shared';

function Tile({ label, value, cls = 'text-on-surface', onClick, hint }) {
  const body = (
    <>
      <p className={`text-2xl font-bold ${cls}`}>{value}</p>
      <p className="text-xs text-secondary-foreground mt-1">{label}</p>
      {hint && <p className="text-[11px] text-secondary-foreground/70 mt-0.5">{hint}</p>}
    </>
  );
  return onClick ? (
    <button type="button" onClick={onClick} className="text-left rounded-xl bg-surface-container-high px-4 py-3 hover:bg-surface-container-highest transition-colors">{body}</button>
  ) : (
    <div className="rounded-xl bg-surface-container-high px-4 py-3">{body}</div>
  );
}

export default function ResumTab({ t, estat, goTab }) {
  const [data, setData] = useState(null);
  const [events, setEvents] = useState([]);
  const job = estat?.job;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [o, e] = await Promise.all([authFetch(`${CH}/overview`), authFetch(`${CH}/events?limit=8`)]);
      if (cancelled) return;
      if (o.ok) setData(await o.json());
      if (e.ok) setEvents((await e.json()).events);
    })();
    return () => { cancelled = true; };
  }, [job?.id, job?.status]);

  if (!data) return <div className="p-10 text-center text-sm text-secondary-foreground">{t('common.loading')}</div>;

  const a = data.accions || {};
  const e = data.estat_canal || {};
  const alertes = Object.values(data.alertes_obertes || {}).reduce((x, y) => x + y, 0);
  const s = data.settings || {};
  const ordres = s.orders_last_result;

  return (
    <div className="space-y-5">
      <Panel title={t('discogs.resum.state', 'Estat del canal')}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Tile label={t('discogs.resum.on_sale', 'Items a la venda')} value={data.items_a_la_venda} onClick={() => goTab('listings')} />
          <Tile label={t('discogs.resum.published', 'Publicats a Discogs')} value={e.publicat || 0} cls="text-green-700" onClick={() => goTab('listings', { estat: 'publicat' })} />
          <Tile label={t('discogs.resum.value', 'Valor publicat')} value={fmtPrice(data.valor_publicat)} />
          <Tile label={t('discogs.resum.open_orders', 'Comandes de Discogs obertes')} value={data.comandes_obertes} cls={data.comandes_obertes ? 'text-blue-700' : undefined} onClick={() => goTab('comandes')} />
        </div>
      </Panel>

      <Panel title={t('discogs.resum.todo', 'Pendent de fer')}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Tile label={t('discogs.resum.to_publish', 'Per publicar')} value={a.publicar || 0} cls={a.publicar ? 'text-green-700' : undefined} onClick={() => goTab('listings', { accio: 'publicar' })} />
          <Tile label={t('discogs.resum.to_update', 'Preus a actualitzar')} value={a.actualitzar_preu || 0} cls={a.actualitzar_preu ? 'text-blue-700' : undefined} onClick={() => goTab('listings', { accio: 'actualitzar_preu' })} />
          <Tile label={t('discogs.resum.to_retire', 'Per retirar')} value={a.retirar || 0} cls={a.retirar ? 'text-amber-700' : undefined} onClick={() => goTab('listings', { accio: 'retirar' })}
            hint={a.retirar ? t('discogs.resum.retire_hint', 'ja no són a la venda a l\'app') : undefined} />
          <Tile label={t('discogs.resum.to_link', 'Sense release vinculat')} value={a.vincular_release || 0} onClick={() => goTab('listings', { accio: 'vincular_release' })} />
        </div>
      </Panel>

      <Panel title={t('discogs.resum.attention', 'Atenció')}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Tile label={t('discogs.resum.alerts', 'Alertes obertes')} value={alertes} cls={alertes ? 'text-red-700' : undefined} onClick={() => goTab('alertes')} />
          <Tile label={t('discogs.resum.errors24', 'Errors darreres 24 h')} value={data.errors_24h} cls={data.errors_24h ? 'text-red-700' : undefined} />
          <Tile
            label={t('discogs.resum.orders_pull', 'Última consulta de comandes')}
            value={s.orders_last_pull_at ? fmtDate(s.orders_last_pull_at) : '—'}
            hint={ordres?.error ? ordres.error : ordres ? `${ordres.creats ?? 0} noves · ${ordres.sense_match ?? 0} sense coincidència` : undefined}
            onClick={() => goTab('comandes')}
          />
          <Tile
            label={t('discogs.resum.last_run', 'Última execució')}
            value={data.ultima_execucio ? (RUN_KIND[data.ultima_execucio.kind] || data.ultima_execucio.kind) : '—'}
            hint={data.ultima_execucio ? `${fmtDate(data.ultima_execucio.finished_at)} · ${data.ultima_execucio.status}` : undefined}
            onClick={() => goTab('sync')}
          />
        </div>
      </Panel>

      <Panel title={t('discogs.resum.activity', 'Activitat recent')}>
        {events.length === 0 ? (
          <p className="text-sm text-secondary-foreground">{t('discogs.resum.no_activity', 'Encara no hi ha activitat registrada.')}</p>
        ) : (
          <ul className="divide-y divide-outline-variant text-sm">
            {events.map((ev) => (
              <li key={ev.id} className="py-2 flex items-center gap-3 flex-wrap">
                <span className="text-xs text-secondary-foreground w-32 shrink-0">{fmtDate(ev.created_at)}</span>
                <Badge cls={ev.outcome === 'ok' ? 'bg-green-100 text-green-800' : ev.outcome === 'error' ? 'bg-red-100 text-red-800' : undefined}>{ev.outcome}</Badge>
                <span className="font-medium text-on-surface">{ev.action}</span>
                {ev.external_id && <span className="text-secondary-foreground">#{ev.external_id}</span>}
                <span className="text-xs text-secondary-foreground">{ev.actor}</span>
                {(ev.error || ev.detail?.motiu) && <span className="text-xs text-secondary-foreground truncate max-w-md">{ev.error || ev.detail.motiu}</span>}
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
