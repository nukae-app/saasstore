'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { authFetch } from '../../lib/auth';
import { searchDiscogsReleases, enrichDiscogsResult, resolveOrCreateRelease } from '../../lib/discogs';
import { useSortFilter } from '../../../components/admin/table/useSortFilter';
import { SortableTh } from '../../../components/admin/table/SortableTh';
import { CoverImg } from '../../../components/admin/discogs/DiscogsSearchField';
import MIcon from '../../../components/ui/m-icon';
import { useT } from '../../lib/i18n';

const ESTAT_LABEL_FALLBACK = {
  pendent: 'Pendent de valorar', pendent_acceptacio: 'Esperant client',
  acceptada: 'Acceptada', rebutjada: 'Rebutjada', en_tramit: 'En tràmit',
  reservada: 'Reservada', recollida: 'Recollida', caducada: 'Caducada', cancelada: 'Cancel·lada',
};
function estatLabel(t, estat) {
  return t(`requests.estat.${estat}`, ESTAT_LABEL_FALLBACK[estat] ?? estat);
}
const ESTAT_COLOR = {
  pendent: 'bg-surface-container-high text-on-surface-variant', pendent_acceptacio: 'bg-amber-100 text-amber-700',
  acceptada: 'bg-blue-100 text-blue-700', rebutjada: 'bg-surface-container-high text-secondary-foreground',
  en_tramit: 'bg-blue-100 text-blue-700', reservada: 'bg-emerald-100 text-emerald-700',
  recollida: 'bg-surface-container-high text-secondary-foreground', caducada: 'bg-red-100 text-red-600',
  cancelada: 'bg-surface-container-high text-secondary-foreground',
};

function CatalogarModal({ peticion, onClose, onSaved }) {
  const t = useT();
  const [mode, setMode] = useState('catalog'); // 'catalog' | 'discogs'
  const [q, setQ] = useState(`${peticion.artista || ''} ${peticion.titulo || ''}`.trim());
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [saving, setSaving] = useState(false);
  const discogsDebounce = useRef(null);

  async function searchCatalog() {
    if (!q.trim()) return;
    setSearching(true);
    try {
      const r = await authFetch(`/admin/releases?q=${encodeURIComponent(q.trim())}&limit=20`);
      const d = await r.json();
      setResults(d.releases || []);
    } finally { setSearching(false); }
  }

  function searchDiscogs(val) {
    setQ(val);
    clearTimeout(discogsDebounce.current);
    if (val.trim().length < 3) { setResults([]); return; }
    discogsDebounce.current = setTimeout(async () => {
      setSearching(true);
      try { setResults(await searchDiscogsReleases(val)); }
      finally { setSearching(false); }
    }, 400);
  }

  useEffect(() => { searchCatalog(); /* eslint-disable-next-line */ }, []);

  function switchMode(next) {
    setMode(next);
    setResults([]);
    if (next === 'discogs') searchDiscogs(q);
    else searchCatalog();
  }

  async function linkExisting(release) {
    setSaving(true);
    try {
      const r = await authFetch(`/admin/peticiones/${peticion.id}/catalogar`, {
        method: 'PATCH', body: JSON.stringify({ release_id: release.id }),
      });
      if (r.ok) onSaved();
    } finally { setSaving(false); }
  }

  async function pickDiscogs(result) {
    setSaving(true);
    try {
      const full = await enrichDiscogsResult(result);
      const rel = await resolveOrCreateRelease(full);
      const r = await authFetch(`/admin/peticiones/${peticion.id}/catalogar`, {
        method: 'PATCH', body: JSON.stringify({ release_id: rel.id }),
      });
      if (r.ok) onSaved();
    } finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
      <div className="bg-card rounded-xl max-w-lg w-full p-6 max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-serif italic text-xl">{t('requests.catalogar_modal.title', 'Catalogar petició')}</h2>
          <button onClick={onClose} className="text-secondary-foreground hover:text-on-surface-variant"><MIcon name="close" size={18} /></button>
        </div>
        <div className="flex gap-1 bg-surface-container-high p-1 rounded-lg w-fit mb-3">
          {[['catalog', t('requests.catalogar_modal.mode_catalog', 'Al catàleg')], ['discogs', t('requests.catalogar_modal.mode_discogs', 'A Discogs')]].map(([key, label]) => (
            <button key={key} onClick={() => switchMode(key)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${mode === key ? 'bg-card text-on-surface shadow-sm' : 'text-secondary-foreground hover:text-on-surface'}`}>
              {label}
            </button>
          ))}
        </div>
        <div className="flex gap-2 mb-3">
          <input value={q}
            onChange={e => mode === 'discogs' ? searchDiscogs(e.target.value) : setQ(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && mode === 'catalog' && searchCatalog()}
            placeholder={mode === 'discogs' ? t('requests.catalogar_modal.search_discogs_ph', 'Cerca a Discogs...') : t('requests.catalogar_modal.search_catalog_ph', 'Cerca al catàleg...')}
            className="flex-1 border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
          {mode === 'catalog' && (
            <button onClick={searchCatalog} className="border border-outline-variant text-on-surface-variant hover:bg-surface-container-high rounded-lg px-3">
              {searching ? <MIcon name="progress_activity" size={14} className="animate-spin" /> : <MIcon name="search" size={14} />}
            </button>
          )}
        </div>
        <div className="flex-1 overflow-y-auto space-y-1.5">
          {results.length === 0 && !searching && (
            <p className="text-sm text-secondary-foreground text-center py-6">
              {mode === 'discogs' ? t('requests.catalogar_modal.no_discogs_results', 'Cap resultat a Discogs.') : t('requests.catalogar_modal.no_catalog_results', "Cap resultat. Prova a cercar-lo a Discogs per donar-lo d'alta.")}
            </p>
          )}
          {mode === 'catalog' && results.map(r => (
            <button key={r.id} disabled={saving} onClick={() => linkExisting(r)}
              className="w-full flex items-center gap-3 text-left p-2.5 rounded-lg shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] hover:border-outline-variant hover:bg-surface-container-high transition-colors disabled:opacity-50">
              {r.imagen_url ? (
                <img src={r.imagen_url} alt="" className="w-9 h-9 rounded object-cover shrink-0 bg-surface-container-high" />
              ) : <div className="w-9 h-9 rounded bg-surface-container-high shrink-0" />}
              <div className="min-w-0">
                <p className="text-sm font-medium text-on-surface truncate">{r.titulo}</p>
                <p className="text-xs text-secondary-foreground truncate">{r.artista} {r.sello ? `· ${r.sello}` : ''}</p>
              </div>
            </button>
          ))}
          {mode === 'discogs' && results.map((r, i) => (
            <button key={r.discogs_release_id || i} disabled={saving} onClick={() => pickDiscogs(r)}
              className="w-full flex items-center gap-3 text-left p-2.5 rounded-lg shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] hover:border-outline-variant hover:bg-surface-container-high transition-colors disabled:opacity-50">
              <CoverImg url={r.imagen_url} size={36} />
              <div className="min-w-0">
                <p className="text-sm font-medium text-on-surface truncate">{r.titulo}</p>
                <p className="text-xs text-secondary-foreground truncate">{[r.artista, r.sello, r.anio, r.genero].filter(Boolean).join(' · ')}</p>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function PrecioModal({ peticion, onClose, onSaved }) {
  const t = useT();
  const [precio, setPrecio] = useState('');
  const [saving, setSaving] = useState(false);

  async function save() {
    if (!precio) return;
    setSaving(true);
    try {
      const r = await authFetch(`/admin/peticiones/${peticion.id}/precio`, {
        method: 'PATCH', body: JSON.stringify({ estimated_price: precio }),
      });
      if (r.ok) onSaved();
    } finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
      <div className="bg-card rounded-xl max-w-sm w-full p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-serif italic text-xl">{t('requests.precio_modal.title', 'Fixar preu')}</h2>
          <button onClick={onClose} className="text-secondary-foreground hover:text-on-surface-variant"><MIcon name="close" size={18} /></button>
        </div>
        <p className="text-sm text-secondary-foreground mb-3">{peticion.artista} — {peticion.titulo}</p>
        <div className="flex items-center gap-2 mb-4">
          <input type="number" step="0.01" min="0" value={precio} onChange={e => setPrecio(e.target.value)}
            placeholder="0.00" autoFocus
            className="flex-1 border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
          <span className="text-secondary-foreground text-sm">€</span>
        </div>
        <p className="text-xs text-secondary-foreground mb-4">
          {peticion.channel === 'tienda'
            ? t('requests.precio_modal.hint_tienda', "Petició de tenda: es donarà per acceptada directament (recollida i pagament a botiga), sense passar pel client.")
            : t('requests.precio_modal.hint_online', "Es notificarà per email al client, que l'haurà d'acceptar abans de fer-ne la comanda.")}
        </p>
        <div className="flex gap-2">
          <button onClick={save} disabled={saving || !precio}
            className="flex items-center gap-1.5 bg-primary hover:opacity-90 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-60">
            {saving ? <MIcon name="progress_activity" size={13} className="animate-spin" /> : <MIcon name="check" size={13} />}
            {saving ? t('requests.precio_modal.sending', 'Enviant…') : peticion.channel === 'tienda' ? t('requests.precio_modal.fix_and_accept', 'Fixar i acceptar') : t('requests.precio_modal.fix_and_notify', 'Fixar i notificar')}
          </button>
          <button onClick={onClose} className="border border-outline-variant text-on-surface-variant px-4 py-2 rounded-lg text-sm hover:bg-surface-container-high transition-colors">
            {t('common.cancel', 'Cancel·lar')}
          </button>
        </div>
      </div>
    </div>
  );
}

function VincularSolicitudModal({ peticion, proveedores, onClose, onSaved }) {
  const t = useT();
  const [cantidad, setCantidad] = useState(1);
  const [proveedorId, setProveedorId] = useState('');
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      const r = await authFetch(`/admin/peticiones/${peticion.id}/vincular-solicitud`, {
        method: 'POST',
        body: JSON.stringify({ cantidad: Number(cantidad), proveedor_sugerido_id: proveedorId || null }),
      });
      if (r.ok) onSaved();
    } finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
      <div className="bg-card rounded-xl max-w-sm w-full p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-serif italic text-xl">{t('requests.solicitud_modal.title', 'Crear sol·licitud de compra')}</h2>
          <button onClick={onClose} className="text-secondary-foreground hover:text-on-surface-variant"><MIcon name="close" size={18} /></button>
        </div>
        <p className="text-sm text-secondary-foreground mb-4">{peticion.artista} — {peticion.titulo}</p>
        <div className="space-y-3 mb-4">
          <div>
            <label className="block text-xs font-medium text-on-surface-variant mb-1">{t('requests.solicitud_modal.quantity', 'Quantitat')}</label>
            <input type="number" min="1" value={cantidad} onChange={e => setCantidad(e.target.value)}
              className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
          </div>
          <div>
            <label className="block text-xs font-medium text-on-surface-variant mb-1">{t('requests.solicitud_modal.suggested_supplier', 'Proveïdor suggerit (opcional)')}</label>
            <select value={proveedorId} onChange={e => setProveedorId(e.target.value)}
              className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary">
              <option value="">{t('requests.solicitud_modal.no_selection', '— sense triar —')}</option>
              {proveedores.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={save} disabled={saving}
            className="flex items-center gap-1.5 bg-primary hover:opacity-90 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-60">
            {saving ? <MIcon name="progress_activity" size={13} className="animate-spin" /> : <MIcon name="check" size={13} />}
            {saving ? t('requests.solicitud_modal.creating', 'Creant…') : t('requests.solicitud_modal.create', 'Crear sol·licitud')}
          </button>
          <button onClick={onClose} className="border border-outline-variant text-on-surface-variant px-4 py-2 rounded-lg text-sm hover:bg-surface-container-high transition-colors">
            {t('common.cancel', 'Cancel·lar')}
          </button>
        </div>
      </div>
    </div>
  );
}

function VincularItemModal({ peticion, onClose, onSaved }) {
  const t = useT();
  const [items, setItems] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    authFetch(`/catalog/releases/${peticion.release_id}`)
      .then(r => r.json())
      .then(d => setItems((d.items || []).filter(i => i.condition === 'nou'
        ? i.status === 'disponible' && (i.quantity - i.reserved_quantity) > 0
        : i.status === 'disponible')));
  }, [peticion.release_id]);

  async function link(item) {
    setSaving(true);
    setError('');
    try {
      const r = await authFetch(`/admin/peticiones/${peticion.id}/vincular-item`, {
        method: 'POST', body: JSON.stringify({ item_id: item.id }),
      });
      if (r.ok) onSaved();
      else { const d = await r.json().catch(() => ({})); setError(d.detail || t('requests.item_modal.link_error', 'No s\'ha pogut vincular.')); }
    } finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
      <div className="bg-card rounded-xl max-w-sm w-full p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-serif italic text-xl">{t('requests.item_modal.title', 'Vincular exemplar')}</h2>
          <button onClick={onClose} className="text-secondary-foreground hover:text-on-surface-variant"><MIcon name="close" size={18} /></button>
        </div>
        <p className="text-sm text-secondary-foreground mb-2">{peticion.artista} — {peticion.titulo}</p>
        <p className="text-xs text-secondary-foreground mb-4">{t('requests.item_modal.hint', "Normalment això es fa sol en rebre la comanda del proveïdor. Fes-ho a mà només si l'exemplar ja és a estoc per una altra via.")}</p>
        {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
        {items === null ? (
          <div className="animate-pulse bg-surface-container-high rounded-lg h-16" />
        ) : items.length === 0 ? (
          <p className="text-sm text-secondary-foreground text-center py-6">{t('requests.item_modal.no_stock', 'Aquest disc encara no té cap exemplar disponible a estoc.')}</p>
        ) : (
          <div className="space-y-1.5">
            {items.map(i => (
              <button key={i.id} disabled={saving} onClick={() => link(i)}
                className="w-full flex items-center justify-between p-2.5 rounded-lg shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] hover:border-outline-variant hover:bg-surface-container-high transition-colors text-sm disabled:opacity-50">
                <span className="text-on-surface-variant">
                  {i.condition === 'nou' ? t('common.condition.new') : t('common.condition.used')} {i.estado_disco ? `· ${i.estado_disco}` : ''}
                  {i.condition === 'nou' && ` · ${t('requests.item_modal.free_units', '{n} lliures').replace('{n}', i.quantity - i.reserved_quantity)}`}
                </span>
                <span className="font-medium text-on-surface">{Number(i.price).toFixed(2)} €</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function NovaPeticioTiendaModal({ onClose, onSaved }) {
  const t = useT();
  const [userQ, setUserQ] = useState('');
  const [userResults, setUserResults] = useState([]);
  const [linkedUser, setLinkedUser] = useState(null);
  const [creatingClient, setCreatingClient] = useState(false);
  const [novaEmail, setNovaEmail] = useState('');
  const [novaNombre, setNovaNombre] = useState('');
  const [novaTelefon, setNovaTelefon] = useState('');
  const [artista, setArtista] = useState('');
  const [titulo, setTitulo] = useState('');
  const [notas, setNotas] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const userDebounce = useRef(null);

  function handleUserQ(val) {
    setUserQ(val);
    setLinkedUser(null);
    clearTimeout(userDebounce.current);
    if (val.trim().length < 2) { setUserResults([]); return; }
    userDebounce.current = setTimeout(async () => {
      const r = await authFetch(`/admin/users/search?q=${encodeURIComponent(val.trim())}`);
      setUserResults(r.ok ? await r.json() : []);
    }, 300);
  }

  function selectUser(u) {
    setLinkedUser(u);
    setUserQ(u.name || u.email);
    setUserResults([]);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      let userId = linkedUser?.id;
      if (!userId) {
        if (!creatingClient || !novaEmail.trim()) {
          setError(t('requests.nova_tienda_modal.need_client', 'Cal seleccionar un client existent o crear-ne un de nou amb email.'));
          return;
        }
        const rUser = await authFetch('/admin/users', {
          method: 'POST',
          body: JSON.stringify({
            email: novaEmail.trim(), name: novaNombre.trim() || null, phone: novaTelefon.trim() || null,
          }),
        });
        if (!rUser.ok) {
          const d = await rUser.json().catch(() => ({}));
          setError(d.detail || t('requests.nova_tienda_modal.create_client_error', 'No s\'ha pogut crear el client.'));
          return;
        }
        userId = (await rUser.json()).id;
      }

      const r = await authFetch('/admin/peticiones/tienda', {
        method: 'POST',
        body: JSON.stringify({
          user_id: userId, free_artist: artista.trim(), free_title: titulo.trim(),
          client_notes: notas.trim() || null,
        }),
      });
      if (r.ok) onSaved();
      else { const d = await r.json().catch(() => ({})); setError(d.detail || t('requests.nova_tienda_modal.create_error', 'No s\'ha pogut crear la petició.')); }
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
      <div className="bg-card rounded-xl max-w-md w-full p-6 max-h-[85vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-serif italic text-xl">{t('requests.nova_tienda_modal.title', 'Petició de tenda o telèfon')}</h2>
          <button onClick={onClose} className="text-secondary-foreground hover:text-on-surface-variant"><MIcon name="close" size={18} /></button>
        </div>
        <p className="text-sm text-secondary-foreground mb-4">
          {t('requests.nova_tienda_modal.hint', "Per quan un client truca o ve a la botiga a demanar un disc. Un cop hi fixis el preu, es dona per acceptat directament (recollida i pagament a botiga) — sense passar per l'acceptació online.")}
        </p>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-on-surface-variant mb-1">{t('requests.nova_tienda_modal.client_required', 'Client *')}</label>
            {linkedUser ? (
              <div className="flex items-center justify-between border border-outline-variant bg-surface-container-high rounded-lg px-3 py-2 text-sm">
                <span>{linkedUser.name || linkedUser.email} {linkedUser.name && <span className="text-secondary-foreground">· {linkedUser.email}</span>}</span>
                <button type="button" onClick={() => { setLinkedUser(null); setUserQ(''); }} className="text-secondary-foreground hover:text-on-surface-variant"><MIcon name="close" size={14} /></button>
              </div>
            ) : (
              <div className="relative">
                <input value={userQ} onChange={e => handleUserQ(e.target.value)}
                  placeholder={t('requests.nova_tienda_modal.search_client_ph', 'Cerca per nom, email o telèfon...')}
                  className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
                {userResults.length > 0 && (
                  <div className="absolute z-10 mt-1 w-full bg-card border border-outline-variant rounded-lg shadow-lg max-h-40 overflow-y-auto">
                    {userResults.map(u => (
                      <button key={u.id} type="button" onClick={() => selectUser(u)}
                        className="w-full text-left px-3 py-2 text-sm hover:bg-surface-container-high border-b border-outline-variant last:border-0">
                        <p className="text-on-surface">{u.name || u.email}</p>
                        {u.name && <p className="text-xs text-secondary-foreground">{u.email}</p>}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
            {!linkedUser && (
              <button type="button" onClick={() => setCreatingClient(v => !v)}
                className="text-xs text-on-surface hover:text-on-surface-variant mt-1.5">
                {creatingClient ? t('requests.nova_tienda_modal.cancel_new_client', 'Cancel·lar client nou') : t('requests.nova_tienda_modal.create_new_client', '+ No té compte: crear client nou')}
              </button>
            )}
            {!linkedUser && creatingClient && (
              <div className="grid grid-cols-2 gap-2 mt-2">
                <input value={novaEmail} onChange={e => setNovaEmail(e.target.value)} type="email" placeholder={t('requests.nova_tienda_modal.email_required_ph', 'Email *')}
                  className="col-span-2 border border-outline-variant rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
                <input value={novaNombre} onChange={e => setNovaNombre(e.target.value)} placeholder={t('requests.nova_tienda_modal.name_optional_ph', 'Nom (opcional)')}
                  className="border border-outline-variant rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
                <input value={novaTelefon} onChange={e => setNovaTelefon(e.target.value)} placeholder={t('requests.nova_tienda_modal.phone_optional_ph', 'Telèfon (opcional)')}
                  className="border border-outline-variant rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
              </div>
            )}
          </div>
          <div>
            <label className="block text-xs font-medium text-on-surface-variant mb-1">{t('requests.nova_tienda_modal.artist_required', 'Artista *')}</label>
            <input value={artista} onChange={e => setArtista(e.target.value)} required
              className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
          </div>
          <div>
            <label className="block text-xs font-medium text-on-surface-variant mb-1">{t('requests.nova_tienda_modal.title_required', 'Títol *')}</label>
            <input value={titulo} onChange={e => setTitulo(e.target.value)} required
              className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
          </div>
          <div>
            <label className="block text-xs font-medium text-on-surface-variant mb-1">{t('requests.nova_tienda_modal.notes_optional', 'Notes (opcional)')}</label>
            <textarea value={notas} onChange={e => setNotas(e.target.value)} rows={2}
              placeholder={t('requests.nova_tienda_modal.notes_ph', 'Format, edició concreta, com contactar-lo...')}
              className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex gap-2 pt-1">
            <button type="submit" disabled={saving}
              className="flex items-center gap-1.5 bg-primary hover:opacity-90 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-60">
              {saving ? <MIcon name="progress_activity" size={13} className="animate-spin" /> : <MIcon name="check" size={13} />}
              {saving ? t('requests.nova_tienda_modal.creating', 'Creant…') : t('requests.nova_tienda_modal.create', 'Crear petició')}
            </button>
            <button type="button" onClick={onClose}
              className="flex items-center gap-1.5 border border-outline-variant text-on-surface-variant px-4 py-2 rounded-lg text-sm hover:bg-surface-container-high transition-colors">
              {t('common.cancel', 'Cancel·lar')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function PeticioRow({ p, proveedores, onRefresh }) {
  const t = useT();
  const [busy, setBusy] = useState(false);
  const [modal, setModal] = useState(null); // 'catalogar' | 'precio' | 'solicitud' | 'item'

  async function cancelar() {
    setBusy(true);
    try {
      await authFetch(`/admin/peticiones/${p.id}/cancelar`, { method: 'PATCH' });
      onRefresh();
    } finally { setBusy(false); }
  }

  const canCancel = !['recollida', 'cancelada'].includes(p.status);

  return (
    <tr className="hover:bg-surface-container-high transition-colors">
      <td className="px-5 py-3">
        <p className="font-medium text-sm text-on-surface">{p.titulo}</p>
        <p className="text-xs text-secondary-foreground">{p.artista}{!p.release_id && ` (${t('requests.out_of_catalog', 'fora de catàleg')})`}</p>
        {p.client_notes && (
          <p className="text-xs text-secondary-foreground mt-1 max-w-xs whitespace-pre-line">{p.client_notes}</p>
        )}
      </td>
      <td className="px-5 py-3 text-sm text-on-surface-variant">
        <p className="flex items-center gap-1.5">
          {p.user_nombre || '—'}
          {p.channel === 'tienda' && (
            <span title={t('requests.created_from_store_tooltip', 'Petició creada des de tenda/telèfon')} className="inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[10px] font-medium bg-surface-container-high text-secondary-foreground">
              <MIcon name="call" size={9} /> {t('requests.store_badge', 'Tenda')}
            </span>
          )}
        </p>
        <p className="text-xs text-secondary-foreground">{p.user_email}</p>
      </td>
      <td className="px-5 py-3 text-center">
        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${ESTAT_COLOR[p.status] || 'bg-surface-container-high text-secondary-foreground'}`}>
          {estatLabel(t, p.status)}
        </span>
        {p.pagada && (
          <span className="ml-1 inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-emerald-100 text-emerald-700">
            {t('requests.paid', 'Pagada')}
          </span>
        )}
      </td>
      <td className="px-5 py-3 text-sm text-on-surface-variant text-right">
        {p.estimated_price ? `${Number(p.estimated_price).toFixed(2)} €` : '—'}
      </td>
      <td className="px-5 py-3">
        <div className="flex items-center justify-end gap-1.5 flex-wrap">
          {p.status === 'pendent' && !p.release_id && (
            <button onClick={() => setModal('catalogar')} className="flex items-center gap-1 text-xs border border-outline-variant text-on-surface-variant hover:bg-surface-container-high px-2.5 py-1.5 rounded-lg transition-colors">
              <MIcon name="link" size={11} /> {t('requests.action.catalogar', 'Catalogar')}
            </button>
          )}
          {p.status === 'pendent' && p.release_id && (
            <>
              <button onClick={() => setModal('catalogar')} className="flex items-center gap-1 text-xs border border-outline-variant text-on-surface-variant hover:bg-surface-container-high px-2.5 py-1.5 rounded-lg transition-colors">
                <MIcon name="link" size={11} /> {t('requests.action.change_record', 'Canviar disc')}
              </button>
              <button onClick={() => setModal('precio')} className="flex items-center gap-1 text-xs border border-outline-variant text-on-surface-variant hover:bg-surface-container-high px-2.5 py-1.5 rounded-lg transition-colors">
                <MIcon name="sell" size={11} /> {t('requests.action.fix_price', 'Fixar preu')}
              </button>
            </>
          )}
          {p.status === 'pendent_acceptacio' && (
            <button onClick={() => setModal('catalogar')} className="flex items-center gap-1 text-xs border border-outline-variant text-on-surface-variant hover:bg-surface-container-high px-2.5 py-1.5 rounded-lg transition-colors">
              <MIcon name="link" size={11} /> {t('requests.action.change_record', 'Canviar disc')}
            </button>
          )}
          {p.status === 'acceptada' && (
            <button onClick={() => setModal('solicitud')} className="flex items-center gap-1 text-xs border border-outline-variant text-on-surface-variant hover:bg-surface-container-high px-2.5 py-1.5 rounded-lg transition-colors">
              <MIcon name="package_2" size={11} /> {t('requests.action.create_solicitud', 'Crear sol·licitud')}
            </button>
          )}
          {p.status === 'en_tramit' && (
            <button onClick={() => setModal('item')} className="flex items-center gap-1 text-xs border border-outline-variant text-on-surface-variant hover:bg-surface-container-high px-2.5 py-1.5 rounded-lg transition-colors">
              <MIcon name="link" size={11} /> {t('requests.action.link_item', 'Vincular exemplar')}
            </button>
          )}
          {canCancel && (
            <button onClick={cancelar} disabled={busy} className="flex items-center gap-1 text-xs text-secondary-foreground hover:text-red-500 px-2 py-1.5 rounded-lg transition-colors disabled:opacity-50">
              <MIcon name="block" size={11} />
            </button>
          )}
        </div>
      </td>

      {modal === 'catalogar' && (
        <CatalogarModal peticion={p} onClose={() => setModal(null)} onSaved={() => { setModal(null); onRefresh(); }} />
      )}
      {modal === 'precio' && (
        <PrecioModal peticion={p} onClose={() => setModal(null)} onSaved={() => { setModal(null); onRefresh(); }} />
      )}
      {modal === 'solicitud' && (
        <VincularSolicitudModal peticion={p} proveedores={proveedores} onClose={() => setModal(null)} onSaved={() => { setModal(null); onRefresh(); }} />
      )}
      {modal === 'item' && (
        <VincularItemModal peticion={p} onClose={() => setModal(null)} onSaved={() => { setModal(null); onRefresh(); }} />
      )}
    </tr>
  );
}

export default function PeticionsPage() {
  const t = useT();
  const [peticiones, setPeticiones] = useState([]);
  const [proveedores, setProveedores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showNova, setShowNova] = useState(false);

  async function load() {
    setLoading(true);
    const [pRes, provRes] = await Promise.all([
      authFetch('/admin/peticiones'), authFetch('/admin/proveedores'),
    ]);
    setPeticiones(await pRes.json());
    setProveedores(await provRes.json());
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  const columns = useMemo(() => ({
    titulo: { sortValue: p => `${p.artista ?? ''} ${p.titulo ?? ''}`.toLowerCase() },
    user_nombre: { sortValue: p => (p.user_nombre ?? '').toLowerCase(), filterValue: p => p.user_nombre },
    status: { sortValue: p => estatLabel(t, p.status) || '', filterValue: p => estatLabel(t, p.status) },
    estimated_price: { sortValue: p => p.estimated_price != null ? parseFloat(p.estimated_price) : null },
  }), [t]);

  const { rows: peticionsFiltrades, sort, toggleSort, filters, setFilter, distinctValues } = useSortFilter(peticiones, columns);

  return (
    <div className="space-y-5 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-on-surface">{t('requests.title', 'Peticions de clients')}</h2>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowNova(true)}
            className="flex items-center gap-1.5 bg-primary hover:opacity-90 text-white px-3 py-2 rounded-lg text-sm font-medium transition-colors">
            <MIcon name="add" size={14} /> {t('requests.new_store_request', 'Petició de tenda')}
          </button>
        </div>
      </div>

      {showNova && (
        <NovaPeticioTiendaModal onClose={() => setShowNova(false)} onSaved={() => { setShowNova(false); load(); }} />
      )}

      <div className="bg-card rounded-2xl border border-outline-variant shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 space-y-2">
            {[1, 2, 3].map(i => <div key={i} className="animate-pulse bg-surface-container-high rounded-lg h-12" />)}
          </div>
        ) : peticionsFiltrades.length === 0 ? (
          <div className="p-12 text-center text-secondary-foreground text-sm">{t('requests.none_found', 'Cap petició trobada.')}</div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-surface-container-high text-xs text-secondary-foreground border-b border-outline-variant">
              <tr>
                <SortableTh label={t('requests.col.record', 'Disc')} sortKey="titulo" sort={sort} onSort={toggleSort} />
                <SortableTh label={t('requests.col.client', 'Client')} sortKey="user_nombre" sort={sort} onSort={toggleSort}
                  filterOptions={distinctValues.user_nombre} selected={filters.user_nombre} onFilterChange={setFilter} />
                <SortableTh label={t('requests.col.status', 'Estat')} sortKey="status" sort={sort} onSort={toggleSort} align="center"
                  filterOptions={distinctValues.status} selected={filters.status} onFilterChange={setFilter} />
                <SortableTh label={t('requests.col.price', 'Preu')} sortKey="estimated_price" sort={sort} onSort={toggleSort} align="right" />
                <th className="px-5 py-3 text-right font-medium">{t('requests.col.actions', 'Accions')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant">
              {peticionsFiltrades.map(p => <PeticioRow key={p.id} p={p} proveedores={proveedores} onRefresh={load} />)}
            </tbody>
          </table>
          </div>
        )}
      </div>
    </div>
  );
}
