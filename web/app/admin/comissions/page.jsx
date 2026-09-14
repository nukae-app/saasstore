'use client';

import { useState, useEffect, useMemo } from 'react';
import { authFetch } from '../../lib/auth';
import { Button } from '../../../components/ui/button';
import MIcon from '../../../components/ui/m-icon';
import { useT } from '../../lib/i18n';

export default function ComissionsPage() {
  const t = useT();

  const CANALS = useMemo(() => [
    { value: 'web_targeta', label: t('comissions.canal.web', 'Web (Redsys)'), hint: t('comissions.canal.web_hint', 'Checkout amb targeta — es tanca automàticament en confirmar-se el pagament.') },
    { value: 'mostrador_targeta', label: t('comissions.canal.mostrador', 'Mostrador (TPV)'), hint: t('comissions.canal.mostrador_hint', "Datàfon del TPV — es tanca via caixa diària.") },
    { value: 'club_targeta', label: t('comissions.canal.club', 'Club del disc'), hint: t('comissions.canal.club_hint', 'Cobrament recurrent Redsys (COF/MIT).') },
  ], [t]);

  const MODES = useMemo(() => ({
    deduccio: { label: t('comissions.mode.deduccio', 'Deducció (net)'), hint: t('comissions.mode.deduccio_hint', "El banc ingressa l'import ja net de comissió.") },
    cobrament_apart: { label: t('comissions.mode.cobrament_apart', 'Cobrament a part (brut)'), hint: t('comissions.mode.cobrament_apart_hint', "El banc ingressa l'import íntegre; la comissió es factura a part com una despesa.") },
  }), [t]);

  const [comissions, setComissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editCanal, setEditCanal] = useState(null);

  async function load() {
    setLoading(true);
    const r = await authFetch('/admin/comissions-pagament');
    setComissions(await r.json());
    setLoading(false);
  }
  useEffect(() => { load(); }, []);

  async function eliminar(comissio) {
    if (!confirm(t('comissions.confirm_delete', 'Eliminar aquesta configuració de comissió?'))) return;
    await authFetch(`/admin/comissions-pagament/${comissio.id}`, { method: 'DELETE' });
    load();
  }

  return (
    <div className="space-y-5 max-w-4xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold text-on-surface">{t('comissions.title', 'Comissions bancàries')}</h2>
        <p className="text-sm text-secondary-foreground mt-1">
          {t('comissions.subtitle', "Configura, per canal de cobrament amb targeta, si i com es reconeix la comissió del banc (compte 626) en tancar el cobrament.")}
        </p>
      </div>

      {loading ? (
        <div className="p-12 text-center text-secondary-foreground text-sm">{t('common.loading', 'Carregant...')}</div>
      ) : (
        <div className="grid gap-3">
          {CANALS.map(canal => {
            const config = comissions.find(c => c.canal === canal.value);
            return (
              <div key={canal.value} className="bg-card rounded-2xl border border-outline-variant shadow-sm p-5 flex items-center justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-on-surface">{canal.label}</div>
                  <div className="text-xs text-secondary-foreground mt-0.5">{canal.hint}</div>
                  {config ? (
                    <div className="mt-2 flex items-center gap-3 flex-wrap text-sm">
                      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${config.active ? 'bg-green-100 text-green-700' : 'bg-surface-container-high text-secondary-foreground'}`}>
                        {config.active ? t('purchases.supplier.active', 'Actiu') : t('purchases.supplier.inactive', 'Inactiu')}
                      </span>
                      <span className="text-on-surface-variant">{MODES[config.mode]?.label || config.mode}</span>
                      <span className="font-mono text-xs text-secondary-foreground">
                        {parseFloat(config.pct).toFixed(2)}% + {parseFloat(config.fixed_fee).toFixed(2)} €
                      </span>
                    </div>
                  ) : (
                    <div className="mt-2 text-xs text-secondary-foreground italic">{t('comissions.not_configured', 'Sense comissió configurada')}</div>
                  )}
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <Button size="sm" variant="secondary" onClick={() => setEditCanal({ canal: canal.value, config })}>
                    {config ? t('catalog.edit', 'Editar') : t('comissions.configure', 'Configurar')}
                  </Button>
                  {config && (
                    <button onClick={() => eliminar(config)} className="text-secondary-foreground hover:text-red-600 p-1.5 rounded hover:bg-red-50 transition-colors">
                      <MIcon name="delete" size={15} />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {editCanal && (
        <ComissioModal
          canal={editCanal.canal}
          config={editCanal.config}
          canalLabel={CANALS.find(c => c.value === editCanal.canal)?.label}
          modes={MODES}
          onClose={() => setEditCanal(null)}
          onSaved={() => { setEditCanal(null); load(); }}
        />
      )}
    </div>
  );
}

function ComissioModal({ canal, config, canalLabel, modes, onClose, onSaved }) {
  const t = useT();
  const isEdit = !!config;
  const [mode, setMode] = useState(config?.mode || 'deduccio');
  const [pct, setPct] = useState(config?.pct ?? '0.00');
  const [fixedFee, setFixedFee] = useState(config?.fixed_fee ?? '0.00');
  const [active, setActive] = useState(config?.active ?? true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    const payload = { canal, mode, pct: parseFloat(pct), fixed_fee: parseFloat(fixedFee), active };
    const url = isEdit ? `/admin/comissions-pagament/${config.id}` : '/admin/comissions-pagament';
    const method = isEdit ? 'PATCH' : 'POST';
    const r = await authFetch(url, { method, body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json()).detail || t('common.error_saving', 'Error desant'));
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-card rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-outline-variant">
          <h3 className="text-lg font-bold text-on-surface">{canalLabel}</h3>
          <button onClick={onClose} className="text-secondary-foreground hover:text-on-surface-variant p-1 rounded-lg hover:bg-surface-container-high"><MIcon name="close" size={20} /></button>
        </div>
        <form onSubmit={save} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-on-surface-variant mb-1">{t('comissions.mode_label', 'Mode de liquidació')}</label>
            <div className="space-y-2">
              {Object.entries(modes).map(([value, m]) => (
                <label key={value} className={`flex items-start gap-2 border rounded-xl p-3 cursor-pointer transition-colors ${mode === value ? 'border-primary bg-primary/5' : 'border-outline-variant'}`}>
                  <input type="radio" name="mode" value={value} checked={mode === value} onChange={() => setMode(value)} className="mt-0.5" />
                  <span>
                    <span className="block text-sm font-medium text-on-surface">{m.label}</span>
                    <span className="block text-xs text-secondary-foreground">{m.hint}</span>
                  </span>
                </label>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1">{t('comissions.pct', 'Percentatge')} (%)</label>
              <input type="number" step="0.01" min="0" value={pct} onChange={e => setPct(e.target.value)}
                className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
            </div>
            <div>
              <label className="block text-sm font-medium text-on-surface-variant mb-1">{t('comissions.fixed_fee', 'Fixa per operació')} (€)</label>
              <input type="number" step="0.01" min="0" value={fixedFee} onChange={e => setFixedFee(e.target.value)}
                className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm text-on-surface-variant">
            <input type="checkbox" checked={active} onChange={e => setActive(e.target.checked)} />
            {t('purchases.supplier.active', 'Actiu')}
          </label>
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel', "Cancel·lar")}</Button>
            <Button type="submit" disabled={saving}>{saving ? t('common.saving', 'Desant...') : t('config.save_changes', 'Desar canvis')}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}
