'use client';

// Pestaña Configuració del canal: publicación manual/automática, retirada y consulta de pedidos programadas,
// recargo, y los AVISOS por correo que cada usuario quiere recibir (por defecto, ninguno).

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { Badge, CH, ErrorBox, Panel, api } from './shared';

function Toggle({ on, onChange, disabled }) {
  return (
    <button type="button" disabled={disabled} onClick={() => onChange(!on)}
      className={`w-10 h-5 rounded-full transition-colors relative shrink-0 ${on ? 'bg-green-500' : 'bg-muted'} ${disabled ? 'opacity-50' : ''}`}>
      <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-card shadow transition-all ${on ? 'left-5' : 'left-0.5'}`} />
    </button>
  );
}

function Row({ title, hint, children }) {
  return (
    <div className="flex items-start justify-between gap-6 py-3 border-b border-outline-variant last:border-0">
      <div>
        <p className="text-sm font-medium text-on-surface-variant">{title}</p>
        {hint && <p className="text-xs text-secondary-foreground mt-1 max-w-xl">{hint}</p>}
      </div>
      {children}
    </div>
  );
}

export default function SettingsTab({ t, account }) {
  const [s, setS] = useState(null);
  const [notif, setNotif] = useState(null);
  const [recargo, setRecargo] = useState('');
  const [error, setError] = useState('');
  const [saved, setSaved] = useState('');

  const load = useCallback(async () => {
    const [a, b] = await Promise.all([api(`${CH}/settings`), api(`${CH}/notifications`)]);
    if (a.ok) { setS(a.data); setRecargo(String(a.data.recargo_pct)); }
    if (b.ok) setNotif(b.data.events);
  }, []);
  useEffect(() => { load(); }, [load]);

  async function save(patch) {
    setError('');
    const r = await api(`${CH}/settings`, { method: 'PUT', body: patch });
    if (!r.ok) { setError(Array.isArray(r.data.detail) ? 'Valor no vàlid' : (r.data.detail || 'No s\'ha pogut desar.')); return; }
    setS(r.data);
    setRecargo(String(r.data.recargo_pct));
    setSaved(t('discogs.settings.saved', 'Desat'));
    setTimeout(() => setSaved(''), 1500);
  }

  async function savePref(key, enabled) {
    const r = await api(`${CH}/notifications`, { method: 'PUT', body: { prefs: { [key]: enabled } } });
    if (r.ok) setNotif(r.data.events);
  }

  if (!s) return <div className="p-10 text-center text-sm text-secondary-foreground">{t('common.loading')}</div>;

  return (
    <div className="space-y-5 max-w-3xl">
      <ErrorBox>{error}</ErrorBox>
      {saved && <p className="text-xs text-green-700">{saved}</p>}

      <Panel title={t('discogs.settings.mode', 'Mode del canal')}>
        <div className="flex items-center gap-3 text-sm">
          <Badge cls={account?.solo_lectura ? 'bg-amber-100 text-amber-800' : 'bg-green-100 text-green-800'}>
            {account?.solo_lectura ? t('discogs.canal.read_only', 'Només lectura') : t('discogs.canal.read_write', 'Lectura i escriptura')}
          </Badge>
          <span className="text-secondary-foreground text-xs">
            {t('discogs.settings.mode_hint', 'El mode i els tokens es canvien a')}{' '}
            <Link href="/admin/configuracio" className="text-primary underline">{t('nav.configuracio', 'Configuració')}</Link>.
          </span>
        </div>
      </Panel>

      <Panel title={t('discogs.settings.automation', 'Automatització')}>
        <Row title={t('discogs.settings.auto_publish', 'Publicar automàticament')}
          hint={t('discogs.settings.auto_publish_hint', 'Apagat (recomanat al principi): els discos nous queden «pendents» a Listings fins que els aprovis. Reposar un listing que ja es va publicar (p. ex. després d\'una venda a Discogs) sempre és automàtic.')}>
          <Toggle on={s.publicacion_auto} onChange={(v) => save({ publicacion_auto: v })} />
        </Row>
        <Row title={t('discogs.settings.auto_retire', 'Retirar automàticament el que ja no es ven')}
          hint={t('discogs.settings.auto_retire_hint', 'Cada 15 min es treuen de Discogs els discos que ja no són a la venda a l\'app (venuts a botiga o a la web, retirats). Amb la publicació automàtica activada, també publica i actualitza preus. Només actua amb mode lectura i escriptura.')}>
          <Toggle on={s.sync_auto} onChange={(v) => save({ sync_auto: v })} />
        </Row>
        <Row title={t('discogs.settings.auto_orders', 'Consultar comandes automàticament')}
          hint={t('discogs.settings.auto_orders_hint', 'Baixa les comandes noves o modificades de Discogs. Funciona també en mode només lectura. Comença un cop feta la càrrega inicial.')}>
          <div className="flex items-center gap-3">
            <select value={s.orders_poll_minutes} onChange={(e) => save({ orders_poll_minutes: Number(e.target.value) })}
              className="border border-outline-variant rounded-xl px-2 py-1 text-sm bg-card">
              {[5, 10, 15, 30, 60, 120].map((m) => <option key={m} value={m}>{m} min</option>)}
            </select>
            <Toggle on={s.orders_auto} onChange={(v) => save({ orders_auto: v })} />
          </div>
        </Row>
        <Row title={t('discogs.settings.markup', 'Recàrrec sobre el preu de la web (%)')}
          hint={t('discogs.settings.markup_hint', '0 = mateix preu que a la web. Si poses un recàrrec, el preu publicat a Discogs serà el de l\'app més aquest percentatge.')}>
          <div className="flex items-center gap-2">
            <input value={recargo} onChange={(e) => setRecargo(e.target.value)} inputMode="decimal"
              className="w-20 border border-outline-variant rounded-xl px-2 py-1 text-sm bg-card text-right" />
            <button type="button" className="text-xs text-primary hover:underline" onClick={() => save({ recargo_pct: Number(recargo) })}>{t('discogs.settings.save', 'Desa')}</button>
          </div>
        </Row>
      </Panel>

      <Panel title={t('discogs.settings.notifications', 'Els meus avisos per correu')}>
        <p className="text-xs text-secondary-foreground max-w-xl">
          {t('discogs.settings.notifications_hint', 'Tria què vols rebre. Per defecte, res: tot el que passa es veu igualment a Alertes. Cada usuari administrador tria els seus.')}
        </p>
        {(notif || []).map((e) => (
          <Row key={e.key} title={e.label}><Toggle on={e.enabled} onChange={(v) => savePref(e.key, v)} /></Row>
        ))}
      </Panel>
    </div>
  );
}
