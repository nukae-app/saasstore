'use client';

import { useState, useEffect } from 'react';
import { authFetch } from '../../lib/auth';
import { Plus, Star, Trash2, Pencil } from 'lucide-react';
import { Button } from '../../../components/ui/button';

export default function ConfiguracioPage() {
  const [tab, setTab] = useState('fiscals'); // fiscals | contacte | iva | marges | cubetes | enviaments
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
        <h2 className="text-2xl font-bold text-zinc-900">Configuració</h2>
      </div>

      <div className="flex gap-1 bg-zinc-100 p-1 rounded-xl w-fit">
        {[
          ['fiscals', 'Dades fiscals'],
          ['contacte', 'Botiga'],
          ['iva', "Tipus d'IVA"],
          ['marges', 'Marges'],
          ['cubetes', 'Cubetes'],
          ['enviaments', 'Enviaments'],
        ].map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${tab === k ? 'bg-white shadow-sm text-zinc-900' : 'text-zinc-600 hover:text-zinc-900'}`}>
            {l}
          </button>
        ))}
      </div>

      {loading || !config ? (
        <div className="p-12 text-center text-zinc-400 text-sm">Carregant...</div>
      ) : tab === 'fiscals' ? (
        <DadesFiscalsPanel config={config} onSaved={loadConfig} />
      ) : tab === 'contacte' ? (
        <BotigaPanel config={config} onSaved={loadConfig} />
      ) : tab === 'iva' ? (
        <TipusIvaPanel />
      ) : tab === 'marges' ? (
        <MargesPanel />
      ) : tab === 'cubetes' ? (
        <SeccionsPanel />
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
  const [nomFiscal, setNomFiscal] = useState(config.nom_fiscal || '');
  const [nif, setNif] = useState(config.nif || '');
  const [adreca, setAdreca] = useState(config.adreca || '');
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
      body: JSON.stringify({ nom_fiscal: nomFiscal, nif, adreca }),
    });
    setSaving(false);
    if (r.ok) {
      setSaved(true);
      onSaved();
    } else {
      setError((await r.json()).detail || 'Error desant');
    }
  }

  return (
    <form onSubmit={save} className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6 space-y-4 max-w-lg">
      <p className="text-sm text-zinc-500">
        Dades fiscals de la botiga: apareixen a la capçalera dels PDF de comanda a proveïdor.
      </p>
      <div>
        <label className="block text-sm font-medium text-zinc-700 mb-1">Nom / raó social *</label>
        <input value={nomFiscal} onChange={e => setNomFiscal(e.target.value)} required
          className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
      </div>
      <div>
        <label className="block text-sm font-medium text-zinc-700 mb-1">NIF</label>
        <input value={nif} onChange={e => setNif(e.target.value)}
          className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
      </div>
      <div>
        <label className="block text-sm font-medium text-zinc-700 mb-1">Adreça fiscal *</label>
        <textarea value={adreca} onChange={e => setAdreca(e.target.value)} required rows={3}
          placeholder={'Carrer, número\nCodi postal, ciutat'}
          className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
        <p className="text-xs text-zinc-400 mt-1">Cada línia es mostra per separat al PDF.</p>
      </div>
      {error && <p className="text-red-500 text-xs">{error}</p>}
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={saving}>{saving ? 'Desant...' : 'Desar canvis'}</Button>
        {saved && !saving && <span className="text-xs text-green-600">Desat</span>}
      </div>
    </form>
  );
}

function BotigaPanel({ config, onSaved }) {
  const [telefon, setTelefon] = useState(config.telefon || '');
  const [email, setEmail] = useState(config.email_contacte || '');
  const [instagram, setInstagram] = useState(config.instagram_url || '');
  const [horari, setHorari] = useState(config.horari || '');
  const [reservaMinuts, setReservaMinuts] = useState(config.reserva_minuts ?? 20);
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
      body: JSON.stringify({
        telefon: telefon || null,
        email_contacte: email || null,
        instagram_url: instagram || null,
        horari: horari || null,
        reserva_minuts: Number(reservaMinuts),
      }),
    });
    setSaving(false);
    if (r.ok) {
      setSaved(true);
      onSaved();
    } else {
      setError((await r.json()).detail || 'Error desant');
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
      body: JSON.stringify({ manteniment_actiu: !config.manteniment_actiu }),
    });
    onSaved();
  }

  return (
    <form onSubmit={save} className="space-y-5 max-w-lg">
      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6 space-y-4">
        <p className="text-sm text-zinc-500">
          Contacte i xarxes que es mostren al peu de la web pública.
        </p>
        <div>
          <label className="block text-sm font-medium text-zinc-700 mb-1">Telèfon</label>
          <input value={telefon} onChange={e => setTelefon(e.target.value)}
            className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
        </div>
        <div>
          <label className="block text-sm font-medium text-zinc-700 mb-1">Email de contacte</label>
          <input type="email" value={email} onChange={e => setEmail(e.target.value)}
            className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
        </div>
        <div>
          <label className="block text-sm font-medium text-zinc-700 mb-1">Instagram (URL)</label>
          <input value={instagram} onChange={e => setInstagram(e.target.value)}
            placeholder="https://instagram.com/..."
            className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
        </div>
        <div>
          <label className="block text-sm font-medium text-zinc-700 mb-1">Horari</label>
          <textarea value={horari} onChange={e => setHorari(e.target.value)} rows={3}
            placeholder={'Dl–Dv: 11h–20h\nDs: 11h–14h / 17h–20h\nDg: tancat'}
            className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          <p className="text-xs text-zinc-400 mt-1">Cada línia es mostra per separat al footer.</p>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6 space-y-4">
        <p className="text-sm text-zinc-500">Paràmetres operatius del checkout.</p>
        <div>
          <label className="block text-sm font-medium text-zinc-700 mb-1">Minuts de reserva de stock</label>
          <input type="number" min="1" value={reservaMinuts} onChange={e => setReservaMinuts(e.target.value)}
            className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          <p className="text-xs text-zinc-400 mt-1">
            Temps que es reserva un exemplar mentre un client fa el checkout abans d&apos;alliberar-se.
          </p>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6 space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-zinc-700">Club del disc (subscripció)</p>
            <p className="text-xs text-zinc-400 mt-1 max-w-md">
              Activa o desactiva l&apos;opció de subscriure&apos;s al front públic. Els plans, els
              subscriptors i el cicle mensual es gestionen a &quot;Club del disc&quot; al menú.
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
            <p className="text-sm font-medium text-zinc-700">Mode manteniment (web en construcció)</p>
            <p className="text-xs text-zinc-400 mt-1 max-w-md">
              Bloqueja el checkout a qualsevol client que no sigui admin i mostra un banner
              &quot;en construcció&quot; a tota la web pública. Un admin loguejat pot seguir
              comprant per provar el flux sencer.
            </p>
          </div>
          <button type="button" onClick={toggleManteniment}
            className={`w-10 h-5 rounded-full transition-colors relative shrink-0 ${config.manteniment_actiu ? 'bg-amber-500' : 'bg-zinc-300'}`}>
            <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${config.manteniment_actiu ? 'left-5' : 'left-0.5'}`} />
          </button>
        </div>
      </div>

      {error && <p className="text-red-500 text-xs">{error}</p>}
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={saving}>{saving ? 'Desant...' : 'Desar canvis'}</Button>
        {saved && !saving && <span className="text-xs text-green-600">Desat</span>}
      </div>
    </form>
  );
}

const TIPUS_LABELS = {
  nou: 'Discos nous (règim general)',
  segona_ma: 'Discos 2a mà (REBU — marge)',
};

function TipusIvaPanel() {
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

  async function toggleActiu(t) {
    await authFetch(`/admin/tipus-iva/${t.id}`, { method: 'PATCH', body: JSON.stringify({ actiu: !t.actiu }) });
    load();
  }

  async function marcarDefecte(t, camp) {
    await authFetch(`/admin/tipus-iva/${t.id}`, { method: 'PATCH', body: JSON.stringify({ [camp]: true }) });
    load();
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-500 max-w-xl">
          Configura els percentatges d'IVA. Marca quin tipus s'aplica per defecte a les vendes de
          discos nous i quin a les de 2a mà (REBU) — a compra es tria sempre a mà.
        </p>
        <Button onClick={() => { setEdit(null); setShowForm(true); }}>
          <Plus size={16} /> Nou tipus
        </Button>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">Carregant...</div>
        ) : tipus.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">Cap tipus d'IVA configurat</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
              <tr>
                <th className="px-4 py-3 text-left font-medium">Nom</th>
                <th className="px-4 py-3 text-right font-medium">%</th>
                <th className="px-4 py-3 text-center font-medium">REBU</th>
                <th className="px-4 py-3 text-center font-medium">Per defecte: nou</th>
                <th className="px-4 py-3 text-center font-medium">Per defecte: 2a mà</th>
                <th className="px-4 py-3 text-center font-medium">Actiu</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {tipus.map(t => (
                <tr key={t.id} className="hover:bg-zinc-50">
                  <td className="px-4 py-3 font-medium text-zinc-900">{t.nom}</td>
                  <td className="px-4 py-3 text-right">{parseFloat(t.percentatge).toFixed(2)}%</td>
                  <td className="px-4 py-3 text-center">{t.es_rebu ? 'Sí' : '—'}</td>
                  <td className="px-4 py-3 text-center">
                    {t.per_defecte_nou ? (
                      <Star size={16} className="inline text-amber-500 fill-amber-500" />
                    ) : (
                      <button onClick={() => marcarDefecte(t, 'per_defecte_nou')}
                        className="text-xs text-zinc-400 hover:text-zinc-700 underline">Fer servir</button>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {t.per_defecte_segona_ma ? (
                      <Star size={16} className="inline text-amber-500 fill-amber-500" />
                    ) : (
                      <button onClick={() => marcarDefecte(t, 'per_defecte_segona_ma')}
                        className="text-xs text-zinc-400 hover:text-zinc-700 underline">Fer servir</button>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button onClick={() => toggleActiu(t)}
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${t.actiu ? 'bg-green-100 text-green-700' : 'bg-zinc-100 text-zinc-500'}`}>
                      {t.actiu ? 'Actiu' : 'Inactiu'}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => { setEdit(t); setShowForm(true); }}
                      className="text-xs text-zinc-400 hover:text-zinc-700 font-medium px-2 py-1 rounded hover:bg-zinc-100">
                      Editar
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
  const isEdit = !!tipus;
  const [nom, setNom] = useState(tipus?.nom || '');
  const [percentatge, setPercentatge] = useState(tipus?.percentatge || '21.00');
  const [esRebu, setEsRebu] = useState(tipus?.es_rebu || false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    const payload = { nom, percentatge: parseFloat(percentatge), es_rebu: esRebu };
    const url = isEdit ? `/admin/tipus-iva/${tipus.id}` : '/admin/tipus-iva';
    const method = isEdit ? 'PATCH' : 'POST';
    const r = await authFetch(url, { method, body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json()).detail || 'Error desant');
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">{isEdit ? 'Editar tipus d\'IVA' : 'Nou tipus d\'IVA'}</h3>
        </div>
        <form onSubmit={save} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">Nom *</label>
            <input value={nom} onChange={e => setNom(e.target.value)} required
              placeholder="General 21%, REBU 2a mà..."
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">Percentatge *</label>
            <input type="number" step="0.01" value={percentatge} onChange={e => setPercentatge(e.target.value)} required
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <label className="flex items-center gap-2 text-sm text-zinc-700">
            <input type="checkbox" checked={esRebu} onChange={e => setEsRebu(e.target.checked)} />
            Règim especial de béns usats (REBU) — l'IVA es calcula sobre el marge, no sobre el preu
          </label>
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>Cancel·lar</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Desant...' : isEdit ? 'Desar canvis' : 'Crear'}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}

function MargesPanel() {
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
    await authFetch(`/admin/marges/${m.id}`, { method: 'PATCH', body: JSON.stringify({ actiu: !m.actiu }) });
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
          Configura els marges de benefici. El de per defecte segons condició (nou / 2a mà)
          es fa servir per suggerir el preu de venda a la recepció de compres — sempre editable a mà allà.
        </p>
        <Button onClick={() => { setEdit(null); setShowForm(true); }}>
          <Plus size={16} /> Nou marge
        </Button>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">Carregant...</div>
        ) : marges.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">Cap marge configurat</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
              <tr>
                <th className="px-4 py-3 text-left font-medium">Nom</th>
                <th className="px-4 py-3 text-right font-medium">%</th>
                <th className="px-4 py-3 text-center font-medium">Per defecte: nou</th>
                <th className="px-4 py-3 text-center font-medium">Per defecte: 2a mà</th>
                <th className="px-4 py-3 text-center font-medium">Actiu</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {marges.map(m => (
                <tr key={m.id} className="hover:bg-zinc-50">
                  <td className="px-4 py-3 font-medium text-zinc-900">{m.nom}</td>
                  <td className="px-4 py-3 text-right">{parseFloat(m.percentatge).toFixed(2)}%</td>
                  <td className="px-4 py-3 text-center">
                    {m.per_defecte_nou ? (
                      <Star size={16} className="inline text-amber-500 fill-amber-500" />
                    ) : (
                      <button onClick={() => marcarDefecte(m, 'per_defecte_nou')}
                        className="text-xs text-zinc-400 hover:text-zinc-700 underline">Fer servir</button>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {m.per_defecte_segona_ma ? (
                      <Star size={16} className="inline text-amber-500 fill-amber-500" />
                    ) : (
                      <button onClick={() => marcarDefecte(m, 'per_defecte_segona_ma')}
                        className="text-xs text-zinc-400 hover:text-zinc-700 underline">Fer servir</button>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button onClick={() => toggleActiu(m)}
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${m.actiu ? 'bg-green-100 text-green-700' : 'bg-zinc-100 text-zinc-500'}`}>
                      {m.actiu ? 'Actiu' : 'Inactiu'}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => { setEdit(m); setShowForm(true); }}
                      className="text-xs text-zinc-400 hover:text-zinc-700 font-medium px-2 py-1 rounded hover:bg-zinc-100">
                      Editar
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
  const isEdit = !!marge;
  const [nom, setNom] = useState(marge?.nom || '');
  const [percentatge, setPercentatge] = useState(marge?.percentatge || '40.00');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    const payload = { nom, percentatge: parseFloat(percentatge) };
    const url = isEdit ? `/admin/marges/${marge.id}` : '/admin/marges';
    const method = isEdit ? 'PATCH' : 'POST';
    const r = await authFetch(url, { method, body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json()).detail || 'Error desant');
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">{isEdit ? 'Editar marge' : 'Nou marge'}</h3>
        </div>
        <form onSubmit={save} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">Nom *</label>
            <input value={nom} onChange={e => setNom(e.target.value)} required
              placeholder="Marge estàndard nou, marge col·leccionista..."
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">Percentatge *</label>
            <input type="number" step="0.01" value={percentatge} onChange={e => setPercentatge(e.target.value)} required
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>Cancel·lar</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Desant...' : isEdit ? 'Desar canvis' : 'Crear'}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}

const FORMATS_DISPONIBLES = ['LP', 'EP', '7"', '12"', 'CD', 'Cassette', 'Altre'];

function PesFormatPanel() {
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
    if (!confirm(`Eliminar el pes configurat per a "${p.formato}"?`)) return;
    await authFetch(`/admin/pes-format/${p.id}`, { method: 'DELETE' });
    load();
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-500 max-w-xl">
          Pes per defecte segons el format del disc: s&apos;usa per calcular el pes total
          d&apos;una comanda (i per tant el tram d&apos;enviament) quan una còpia no té un pes
          propi indicat al catàleg. Un LP no pesa el mateix que un CD o un 7&quot;.
        </p>
        <Button onClick={() => { setEdit(null); setShowForm(true); }}>
          <Plus size={16} /> Nou format
        </Button>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">Carregant...</div>
        ) : pesos.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">
            Cap format configurat — s&apos;usarà un pes genèric per defecte.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
              <tr>
                <th className="px-4 py-3 text-left font-medium">Format</th>
                <th className="px-4 py-3 text-right font-medium">Pes</th>
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
                        Editar
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
    else setError((await r.json()).detail || 'Error desant');
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">{isEdit ? 'Editar pes' : 'Nou pes per format'}</h3>
        </div>
        <form onSubmit={save} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">Format *</label>
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
            <label className="block text-sm font-medium text-zinc-700 mb-1">Pes (grams) *</label>
            <input type="number" min="1" value={pesG} onChange={e => setPesG(e.target.value)} required
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>Cancel·lar</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Desant...' : isEdit ? 'Desar canvis' : 'Crear'}</Button>
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
      body: JSON.stringify({ ...s, nom_es: s.nom_es || '', activa: !s.activa }),
    });
    load();
  }

  async function eliminar(s) {
    if (!confirm(`Eliminar la cubeta "${s.nom_ca}"? Els discos que hi eren assignats quedaran sense classificar.`)) return;
    await authFetch(`/admin/seccions/${s.id}`, { method: 'DELETE' });
    load();
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-500 max-w-xl">
          Cubetes físiques de la botiga (Nacional, Internacional, Alternatiu...). Cada disc pot
          viure en una sola cubeta — s&apos;assigna des de la fitxa del disc — i determinen les
          files del mode &quot;Remena&quot; del catàleg públic.
        </p>
        <Button onClick={() => { setEdit(null); setShowForm(true); }}>
          <Plus size={16} /> Nova cubeta
        </Button>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">Carregant...</div>
        ) : seccions.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">
            Encara no hi ha cap cubeta configurada. Crea&apos;n una!
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
              <tr>
                <th className="px-4 py-3 text-left font-medium">Cubeta</th>
                <th className="px-4 py-3 text-left font-medium">Slug</th>
                <th className="px-4 py-3 text-left font-medium">Castellà</th>
                <th className="px-4 py-3 text-center font-medium">Posició</th>
                <th className="px-4 py-3 text-center font-medium">Activa</th>
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
                      {s.nom_ca}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-zinc-500 text-xs">{s.slug}</td>
                  <td className="px-4 py-3 text-zinc-500">{s.nom_es || '—'}</td>
                  <td className="px-4 py-3 text-center text-zinc-500">{s.posicio}</td>
                  <td className="px-4 py-3 text-center">
                    <button onClick={() => toggleActiva(s)}
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${s.activa ? 'bg-green-100 text-green-700' : 'bg-zinc-100 text-zinc-500'}`}>
                      {s.activa ? 'Activa' : 'Inactiva'}
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
  const isEdit = !!seccio;
  const [slug, setSlug] = useState(seccio?.slug || '');
  const [nomCa, setNomCa] = useState(seccio?.nom_ca || '');
  const [nomEs, setNomEs] = useState(seccio?.nom_es || '');
  const [color, setColor] = useState(seccio?.color || '#f59e0b');
  const [posicio, setPosicio] = useState(seccio?.posicio ?? 0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function save(e) {
    e.preventDefault();
    if (!slug || !nomCa) { setError('Slug i nom en català són obligatoris'); return; }
    setSaving(true);
    setError('');
    const payload = { slug, nom_ca: nomCa, nom_es: nomEs || null, color, activa: seccio?.activa ?? true, posicio: Number(posicio) };
    const url = isEdit ? `/admin/seccions/${seccio.id}` : '/admin/seccions';
    const method = isEdit ? 'PATCH' : 'POST';
    const r = await authFetch(url, { method, body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json()).detail || 'Error desant');
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">{isEdit ? 'Editar cubeta' : 'Nova cubeta'}</h3>
        </div>
        <form onSubmit={save} className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">Slug *</label>
              <input value={slug} onChange={e => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, '-'))}
                placeholder="nacional" required
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">Posició</label>
              <input type="number" value={posicio} onChange={e => setPosicio(e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">Nom català *</label>
            <input value={nomCa} onChange={e => setNomCa(e.target.value)} placeholder="Nacional" required
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">Nom castellà</label>
            <input value={nomEs} onChange={e => setNomEs(e.target.value)} placeholder="Nacional"
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-2">Color</label>
            <div className="flex items-center gap-2 flex-wrap">
              {SECCIO_COLORS.map(c => (
                <button type="button" key={c} onClick={() => setColor(c)}
                  className={`w-7 h-7 rounded-full transition-transform ${color === c ? 'ring-2 ring-offset-2 ring-zinc-400 scale-110' : ''}`}
                  style={{ backgroundColor: c }} />
              ))}
              <input type="color" value={color} onChange={e => setColor(e.target.value)}
                className="w-7 h-7 rounded-full border border-zinc-200 cursor-pointer" title="Color personalitzat" />
              <span className="ml-2 inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold text-white"
                style={{ backgroundColor: color }}>
                {nomCa || 'Previsualització'}
              </span>
            </div>
          </div>
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>Cancel·lar</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Desant...' : isEdit ? 'Desar canvis' : 'Crear'}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}

function TramsEnviamentPanel() {
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

  async function toggleActiu(t) {
    await authFetch(`/admin/trams-enviament/${t.id}`, { method: 'PATCH', body: JSON.stringify({ actiu: !t.actiu }) });
    load();
  }

  async function eliminar(t) {
    if (!confirm(`Eliminar el tram fins a ${t.pes_maxim_g} g?`)) return;
    await authFetch(`/admin/trams-enviament/${t.id}`, { method: 'DELETE' });
    load();
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-500 max-w-xl">
          Tarifa pròpia d&apos;enviament per país i tram de pes: cada comanda es cobra
          amb el tram actiu més barat del país de destí que cobreixi el pes total dels
          discos. Es fa servir quan el client tria &quot;Enviament&quot; al checkout;
          la recollida a botiga sempre és gratuïta. Un país només és venedor si té
          algun tram actiu — per vendre a un país nou, només cal afegir-hi un tram aquí.
        </p>
        <Button onClick={() => { setEdit(null); setShowForm(true); }}>
          <Plus size={16} /> Nou tram
        </Button>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">Carregant...</div>
        ) : trams.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">
            Cap tram configurat — sense trams no es pot triar &quot;Enviament&quot; a cap país al checkout.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
              <tr>
                <th className="px-4 py-3 text-left font-medium">País</th>
                <th className="px-4 py-3 text-left font-medium">Fins a (pes)</th>
                <th className="px-4 py-3 text-right font-medium">Preu</th>
                <th className="px-4 py-3 text-center font-medium">Actiu</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {trams.map(t => (
                <tr key={t.id} className="hover:bg-zinc-50">
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-zinc-100 text-zinc-600">
                      {t.pais}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-medium text-zinc-900">
                    {t.pes_maxim_g >= 1000 ? `${(t.pes_maxim_g / 1000).toFixed(2).replace(/\.?0+$/, '')} kg` : `${t.pes_maxim_g} g`}
                  </td>
                  <td className="px-4 py-3 text-right">{parseFloat(t.preu).toFixed(2)} €</td>
                  <td className="px-4 py-3 text-center">
                    <button onClick={() => toggleActiu(t)}
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${t.actiu ? 'bg-green-100 text-green-700' : 'bg-zinc-100 text-zinc-500'}`}>
                      {t.actiu ? 'Actiu' : 'Inactiu'}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-1">
                      <button onClick={() => { setEdit(t); setShowForm(true); }}
                        className="text-xs text-zinc-400 hover:text-zinc-700 font-medium px-2 py-1 rounded hover:bg-zinc-100">
                        Editar
                      </button>
                      <button onClick={() => eliminar(t)}
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
  const isEdit = !!tram;
  const [pesMaxim, setPesMaxim] = useState(tram?.pes_maxim_g ?? '');
  const [preu, setPreu] = useState(tram?.preu || '');
  const [pais, setPais] = useState(tram?.pais || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    const payload = { pes_maxim_g: Number(pesMaxim), preu: parseFloat(preu), pais: pais.trim().toUpperCase() };
    const url = isEdit ? `/admin/trams-enviament/${tram.id}` : '/admin/trams-enviament';
    const method = isEdit ? 'PATCH' : 'POST';
    const r = await authFetch(url, { method, body: JSON.stringify(payload) });
    setSaving(false);
    if (r.ok) onSaved();
    else setError((await r.json()).detail || 'Error desant');
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="px-6 py-4 border-b border-zinc-200">
          <h3 className="text-lg font-bold text-zinc-900">{isEdit ? 'Editar tram' : 'Nou tram'}</h3>
        </div>
        <form onSubmit={save} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">Pes màxim (grams) *</label>
            <input type="number" min="1" value={pesMaxim} onChange={e => setPesMaxim(e.target.value)} required
              placeholder="500"
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            <p className="text-xs text-zinc-400 mt-1">
              Aquest tram s&apos;aplica a comandes de fins a aquest pes (inclusiu).
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">Preu *</label>
            <input type="number" step="0.01" min="0" value={preu} onChange={e => setPreu(e.target.value)} required
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-1">País *</label>
            <input type="text" maxLength={2} value={pais} onChange={e => setPais(e.target.value.toUpperCase())} required
              placeholder="ES, FR, IT…"
              className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm uppercase focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            <p className="text-xs text-zinc-400 mt-1">
              Codi de 2 lletres (ISO 3166-1). Un país només és venedor si té algun tram actiu:
              per afegir-hi un de nou, crea aquí el primer tram amb el seu codi.
            </p>
          </div>
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>Cancel·lar</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Desant...' : isEdit ? 'Desar canvis' : 'Crear'}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}
