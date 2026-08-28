'use client';

import { useState, useEffect } from 'react';
import { authFetch } from '../../lib/auth';
import { useT } from '../../lib/i18n';
import { Plus, Star, Trash2, Pencil } from 'lucide-react';
import { Button } from '../../../components/ui/button';

export default function ConfiguracioPage() {
  const t = useT();
  const [tab, setTab] = useState('fiscals'); // fiscals | contacte | disseny | css | iva | marges | cubetes | enviaments | secrets
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);

  async function loadConfig() {
    setLoading(true);
    const r = await authFetch('/admin/configuracio');
    setConfig(await r.json());
    setLoading(false);
  }
  useEffect(() => { loadConfig(); }, []);

  return (
    <div className="space-y-5 max-w-4xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-zinc-900">{t('config.title', 'Configuració')}</h2>
      </div>

      <div className="flex gap-1 bg-zinc-100 p-1 rounded-xl w-fit">
        {[
          ['fiscals', t('config.tab.fiscal', 'Dades fiscals')],
          ['contacte', t('config.tab.shop', 'Botiga')],
          ['disseny', t('config.tab.design', 'Disseny')],
          ['css', t('config.tab.css', 'CSS')],
          ['iva', t('config.tab.vat', "Tipus d'IVA")],
          ['marges', t('config.tab.margins', 'Marges')],
          ['cubetes', t('config.tab.sections', 'Cubetes')],
          ['enviaments', t('config.tab.shipping', 'Enviaments')],
          ['secrets', t('config.tab.secrets', 'Secrets')],
        ].map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${tab === k ? 'bg-white shadow-sm text-zinc-900' : 'text-zinc-600 hover:text-zinc-900'}`}>
            {l}
          </button>
        ))}
      </div>

      {loading || !config ? (
        <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading')}</div>
      ) : tab === 'fiscals' ? (
        <DadesFiscalsPanel config={config} onSaved={loadConfig} />
      ) : tab === 'contacte' ? (
        <BotigaPanel config={config} onSaved={loadConfig} />
      ) : tab === 'disseny' ? (
        <DissenyPanel config={config} onSaved={loadConfig} />
      ) : tab === 'css' ? (
        <CustomCssPanel config={config} onSaved={loadConfig} />
      ) : tab === 'iva' ? (
        <TipusIvaPanel />
      ) : tab === 'marges' ? (
        <MargesPanel />
      ) : tab === 'cubetes' ? (
        <SeccionsPanel />
      ) : tab === 'secrets' ? (
        <SecretsPanel />
      ) : (
        <div className="space-y-8">
          <PesFormatPanel />
          <TramsEnviamentPanel />
        </div>
      )}
    </div>
  );
}

function DadesFiscalsPanel({ config, onSaved }) {
  const t = useT();
  const [nomFiscal, setNomFiscal] = useState(config.fiscal_name || '');
  const [nif, setNif] = useState(config.nif || '');
  const [adreca, setAdreca] = useState(config.address || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    setSaved(false);
    const r = await authFetch('/admin/configuracio', {
      method: 'PATCH',
      body: JSON.stringify({ fiscal_name: nomFiscal, nif, address: adreca }),
    });
    setSaving(false);
    if (r.ok) {
      setSaved(true);
      onSaved();
    } else {
      setError((await r.json()).detail || t('config.save_error', 'Error desant'));
    }
  }

  return (
    <form onSubmit={save} className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6 space-y-4 max-w-lg">
      <p className="text-sm text-zinc-500">
        {t('config.fiscal.hint', 'Dades fiscals de la botiga: apareixen a la capçalera dels PDF de comanda a proveïdor.')}
      </p>
      <div>
        <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.fiscal.name', 'Nom / raó social *')}</label>
        <input value={nomFiscal} onChange={e => setNomFiscal(e.target.value)} required
          className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
      </div>
      <div>
        <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.col.nif', 'NIF')}</label>
        <input value={nif} onChange={e => setNif(e.target.value)}
          className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
      </div>
      <div>
        <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.fiscal.address', 'Adreça fiscal *')}</label>
        <textarea value={adreca} onChange={e => setAdreca(e.target.value)} required rows={3}
          placeholder={t('config.fiscal.address_ph', 'Carrer, número\nCodi postal, ciutat')}
          className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
        <p className="text-xs text-zinc-400 mt-1">{t('config.fiscal.address_hint', 'Cada línia es mostra per separat al PDF.')}</p>
      </div>
      {error && <p className="text-red-500 text-xs">{error}</p>}
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={saving}>{saving ? t('common.saving') : t('config.save_changes', 'Desar canvis')}</Button>
        {saved && !saving && <span className="text-xs text-green-600">{t('subscriptions.config.saved', 'Desat')}</span>}
      </div>
    </form>
  );
}

function BotigaPanel({ config, onSaved }) {
  const t = useT();
  const [telefon, setTelefon] = useState(config.phone || '');
  const [email, setEmail] = useState(config.contact_email || '');
  const [emailFrom, setEmailFrom] = useState(config.email_from || '');
  const [instagram, setInstagram] = useState(config.instagram_url || '');
  const [horari, setHorari] = useState(config.hours || '');
  const [reservaMinuts, setReservaMinuts] = useState(config.reservation_minutes ?? 20);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [uploadingFavicon, setUploadingFavicon] = useState(false);
  const [faviconError, setFaviconError] = useState('');
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [logoError, setLogoError] = useState('');

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    setSaved(false);
    const r = await authFetch('/admin/configuracio', {
      method: 'PATCH',
      body: JSON.stringify({
        phone: telefon || null,
        contact_email: email || null,
        email_from: emailFrom || null,
        instagram_url: instagram || null,
        hours: horari || null,
        reservation_minutes: Number(reservaMinuts),
      }),
    });
    setSaving(false);
    if (r.ok) {
      setSaved(true);
      onSaved();
    } else {
      setError((await r.json()).detail || t('config.save_error', 'Error desant'));
    }
  }

  async function toggleSubscripcions() {
    await authFetch('/admin/configuracio', {
      method: 'PATCH',
      body: JSON.stringify({ subscripcions_actives: !config.subscripcions_actives }),
    });
    onSaved();
  }

  async function toggleManteniment() {
    await authFetch('/admin/configuracio', {
      method: 'PATCH',
      body: JSON.stringify({ maintenance_active: !config.maintenance_active }),
    });
    onSaved();
  }

  async function toggleDiscogs() {
    await authFetch('/admin/configuracio', {
      method: 'PATCH',
      body: JSON.stringify({ discogs_habilitat: !config.discogs_habilitat }),
    });
    onSaved();
  }

  async function toggleCatalogFeature(key) {
    await authFetch('/admin/configuracio', {
      method: 'PATCH',
      body: JSON.stringify({ [key]: !config[key] }),
    });
    onSaved();
  }

  async function uploadFavicon(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingFavicon(true);
    setFaviconError('');
    const fd = new FormData();
    fd.append('file', file);
    const r = await authFetch('/admin/configuracio/favicon', { method: 'POST', body: fd });
    if (r.ok) {
      onSaved();
    } else {
      const err = await r.json().catch(() => ({}));
      setFaviconError(err.detail || t('config.favicon_upload_error', "No s'ha pogut pujar el favicon."));
    }
    setUploadingFavicon(false);
    e.target.value = '';
  }

  async function removeFavicon() {
    setUploadingFavicon(true);
    await authFetch('/admin/configuracio/favicon', { method: 'DELETE' });
    setUploadingFavicon(false);
    onSaved();
  }

  async function uploadLogo(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingLogo(true);
    setLogoError('');
    const fd = new FormData();
    fd.append('file', file);
    const r = await authFetch('/admin/configuracio/logo', { method: 'POST', body: fd });
    if (r.ok) {
      onSaved();
    } else {
      const err = await r.json().catch(() => ({}));
      setLogoError(err.detail || t('config.logo_upload_error', "No s'ha pogut pujar el logo."));
    }
    setUploadingLogo(false);
    e.target.value = '';
  }

  async function removeLogo() {
    setUploadingLogo(true);
    await authFetch('/admin/configuracio/logo', { method: 'DELETE' });
    setUploadingLogo(false);
    onSaved();
  }

  return (
    <form onSubmit={save} className="space-y-5 max-w-lg">
      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6 space-y-4">
        <p className="text-sm text-zinc-500">
          {t('config.shop.hint', 'Contacte i xarxes que es mostren al peu de la web pública.')}
        </p>
        <div>
          <label className="block text-sm font-medium text-zinc-700 mb-1">{t('purchases.col.phone', 'Telèfon')}</label>
          <input value={telefon} onChange={e => setTelefon(e.target.value)}
            className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
        </div>
        <div>
          <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.shop.contact_email', 'Email de contacte')}</label>
          <input type="email" value={email} onChange={e => setEmail(e.target.value)}
            className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
        </div>
        <div>
          <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.shop.email_from', 'Remitent dels emails ("From")')}</label>
          <input type="email" value={emailFrom} onChange={e => setEmailFrom(e.target.value)}
            placeholder={t('config.shop.email_from_placeholder', 'botiga@exemple.com')}
            className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          <p className="text-xs text-zinc-400 mt-1">
            {t('config.shop.email_from_hint', "Adreça amb la qual s'envien els emails transaccionals (confirmació de comanda, magic link...).")}
          </p>
        </div>
        <div>
          <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.shop.instagram', 'Instagram (URL)')}</label>
          <input value={instagram} onChange={e => setInstagram(e.target.value)}
            placeholder="https://instagram.com/..."
            className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
        </div>
        <div>
          <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.shop.hours', 'Horari')}</label>
          <textarea value={horari} onChange={e => setHorari(e.target.value)} rows={3}
            placeholder={'Dl–Dv: 11h–20h\nDs: 11h–14h / 17h–20h\nDg: tancat'}
            className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          <p className="text-xs text-zinc-400 mt-1">{t('config.shop.hours_hint', 'Cada línia es mostra per separat al footer.')}</p>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6 space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-zinc-700">{t('config.favicon', 'Favicon')}</p>
            <p className="text-xs text-zinc-400 mt-1 max-w-md">
              {t('config.favicon_hint', "La icona que es veu a la pestanya del navegador. Sense pujar-ne cap, s'utilitza la de per defecte.")}
            </p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            {config.favicon_url && (
              <img src={config.favicon_url} alt="" className="w-8 h-8 rounded border border-zinc-200 object-contain" />
            )}
            <label className="text-sm font-medium text-zinc-700 border border-zinc-300 rounded-lg px-3 py-1.5 cursor-pointer hover:bg-zinc-50">
              {uploadingFavicon ? t('common.loading') : t('config.favicon_upload', 'Pujar')}
              <input type="file" accept=".png,.ico,.jpg,.jpeg,.webp" className="hidden"
                disabled={uploadingFavicon} onChange={uploadFavicon} />
            </label>
            {config.favicon_url && (
              <button type="button" onClick={removeFavicon} disabled={uploadingFavicon}
                className="text-zinc-400 hover:text-red-500 transition-colors">
                <Trash2 size={16} />
              </button>
            )}
          </div>
        </div>
        {faviconError && <p className="text-sm text-red-600">{faviconError}</p>}
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6 space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-zinc-700">{t('config.logo', 'Logo')}</p>
            <p className="text-xs text-zinc-400 mt-1 max-w-md">
              {t('config.logo_hint', "El logo del capçal i del peu de la web pública. Sense pujar-ne cap, es mostra el nom de la botiga en text.")}
            </p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            {config.logo_url && (
              <img src={config.logo_url} alt="" className="h-8 w-auto max-w-[120px] rounded border border-zinc-200 object-contain bg-zinc-900 p-1" />
            )}
            <label className="text-sm font-medium text-zinc-700 border border-zinc-300 rounded-lg px-3 py-1.5 cursor-pointer hover:bg-zinc-50">
              {uploadingLogo ? t('common.loading') : t('config.logo_upload', 'Pujar')}
              <input type="file" accept=".png,.jpg,.jpeg,.webp" className="hidden"
                disabled={uploadingLogo} onChange={uploadLogo} />
            </label>
            {config.logo_url && (
              <button type="button" onClick={removeLogo} disabled={uploadingLogo}
                className="text-zinc-400 hover:text-red-500 transition-colors">
                <Trash2 size={16} />
              </button>
            )}
          </div>
        </div>
        {logoError && <p className="text-sm text-red-600">{logoError}</p>}
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6 space-y-4">
        <p className="text-sm text-zinc-500">{t('config.shop.checkout_params', 'Paràmetres operatius del checkout.')}</p>
        <div>
          <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.shop.reserve_minutes', 'Minuts de reserva de stock')}</label>
          <input type="number" min="1" value={reservaMinuts} onChange={e => setReservaMinuts(e.target.value)}
            className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          <p className="text-xs text-zinc-400 mt-1">
            {t('config.shop.reserve_minutes_hint', "Temps que es reserva un exemplar mentre un client fa el checkout abans d'alliberar-se.")}
          </p>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6 space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-zinc-700">{t('config.shop.record_club', 'Club del disc (subscripció)')}</p>
            <p className="text-xs text-zinc-400 mt-1 max-w-md">
              {t('config.shop.record_club_hint', 'Activa o desactiva l\'opció de subscriure\'s al front públic. Els plans, els subscriptors i el cicle mensual es gestionen a "Club del disc" al menú.')}
            </p>
          </div>
          <button type="button" onClick={toggleSubscripcions}
            className={`w-10 h-5 rounded-full transition-colors relative shrink-0 ${config.subscripcions_actives ? 'bg-green-500' : 'bg-zinc-300'}`}>
            <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${config.subscripcions_actives ? 'left-5' : 'left-0.5'}`} />
          </button>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6 space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-zinc-700">{t('config.shop.maintenance_mode', 'Mode manteniment (web en construcció)')}</p>
            <p className="text-xs text-zinc-400 mt-1 max-w-md">
              {t('config.shop.maintenance_mode_hint', 'Bloqueja el checkout a qualsevol client que no sigui admin i mostra un banner "en construcció" a tota la web pública. Un admin loguejat pot seguir comprant per provar el flux sencer.')}
            </p>
          </div>
          <button type="button" onClick={toggleManteniment}
            className={`w-10 h-5 rounded-full transition-colors relative shrink-0 ${config.maintenance_active ? 'bg-amber-500' : 'bg-zinc-300'}`}>
            <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${config.maintenance_active ? 'left-5' : 'left-0.5'}`} />
          </button>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6 space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-zinc-700">{t('config.shop.discogs_sync', 'Sincronització amb Discogs')}</p>
            <p className="text-xs text-zinc-400 mt-1 max-w-md">
              {t('config.shop.discogs_sync_hint', "Activa la cerca i sincronització d'estoc amb Discogs des del catàleg. Només té sentit si el negoci ven vinils via Discogs.")}
            </p>
          </div>
          <button type="button" onClick={toggleDiscogs}
            className={`w-10 h-5 rounded-full transition-colors relative shrink-0 ${config.discogs_habilitat ? 'bg-green-500' : 'bg-zinc-300'}`}>
            <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${config.discogs_habilitat ? 'left-5' : 'left-0.5'}`} />
          </button>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6 space-y-4">
        <p className="text-sm text-zinc-500">
          {t('config.shop.catalog_features_hint', 'Funcions del catàleg públic que només tenen sentit per a vinils — es poden apagar individualment encara que el teu vertical les tingui disponibles.')}
        </p>
        {[
          { key: 'catalog_browse_mode', label: t('config.shop.catalog_browse_mode', 'Mode "Remena" (cubetes)'), hint: t('config.shop.catalog_browse_mode_hint', 'Navegar el catàleg com si regires les cubetes físiques de la botiga.') },
          { key: 'catalog_format_filter', label: t('config.shop.catalog_format_filter', 'Filtre de format'), hint: t('config.shop.catalog_format_filter_hint', 'LP, 12", CD, Cassette... al catàleg.') },
          { key: 'catalog_genre_filter', label: t('config.shop.catalog_genre_filter', 'Filtre de gènere'), hint: t('config.shop.catalog_genre_filter_hint', 'Cercar per gènere musical al catàleg.') },
        ].map(({ key, label, hint }) => (
          <div key={key} className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-zinc-700">{label}</p>
              <p className="text-xs text-zinc-400 mt-1 max-w-md">{hint}</p>
            </div>
            <button type="button" onClick={() => toggleCatalogFeature(key)}
              className={`w-10 h-5 rounded-full transition-colors relative shrink-0 ${config[key] ? 'bg-green-500' : 'bg-zinc-300'}`}>
              <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${config[key] ? 'left-5' : 'left-0.5'}`} />
            </button>
          </div>
        ))}
      </div>

      {error && <p className="text-red-500 text-xs">{error}</p>}
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={saving}>{saving ? t('common.saving') : t('config.save_changes', 'Desar canvis')}</Button>
        {saved && !saving && <span className="text-xs text-green-600">{t('subscriptions.config.saved', 'Desat')}</span>}
      </div>
    </form>
  );
}

// Claus 1:1 amb THEME_COLOR_FIELDS del backend (api/app/schemas/configuracio.py)
// i amb les variables CSS de web/app/globals.css — els valors per defecte
// d'aquí són literalment els mateixos que hi ha allà, perquè un tenant que
// no ha tocat res vegi els pickers ja carregats amb el look actual, no en blanc.
const THEME_FIELDS = [
  { key: 'background', label: 'Fons', default: '#faf9f6' },
  { key: 'foreground', label: 'Text', default: '#1a1a1a' },
  { key: 'primary', label: 'Principal', default: '#171717' },
  { key: 'primary_foreground', label: 'Text sobre principal', default: '#ffffff' },
  { key: 'secondary', label: 'Secundari', default: '#f5f5f5' },
  { key: 'secondary_foreground', label: 'Text sobre secundari', default: '#1a1a1a' },
  { key: 'accent', label: 'Accent', default: '#f2f2f2' },
  { key: 'accent_foreground', label: 'Text sobre accent', default: '#262626' },
  { key: 'muted', label: 'Apagat', default: '#f2f2f2' },
  { key: 'muted_foreground', label: 'Text apagat', default: '#757575' },
  { key: 'border', label: 'Vores', default: '#cccccc' },
];

function DissenyPanel({ config, onSaved }) {
  const t = useT();
  const [values, setValues] = useState(() => {
    const v = {};
    for (const f of THEME_FIELDS) v[f.key] = config.theme?.[f.key] || f.default;
    return v;
  });
  const [fontHeadline, setFontHeadline] = useState(config.theme?.font_headline || '');
  const [fontBody, setFontBody] = useState(config.theme?.font_body || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  function setColor(key, value) {
    setValues((v) => ({ ...v, [key]: value }));
  }

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    setSaved(false);
    const r = await authFetch('/admin/configuracio/theme', {
      method: 'PATCH',
      body: JSON.stringify({
        ...values,
        font_headline: fontHeadline || null,
        font_body: fontBody || null,
      }),
    });
    setSaving(false);
    if (r.ok) {
      setSaved(true);
      onSaved();
    } else {
      setError((await r.json()).detail || t('config.save_error', 'Error desant'));
    }
  }

  function resetDefaults() {
    const v = {};
    for (const f of THEME_FIELDS) v[f.key] = f.default;
    setValues(v);
    setFontHeadline('');
    setFontBody('');
  }

  return (
    <form onSubmit={save} className="space-y-5 max-w-2xl">
      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6 space-y-4">
        <p className="text-sm text-zinc-500">
          {t('config.design.hint', "Colors i tipografia propis de la teva botiga. Si has encarregat un disseny, pots copiar aquí els valors exactes (hex, nom de la font) que et doni el/la dissenyador/a.")}
        </p>

        <div className="flex h-10 rounded-lg overflow-hidden border border-zinc-200">
          {THEME_FIELDS.map((f) => (
            <div key={f.key} className="flex-1" style={{ backgroundColor: values[f.key] }} title={f.label} />
          ))}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {THEME_FIELDS.map((f) => (
            <div key={f.key} className="flex items-center gap-2">
              <input
                type="color"
                value={values[f.key]}
                onChange={(e) => setColor(f.key, e.target.value)}
                className="w-9 h-9 rounded border border-zinc-300 shrink-0 cursor-pointer"
              />
              <div className="min-w-0 flex-1">
                <label className="block text-xs font-medium text-zinc-700">{f.label}</label>
                <input
                  value={values[f.key]}
                  onChange={(e) => setColor(f.key, e.target.value)}
                  className="w-full border border-zinc-300 rounded-lg px-2 py-1 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-zinc-900"
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6 space-y-4">
        <p className="text-sm text-zinc-500">
          {t('config.design.font_hint', 'Nom de família tipogràfica de Google Fonts. Si el nom no existeix, es fa servir la tipografia per defecte sense trencar la pàgina.')}
        </p>
        <div>
          <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.design.font_headline', 'Tipografia de títols')}</label>
          <input value={fontHeadline} onChange={(e) => setFontHeadline(e.target.value)}
            placeholder="Bodoni Moda, Georgia, serif"
            className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
        </div>
        <div>
          <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.design.font_body', 'Tipografia de text')}</label>
          <input value={fontBody} onChange={(e) => setFontBody(e.target.value)}
            placeholder="Hanken Grotesk, system-ui, sans-serif"
            className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={saving}>{saving ? t('common.saving') : t('config.save_changes', 'Desar canvis')}</Button>
        <button type="button" onClick={resetDefaults} className="text-xs text-zinc-500 hover:text-zinc-700">
          {t('config.design.reset', 'Restaurar valors per defecte')}
        </button>
        {saved && !saving && <span className="text-xs text-green-600">{t('subscriptions.config.saved', 'Desat')}</span>}
      </div>
    </form>
  );
}

function CustomCssPanel({ config, onSaved }) {
  const t = useT();
  const [css, setCss] = useState(config.custom_css || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    setSaved(false);
    const r = await authFetch('/admin/configuracio/custom-css', {
      method: 'PATCH',
      body: JSON.stringify({ custom_css: css || null }),
    });
    setSaving(false);
    if (r.ok) {
      setSaved(true);
      onSaved();
    } else {
      setError((await r.json()).detail || t('config.save_error', 'Error desant'));
    }
  }

  return (
    <form onSubmit={save} className="space-y-5 max-w-2xl">
      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6 space-y-3">
        <p className="text-sm text-zinc-500">
          {t('config.css.hint', "Per a retocs que els colors/tipografia de \"Disseny\" no cobreixin. Pensat per a qui sap CSS o per al/la dissenyador/a que hagis contractat — no s'accepten @import ni @media en aquesta primera versió.")}
        </p>
        <textarea
          value={css}
          onChange={(e) => setCss(e.target.value)}
          rows={16}
          placeholder=".hero { letter-spacing: 0.02em; }"
          spellCheck={false}
          className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-zinc-900"
        />
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={saving}>{saving ? t('common.saving') : t('config.save_changes', 'Desar canvis')}</Button>
        {saved && !saving && <span className="text-xs text-green-600">{t('subscriptions.config.saved', 'Desat')}</span>}
      </div>
    </form>
  );
}

const SECRET_FIELDS = [
  { key: 'redsys_merchant_code', labelKey: 'config.secrets.redsys_merchant_code', label: 'Redsys — codi de comerç' },
  { key: 'redsys_terminal', labelKey: 'config.secrets.redsys_terminal', label: 'Redsys — terminal' },
  { key: 'redsys_secret_key', labelKey: 'config.secrets.redsys_secret_key', label: 'Redsys — clau secreta' },
  { key: 'discogs_token', labelKey: 'config.secrets.discogs_token', label: 'Discogs — token' },
  { key: 'spotify_client_id', labelKey: 'config.secrets.spotify_client_id', label: 'Spotify — client id' },
  { key: 'spotify_client_secret', labelKey: 'config.secrets.spotify_client_secret', label: 'Spotify — client secret' },
];

function SecretsPanel() {
  const t = useT();
  const [status, setStatus] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  async function load() {
    const r = await authFetch('/admin/secrets');
    if (r.ok) setStatus(await r.json());
  }
  useEffect(() => { load(); }, []);

  async function handleSave(e) {
    e.preventDefault();
    setMessage('');
    // Solo se envían los campos que se han escrito de verdad — el backend
    // nunca devuelve el valor real, solo si está configurado o no, así que
    // nunca hay nada que precargar ni reenviar sin querer.
    const payload = Object.fromEntries(
      Object.entries(drafts).filter(([, v]) => v && v.trim() !== '')
    );
    if (Object.keys(payload).length === 0) {
      setMessage(t('config.secrets.no_new_value', 'No has escrit cap valor nou.'));
      return;
    }
    setSaving(true);
    try {
      const r = await authFetch('/admin/secrets', { method: 'POST', body: JSON.stringify(payload) });
      if (r.ok) {
        setStatus(await r.json());
        setDrafts({});
        setMessage(t('config.secrets.saved_period', 'Desat.'));
      } else {
        const body = await r.json().catch(() => ({}));
        setMessage(body.detail || t('purchases.supplier_modal.save_error', 'No s\'ha pogut desar.'));
      }
    } finally {
      setSaving(false);
    }
  }

  if (status === null) {
    return <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading')}</div>;
  }

  return (
    <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6 space-y-5 max-w-lg">
      <p className="text-sm text-zinc-500">
        {t('config.secrets.hint', 'Els valors no es mostren mai, ni tan sols els que ja estan configurats — només si hi ha alguna cosa desada o no. Escriu un valor nou només al camp que vulguis canviar.')}
      </p>
      <form onSubmit={handleSave} className="space-y-4">
        {SECRET_FIELDS.map(({ key, labelKey, label }) => (
          <div key={key}>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-sm font-medium text-zinc-700">{t(labelKey, label)}</label>
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${status[key] ? 'bg-green-100 text-green-700' : 'bg-zinc-100 text-zinc-500'}`}>
                {status[key] ? t('config.secrets.configured', 'Configurat') : t('config.secrets.not_configured', 'Sense configurar')}
              </span>
            </div>
            <input
              type="password"
              placeholder={t('config.secrets.leave_blank_ph', 'Deixa en blanc per no canviar-lo')}
              value={drafts[key] || ''}
              onChange={e => setDrafts(d => ({ ...d, [key]: e.target.value }))}
              autoComplete="off"
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
            />
          </div>
        ))}
        {message && <p className="text-sm text-zinc-600">{message}</p>}
        <div className="flex items-center gap-3">
          <Button type="submit" disabled={saving}>{saving ? t('common.saving') : t('config.save_changes', 'Desar canvis')}</Button>
        </div>
      </form>
    </div>
  );
}

const TIPUS_LABELS = {
  nou: 'Discos nous (règim general)',
  segona_ma: 'Discos 2a mà (REBU — marge)',
};

function TipusIvaPanel() {
  const t = useT();
  const [tipus, setTipus] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [edit, setEdit] = useState(null);

  async function load() {
    setLoading(true);
    const r = await authFetch('/admin/tipus-iva');
    setTipus(await r.json());
    setLoading(false);
  }
  useEffect(() => { load(); }, []);

  async function toggleActiu(row) {
    await authFetch(`/admin/tipus-iva/${row.id}`, { method: 'PATCH', body: JSON.stringify({ active: !row.active }) });
    load();
  }

  async function marcarDefecte(row, camp) {
    await authFetch(`/admin/tipus-iva/${row.id}`, { method: 'PATCH', body: JSON.stringify({ [camp]: true }) });
    load();
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-500 max-w-xl">
          {t('config.vat.hint', "Configura els percentatges d'IVA. Marca quin tipus s'aplica per defecte a les vendes de discos nous i quin a les de 2a mà (REBU) — a compra es tria sempre a mà.")}
        </p>
        <Button onClick={() => { setEdit(null); setShowForm(true); }}>
          <Plus size={16} /> {t('config.vat.new', 'Nou tipus')}
        </Button>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading')}</div>
        ) : tipus.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('tpv.no_iva_configured', "Cap tipus d'IVA configurat")}</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
              <tr>
                <th className="px-4 py-3 text-left font-medium">{t('common.name')}</th>
                <th className="px-4 py-3 text-right font-medium">%</th>
                <th className="px-4 py-3 text-center font-medium">{t('config.vat.rebu', 'REBU')}</th>
                <th className="px-4 py-3 text-center font-medium">{t('config.default_new', 'Per defecte: nou')}</th>
                <th className="px-4 py-3 text-center font-medium">{t('config.default_used', 'Per defecte: 2a mà')}</th>
                <th className="px-4 py-3 text-center font-medium">{t('purchases.col.status', 'Actiu')}</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {tipus.map(row => (
                <tr key={row.id} className="hover:bg-zinc-50">
                  <td className="px-4 py-3 font-medium text-zinc-900">{row.name}</td>
                  <td className="px-4 py-3 text-right">{parseFloat(row.percentage).toFixed(2)}%</td>
                  <td className="px-4 py-3 text-center">{row.is_rebu ? t('config.yes', 'Sí') : '—'}</td>
                  <td className="px-4 py-3 text-center">
                    {row.default_new ? (
                      <Star size={16} className="inline text-amber-500 fill-amber-500" />
                    ) : (
                      <button onClick={() => marcarDefecte(row, 'default_new')}
                        className="text-xs text-zinc-400 hover:text-zinc-700 underline">{t('config.use', 'Fer servir')}</button>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {row.default_used ? (
                      <Star size={16} className="inline text-amber-500 fill-amber-500" />
                    ) : (
                      <button onClick={() => marcarDefecte(row, 'default_used')}
                        className="text-xs text-zinc-400 hover:text-zinc-700 underline">{t('config.use', 'Fer servir')}</button>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button onClick={() => toggleActiu(row)}
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${row.active ? 'bg-green-100 text-green-700' : 'bg-zinc-100 text-zinc-500'}`}>
                      {row.active ? t('purchases.supplier.active', 'Actiu') : t('purchases.supplier.inactive', 'Inactiu')}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => { setEdit(row); setShowForm(true); }}
                      className="text-xs text-zinc-400 hover:text-zinc-700 font-medium px-2 py-1 rounded hover:bg-zinc-100">
                      {t('catalog.edit')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showForm && (
        <TipusIvaForm tipus={edit} onClose={() => setShowForm(false)} onSaved={() => { setShowForm(false); load(); }} />
      )}
    </div>
  );
}

function TipusIvaForm({ tipus, onClose, onSaved }) {
  const t = useT();
  const isEdit = !!tipus;
  const [name, setName] = useState(tipus?.name || '');
  const [percentage, setPercentage] = useState(tipus?.percentage || '21.00');
  const [esRebu, setEsRebu] = useState(tipus?.is_rebu || false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    const payload = { name, percentage: parseFloat(percentage), is_rebu: esRebu };
    const url = isEdit ? `/admin/tipus-iva/${tipus.id}` : '/admin/tipus-iva';
    const method = isEdit ? 'PATCH' : 'POST';
    const r = await authFetch(url, { method, body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json()).detail || t('config.save_error', 'Error desant'));
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">{isEdit ? t('config.vat.edit_title', "Editar tipus d'IVA") : t('config.vat.new_title', "Nou tipus d'IVA")}</h3>
        </div>
        <form onSubmit={save} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.name_required', 'Nom *')}</label>
            <input value={name} onChange={e => setName(e.target.value)} required
              placeholder={t('config.vat.name_ph', 'General 21%, REBU 2a mà...')}
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.percentage_required', 'Percentatge *')}</label>
            <input type="number" step="0.01" value={percentage} onChange={e => setPercentage(e.target.value)} required
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <label className="flex items-center gap-2 text-sm text-zinc-700">
            <input type="checkbox" checked={esRebu} onChange={e => setEsRebu(e.target.checked)} />
            {t('config.vat.rebu_checkbox', "Règim especial de béns usats (REBU) — l'IVA es calcula sobre el marge, no sobre el preu")}
          </label>
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={saving}>{saving ? t('common.saving') : isEdit ? t('config.save_changes', 'Desar canvis') : t('common.create')}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}

function MargesPanel() {
  const t = useT();
  const [marges, setMarges] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [edit, setEdit] = useState(null);

  async function load() {
    setLoading(true);
    const r = await authFetch('/admin/marges');
    setMarges(await r.json());
    setLoading(false);
  }
  useEffect(() => { load(); }, []);

  async function toggleActiu(m) {
    await authFetch(`/admin/marges/${m.id}`, { method: 'PATCH', body: JSON.stringify({ active: !m.active }) });
    load();
  }

  async function marcarDefecte(m, camp) {
    await authFetch(`/admin/marges/${m.id}`, { method: 'PATCH', body: JSON.stringify({ [camp]: true }) });
    load();
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-500 max-w-xl">
          {t('config.margins.hint', 'Configura els marges de benefici. El de per defecte segons condició (nou / 2a mà) es fa servir per suggerir el preu de venda a la recepció de compres — sempre editable a mà allà.')}
        </p>
        <Button onClick={() => { setEdit(null); setShowForm(true); }}>
          <Plus size={16} /> {t('config.margins.new', 'Nou marge')}
        </Button>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading')}</div>
        ) : marges.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('config.margins.no_margins', 'Cap marge configurat')}</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
              <tr>
                <th className="px-4 py-3 text-left font-medium">{t('common.name')}</th>
                <th className="px-4 py-3 text-right font-medium">%</th>
                <th className="px-4 py-3 text-center font-medium">{t('config.default_new', 'Per defecte: nou')}</th>
                <th className="px-4 py-3 text-center font-medium">{t('config.default_used', 'Per defecte: 2a mà')}</th>
                <th className="px-4 py-3 text-center font-medium">{t('purchases.col.status', 'Actiu')}</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {marges.map(m => (
                <tr key={m.id} className="hover:bg-zinc-50">
                  <td className="px-4 py-3 font-medium text-zinc-900">{m.name}</td>
                  <td className="px-4 py-3 text-right">{parseFloat(m.percentage).toFixed(2)}%</td>
                  <td className="px-4 py-3 text-center">
                    {m.default_new ? (
                      <Star size={16} className="inline text-amber-500 fill-amber-500" />
                    ) : (
                      <button onClick={() => marcarDefecte(m, 'default_new')}
                        className="text-xs text-zinc-400 hover:text-zinc-700 underline">{t('config.use', 'Fer servir')}</button>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {m.default_used ? (
                      <Star size={16} className="inline text-amber-500 fill-amber-500" />
                    ) : (
                      <button onClick={() => marcarDefecte(m, 'default_used')}
                        className="text-xs text-zinc-400 hover:text-zinc-700 underline">{t('config.use', 'Fer servir')}</button>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button onClick={() => toggleActiu(m)}
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${m.active ? 'bg-green-100 text-green-700' : 'bg-zinc-100 text-zinc-500'}`}>
                      {m.active ? t('purchases.supplier.active', 'Actiu') : t('purchases.supplier.inactive', 'Inactiu')}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => { setEdit(m); setShowForm(true); }}
                      className="text-xs text-zinc-400 hover:text-zinc-700 font-medium px-2 py-1 rounded hover:bg-zinc-100">
                      {t('catalog.edit')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showForm && (
        <MargeForm marge={edit} onClose={() => setShowForm(false)} onSaved={() => { setShowForm(false); load(); }} />
      )}
    </div>
  );
}

function MargeForm({ marge, onClose, onSaved }) {
  const t = useT();
  const isEdit = !!marge;
  const [name, setName] = useState(marge?.name || '');
  const [percentage, setPercentage] = useState(marge?.percentage || '40.00');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    const payload = { name, percentage: parseFloat(percentage) };
    const url = isEdit ? `/admin/marges/${marge.id}` : '/admin/marges';
    const method = isEdit ? 'PATCH' : 'POST';
    const r = await authFetch(url, { method, body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json()).detail || t('config.save_error', 'Error desant'));
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">{isEdit ? t('config.margins.edit_title', 'Editar marge') : t('config.margins.new_title', 'Nou marge')}</h3>
        </div>
        <form onSubmit={save} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.name_required', 'Nom *')}</label>
            <input value={name} onChange={e => setName(e.target.value)} required
              placeholder={t('config.margins.name_ph', "Marge estàndard nou, marge col·leccionista...")}
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.percentage_required', 'Percentatge *')}</label>
            <input type="number" step="0.01" value={percentage} onChange={e => setPercentage(e.target.value)} required
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={saving}>{saving ? t('common.saving') : isEdit ? t('config.save_changes', 'Desar canvis') : t('common.create')}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}

const FORMATS_DISPONIBLES = ['LP', 'EP', '7"', '12"', 'CD', 'Cassette', 'Altre'];

function PesFormatPanel() {
  const t = useT();
  const [pesos, setPesos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [edit, setEdit] = useState(null);

  async function load() {
    setLoading(true);
    const r = await authFetch('/admin/pes-format');
    setPesos(await r.json());
    setLoading(false);
  }
  useEffect(() => { load(); }, []);

  async function eliminar(p) {
    if (!confirm(t('config.weight.confirm_delete', 'Eliminar el pes configurat per a "{format}"?').replace('{format}', p.formato))) return;
    await authFetch(`/admin/pes-format/${p.id}`, { method: 'DELETE' });
    load();
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-500 max-w-xl">
          {t('config.weight.hint', "Pes per defecte segons el format del disc: s'usa per calcular el pes total d'una comanda (i per tant el tram d'enviament) quan una còpia no té un pes propi indicat al catàleg. Un LP no pesa el mateix que un CD o un 7\".")}
        </p>
        <Button onClick={() => { setEdit(null); setShowForm(true); }}>
          <Plus size={16} /> {t('config.weight.new', 'Nou format')}
        </Button>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading')}</div>
        ) : pesos.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">
            {t('config.weight.no_formats', "Cap format configurat — s'usarà un pes genèric per defecte.")}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
              <tr>
                <th className="px-4 py-3 text-left font-medium">{t('catalog.col.format')}</th>
                <th className="px-4 py-3 text-right font-medium">{t('config.weight.col_weight', 'Pes')}</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {pesos.map(p => (
                <tr key={p.id} className="hover:bg-zinc-50">
                  <td className="px-4 py-3 font-medium text-zinc-900">{p.formato}</td>
                  <td className="px-4 py-3 text-right">{p.pes_g} g</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-1">
                      <button onClick={() => { setEdit(p); setShowForm(true); }}
                        className="text-xs text-zinc-400 hover:text-zinc-700 font-medium px-2 py-1 rounded hover:bg-zinc-100">
                        {t('catalog.edit')}
                      </button>
                      <button onClick={() => eliminar(p)}
                        className="text-zinc-400 hover:text-red-600 p-1.5 rounded hover:bg-red-50">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showForm && (
        <PesFormatForm pes={edit} existents={pesos} onClose={() => setShowForm(false)} onSaved={() => { setShowForm(false); load(); }} />
      )}
    </div>
  );
}

function PesFormatForm({ pes, existents, onClose, onSaved }) {
  const t = useT();
  const isEdit = !!pes;
  const disponibles = FORMATS_DISPONIBLES.filter(f => isEdit || !existents.some(e => e.formato === f));
  const [formato, setFormato] = useState(pes?.formato || disponibles[0] || '');
  const [pesG, setPesG] = useState(pes?.pes_g || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    const url = isEdit ? `/admin/pes-format/${pes.id}` : '/admin/pes-format';
    const method = isEdit ? 'PATCH' : 'POST';
    const payload = isEdit ? { pes_g: Number(pesG) } : { formato, pes_g: Number(pesG) };
    const r = await authFetch(url, { method, body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json()).detail || t('config.save_error', 'Error desant'));
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">{isEdit ? t('config.weight.edit_title', 'Editar pes') : t('config.weight.new_title', 'Nou pes per format')}</h3>
        </div>
        <form onSubmit={save} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.format_required', 'Format *')}</label>
            {isEdit ? (
              <input value={formato} disabled
                className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm bg-zinc-50 text-zinc-500" />
            ) : (
              <select value={formato} onChange={e => setFormato(e.target.value)} required
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white">
                {disponibles.map(f => <option key={f} value={f}>{f}</option>)}
              </select>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.modal.weight_required', 'Pes (grams) *')}</label>
            <input type="number" min="1" value={pesG} onChange={e => setPesG(e.target.value)} required
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={saving}>{saving ? t('common.saving') : isEdit ? t('config.save_changes', 'Desar canvis') : t('common.create')}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}

const SECCIO_COLORS = [
  '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#3b82f6', '#ec4899', '#06b6d4', '#84cc16',
];

function SeccionsPanel() {
  const t = useT();
  const [seccions, setSeccions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [edit, setEdit] = useState(null);

  async function load() {
    setLoading(true);
    const r = await authFetch('/admin/seccions');
    setSeccions(await r.json());
    setLoading(false);
  }
  useEffect(() => { load(); }, []);

  async function toggleActiva(s) {
    await authFetch(`/admin/seccions/${s.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ ...s, name_es: s.name_es || '', active: !s.active }),
    });
    load();
  }

  async function eliminar(s) {
    if (!confirm(t('config.sections.confirm_delete', 'Eliminar la cubeta "{nom}"? Els discos que hi eren assignats quedaran sense classificar.').replace('{nom}', s.name_ca))) return;
    await authFetch(`/admin/seccions/${s.id}`, { method: 'DELETE' });
    load();
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-500 max-w-xl">
          {t('config.sections.hint', 'Cubetes físiques de la botiga (Nacional, Internacional, Alternatiu...). Cada disc pot viure en una sola cubeta — s\'assigna des de la fitxa del disc — i determinen les files del mode "Remena" del catàleg públic.')}
        </p>
        <Button onClick={() => { setEdit(null); setShowForm(true); }}>
          <Plus size={16} /> {t('config.sections.new', 'Nova cubeta')}
        </Button>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading')}</div>
        ) : seccions.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">
            {t('config.sections.no_sections', "Encara no hi ha cap cubeta configurada. Crea'n una!")}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
              <tr>
                <th className="px-4 py-3 text-left font-medium">{t('config.sections.col.section', 'Cubeta')}</th>
                <th className="px-4 py-3 text-left font-medium">{t('config.sections.col.slug', 'Slug')}</th>
                <th className="px-4 py-3 text-left font-medium">{t('config.sections.col.spanish', 'Castellà')}</th>
                <th className="px-4 py-3 text-center font-medium">{t('config.sections.col.position', 'Posició')}</th>
                <th className="px-4 py-3 text-center font-medium">{t('config.sections.col.active', 'Activa')}</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {seccions.map(s => (
                <tr key={s.id} className="hover:bg-zinc-50">
                  <td className="px-4 py-3">
                    <span
                      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold text-white"
                      style={{ backgroundColor: s.color || '#94a3b8' }}
                    >
                      {s.name_ca}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-zinc-500 text-xs">{s.slug}</td>
                  <td className="px-4 py-3 text-zinc-500">{s.name_es || '—'}</td>
                  <td className="px-4 py-3 text-center text-zinc-500">{s.position}</td>
                  <td className="px-4 py-3 text-center">
                    <button onClick={() => toggleActiva(s)}
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${s.active ? 'bg-green-100 text-green-700' : 'bg-zinc-100 text-zinc-500'}`}>
                      {s.active ? t('config.sections.active_fem', 'Activa') : t('config.sections.inactive_fem', 'Inactiva')}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-1">
                      <button onClick={() => { setEdit(s); setShowForm(true); }}
                        className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 transition-colors">
                        <Pencil size={14} />
                      </button>
                      <button onClick={() => eliminar(s)}
                        className="p-1.5 rounded-lg text-zinc-400 hover:text-red-600 hover:bg-red-50 transition-colors">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showForm && (
        <SeccioForm seccio={edit} onClose={() => setShowForm(false)} onSaved={() => { setShowForm(false); load(); }} />
      )}
    </div>
  );
}

function SeccioForm({ seccio, onClose, onSaved }) {
  const t = useT();
  const isEdit = !!seccio;
  const [slug, setSlug] = useState(seccio?.slug || '');
  const [nomCa, setNomCa] = useState(seccio?.name_ca || '');
  const [nomEs, setNomEs] = useState(seccio?.name_es || '');
  const [color, setColor] = useState(seccio?.color || '#f59e0b');
  const [position, setPosition] = useState(seccio?.position ?? 0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function save(e) {
    e.preventDefault();
    if (!slug || !nomCa) { setError(t('config.sections.required_fields', 'Slug i nom en català són obligatoris')); return; }
    setSaving(true);
    setError('');
    const payload = { slug, name_ca: nomCa, name_es: nomEs || null, color, active: seccio?.active ?? true, position: Number(position) };
    const url = isEdit ? `/admin/seccions/${seccio.id}` : '/admin/seccions';
    const method = isEdit ? 'PATCH' : 'POST';
    const r = await authFetch(url, { method, body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json()).detail || t('config.save_error', 'Error desant'));
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">{isEdit ? t('config.sections.edit_title', 'Editar cubeta') : t('config.sections.new_title', 'Nova cubeta')}</h3>
        </div>
        <form onSubmit={save} className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.sections.slug_required', 'Slug *')}</label>
              <input value={slug} onChange={e => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, '-'))}
                placeholder="nacional" required
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.sections.col.position', 'Posició')}</label>
              <input type="number" value={position} onChange={e => setPosition(e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.sections.name_ca_required', 'Nom català *')}</label>
            <input value={nomCa} onChange={e => setNomCa(e.target.value)} placeholder="Nacional" required
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.sections.name_es', 'Nom castellà')}</label>
            <input value={nomEs} onChange={e => setNomEs(e.target.value)} placeholder="Nacional"
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-2">{t('catalog.modal.color', 'Color')}</label>
            <div className="flex items-center gap-2 flex-wrap">
              {SECCIO_COLORS.map(c => (
                <button type="button" key={c} onClick={() => setColor(c)}
                  className={`w-7 h-7 rounded-full transition-transform ${color === c ? 'ring-2 ring-offset-2 ring-zinc-400 scale-110' : ''}`}
                  style={{ backgroundColor: c }} />
              ))}
              <input type="color" value={color} onChange={e => setColor(e.target.value)}
                className="w-7 h-7 rounded-full border border-zinc-200 cursor-pointer" title={t('config.sections.custom_color', 'Color personalitzat')} />
              <span className="ml-2 inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold text-white"
                style={{ backgroundColor: color }}>
                {nomCa || t('config.sections.preview', 'Previsualització')}
              </span>
            </div>
          </div>
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={saving}>{saving ? t('common.saving') : isEdit ? t('config.save_changes', 'Desar canvis') : t('common.create')}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}

function TramsEnviamentPanel() {
  const t = useT();
  const [trams, setTrams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [edit, setEdit] = useState(null);

  async function load() {
    setLoading(true);
    const r = await authFetch('/admin/trams-enviament');
    setTrams(await r.json());
    setLoading(false);
  }
  useEffect(() => { load(); }, []);

  async function toggleActiu(tram) {
    await authFetch(`/admin/trams-enviament/${tram.id}`, { method: 'PATCH', body: JSON.stringify({ active: !tram.active }) });
    load();
  }

  async function eliminar(tram) {
    if (!confirm(t('config.shipping.confirm_delete', 'Eliminar el tram fins a {pes} g?').replace('{pes}', tram.max_weight_g))) return;
    await authFetch(`/admin/trams-enviament/${tram.id}`, { method: 'DELETE' });
    load();
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-500 max-w-xl">
          {t('config.shipping.hint', 'Tarifa pròpia d\'enviament per país i tram de pes: cada comanda es cobra amb el tram actiu més barat del país de destí que cobreixi el pes total dels discos. Es fa servir quan el client tria "Enviament" al checkout; la recollida a botiga sempre és gratuïta. Un país només és venedor si té algun tram actiu — per vendre a un país nou, només cal afegir-hi un tram aquí.')}
        </p>
        <Button onClick={() => { setEdit(null); setShowForm(true); }}>
          <Plus size={16} /> {t('config.shipping.new', 'Nou tram')}
        </Button>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading')}</div>
        ) : trams.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">
            {t('config.shipping.no_tiers', 'Cap tram configurat — sense trams no es pot triar "Enviament" a cap país al checkout.')}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
              <tr>
                <th className="px-4 py-3 text-left font-medium">{t('config.shipping.col.country', 'País')}</th>
                <th className="px-4 py-3 text-left font-medium">{t('config.shipping.col.up_to_weight', 'Fins a (pes)')}</th>
                <th className="px-4 py-3 text-right font-medium">{t('common.price', 'Preu')}</th>
                <th className="px-4 py-3 text-center font-medium">{t('purchases.col.status', 'Actiu')}</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {trams.map(tram => (
                <tr key={tram.id} className="hover:bg-zinc-50">
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-zinc-100 text-zinc-600">
                      {tram.country}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-medium text-zinc-900">
                    {tram.max_weight_g >= 1000 ? `${(tram.max_weight_g / 1000).toFixed(2).replace(/\.?0+$/, '')} kg` : `${tram.max_weight_g} g`}
                  </td>
                  <td className="px-4 py-3 text-right">{parseFloat(tram.price).toFixed(2)} €</td>
                  <td className="px-4 py-3 text-center">
                    <button onClick={() => toggleActiu(tram)}
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${tram.active ? 'bg-green-100 text-green-700' : 'bg-zinc-100 text-zinc-500'}`}>
                      {tram.active ? t('purchases.supplier.active', 'Actiu') : t('purchases.supplier.inactive', 'Inactiu')}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-1">
                      <button onClick={() => { setEdit(tram); setShowForm(true); }}
                        className="text-xs text-zinc-400 hover:text-zinc-700 font-medium px-2 py-1 rounded hover:bg-zinc-100">
                        {t('catalog.edit')}
                      </button>
                      <button onClick={() => eliminar(tram)}
                        className="text-zinc-400 hover:text-red-600 p-1.5 rounded hover:bg-red-50">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showForm && (
        <TramEnviamentForm tram={edit} onClose={() => setShowForm(false)} onSaved={() => { setShowForm(false); load(); }} />
      )}
    </div>
  );
}

function TramEnviamentForm({ tram, onClose, onSaved }) {
  const t = useT();
  const isEdit = !!tram;
  const [pesMaxim, setPesMaxim] = useState(tram?.max_weight_g ?? '');
  const [price, setPrice] = useState(tram?.price || '');
  const [country, setCountry] = useState(tram?.country || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    const payload = { max_weight_g: Number(pesMaxim), price: parseFloat(price), country: country.trim().toUpperCase() };
    const url = isEdit ? `/admin/trams-enviament/${tram.id}` : '/admin/trams-enviament';
    const method = isEdit ? 'PATCH' : 'POST';
    const r = await authFetch(url, { method, body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json()).detail || t('config.save_error', 'Error desant'));
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">{isEdit ? t('config.shipping.edit_title', 'Editar tram') : t('config.shipping.new_title', 'Nou tram')}</h3>
        </div>
        <form onSubmit={save} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.shipping.max_weight_required', 'Pes màxim (grams) *')}</label>
            <input type="number" min="1" value={pesMaxim} onChange={e => setPesMaxim(e.target.value)} required
              placeholder="500"
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            <p className="text-xs text-zinc-400 mt-1">
              {t('config.shipping.max_weight_hint', "Aquest tram s'aplica a comandes de fins a aquest pes (inclusiu).")}
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.shipping.price_required', 'Preu *')}</label>
            <input type="number" step="0.01" min="0" value={price} onChange={e => setPrice(e.target.value)} required
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">{t('config.shipping.country_required', 'País *')}</label>
            <input type="text" maxLength={2} value={country} onChange={e => setCountry(e.target.value.toUpperCase())} required
              placeholder="ES, FR, IT…"
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm uppercase focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            <p className="text-xs text-zinc-400 mt-1">
              {t('config.shipping.country_hint', 'Codi de 2 lletres (ISO 3166-1). Un país només és venedor si té algun tram actiu: per afegir-hi un de nou, crea aquí el primer tram amb el seu codi.')}
            </p>
          </div>
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={saving}>{saving ? t('common.saving') : isEdit ? t('config.save_changes', 'Desar canvis') : t('common.create')}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}
