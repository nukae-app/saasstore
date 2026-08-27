'use client';

import { useEffect, useState } from 'react';
import { useRouter } from '../../../../i18n/navigation';
import { useTranslations } from 'next-intl';
import { Bell, Plus, X, Check, Loader2, Truck, Store, Clock, CreditCard } from 'lucide-react';
import { authFetch } from '../../../../components/store/AuthProvider';
import NovaPeticioModal from '../../../../components/store/NovaPeticioModal';

function submitToRedsys({ url, Ds_SignatureVersion, Ds_MerchantParameters, Ds_Signature }) {
  const form = document.createElement('form');
  form.method = 'POST';
  form.action = url;
  for (const [name, value] of Object.entries({ Ds_SignatureVersion, Ds_MerchantParameters, Ds_Signature })) {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = name;
    input.value = value;
    form.appendChild(input);
  }
  document.body.appendChild(form);
  form.submit();
}

async function iniciarPagamentRedsys(orderId) {
  const r = await authFetch(`/checkout/${orderId}/pay/redsys/start`, { method: 'POST' });
  if (!r.ok) throw new Error('No s\'ha pogut iniciar el pagament.');
  submitToRedsys(await r.json());
}

const ESTAT_COLOR = {
  pendent: 'text-zinc-500 bg-zinc-100 border-zinc-200',
  pendent_acceptacio: 'text-amber-700 bg-amber-50 border-amber-200',
  acceptada: 'text-blue-700 bg-blue-50 border-blue-200',
  rebutjada: 'text-zinc-400 bg-zinc-100 border-zinc-200',
  en_tramit: 'text-blue-700 bg-blue-50 border-blue-200',
  reservada: 'text-green-700 bg-green-50 border-green-200',
  recollida: 'text-zinc-500 bg-zinc-100 border-zinc-200',
  caducada: 'text-red-600 bg-red-50 border-red-200',
  cancelada: 'text-zinc-400 bg-zinc-100 border-zinc-200',
};

function AddressPicker({ addresses, addressId, setAddressId, novaAdreca, setNovaAdreca }) {
  const t = useTranslations('peticions');
  const [mode, setMode] = useState(addresses.length > 0 ? 'existing' : 'nova');

  return (
    <div className="space-y-2 mb-4">
      <label className="block text-xs font-medium text-zinc-600">{t('shippingAddress')}</label>
      {addresses.length > 0 && (
        <div className="space-y-1.5">
          {addresses.map(a => (
            <label key={a.id}
              className={`flex items-start gap-2.5 p-2.5 rounded-lg border cursor-pointer text-sm transition-colors ${mode === 'existing' && addressId === a.id ? 'border-zinc-400 bg-zinc-100' : 'border-zinc-200 hover:border-zinc-300'}`}>
              <input type="radio" name="adreca" checked={mode === 'existing' && addressId === a.id}
                onChange={() => { setMode('existing'); setAddressId(a.id); }} className="mt-1 accent-zinc-900" />
              <span className="text-zinc-700">
                {a.recipient_name} — {a.address_line1}, {a.postal_code} {a.city}
              </span>
            </label>
          ))}
          <label className={`flex items-center gap-2.5 p-2.5 rounded-lg border cursor-pointer text-sm transition-colors ${mode === 'nova' ? 'border-zinc-400 bg-zinc-100' : 'border-zinc-200 hover:border-zinc-300'}`}>
            <input type="radio" name="adreca" checked={mode === 'nova'}
              onChange={() => setMode('nova')} className="accent-zinc-900" />
            <span className="text-zinc-700">{t('newAddress')}</span>
          </label>
        </div>
      )}
      {mode === 'nova' && (
        <div className="grid grid-cols-2 gap-2 pt-1">
          <input placeholder={t('recipientName')} value={novaAdreca.recipient_name}
            onChange={e => setNovaAdreca(f => ({ ...f, recipient_name: e.target.value }))}
            className="col-span-2 border border-zinc-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          <input placeholder={t('address')} value={novaAdreca.address_line1}
            onChange={e => setNovaAdreca(f => ({ ...f, address_line1: e.target.value }))}
            className="col-span-2 border border-zinc-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          <input placeholder={t('postalCode')} value={novaAdreca.postal_code}
            onChange={e => setNovaAdreca(f => ({ ...f, postal_code: e.target.value }))}
            className="border border-zinc-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          <input placeholder={t('city')} value={novaAdreca.city}
            onChange={e => setNovaAdreca(f => ({ ...f, city: e.target.value }))}
            className="border border-zinc-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          <input placeholder={t('phoneOptional')} value={novaAdreca.phone}
            onChange={e => setNovaAdreca(f => ({ ...f, phone: e.target.value }))}
            className="col-span-2 border border-zinc-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
        </div>
      )}
    </div>
  );
}

function AcceptarModal({ peticion, onClose, onSaved }) {
  const t = useTranslations('peticions');
  const [metode, setMetode] = useState('envio');
  const [addresses, setAddresses] = useState([]);
  const [addressId, setAddressId] = useState(null);
  const [novaAdreca, setNovaAdreca] = useState({ recipient_name: '', address_line1: '', postal_code: '', city: '', phone: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    authFetch('/me/addresses').then(r => r.ok ? r.json() : []).then(list => {
      setAddresses(list);
      const predet = list.find(a => a.is_default) || list[0];
      if (predet) setAddressId(predet.id);
    });
  }, []);

  async function handleAccept() {
    setSaving(true);
    setError('');
    try {
      const payload = { metodo_entrega: metode };
      if (metode === 'envio') {
        if (addressId) payload.address_id = addressId;
        else payload.direccion_envio = { ...novaAdreca, country: 'ES' };
      }
      const res = await authFetch(`/me/peticiones/${peticion.id}/aceptar`, {
        method: 'POST', body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setError(d.detail || t('couldNotAccept'));
        return;
      }
      const updated = await res.json();
      if (updated.order_id && metode !== 'recollida_paga_botiga') {
        await iniciarPagamentRedsys(updated.order_id);
        return; // el navegador surt cap a Redsys
      }
      onSaved();
    } catch {
      setError(t('connectionError'));
    } finally {
      setSaving(false);
    }
  }

  const OPCIONS = [
    { value: 'envio', icon: Truck, label: t('shipHome'), desc: t('shipHomeDesc') },
    { value: 'recollida_paga_ara', icon: Store, label: t('pickupPayNow'), desc: t('pickupPayNowDesc') },
    { value: 'recollida_paga_botiga', icon: Clock, label: t('pickupPayAtShop'), desc: t('pickupPayAtShopDesc') },
  ];

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50 overflow-y-auto">
      <div className="bg-white rounded-xl max-w-md w-full p-6 my-8">
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-serif italic text-xl">{t('acceptRequest')}</h2>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600"><X size={18} /></button>
        </div>
        <p className="text-sm text-zinc-500 mb-4">
          {peticion.artista} — {peticion.titulo}: <span className="font-semibold text-zinc-800">{Number(peticion.estimated_price).toFixed(2)} €</span>
        </p>
        <div className="space-y-2 mb-4">
          {OPCIONS.map(({ value, icon: Icon, label, desc }) => (
            <label key={value}
              className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${metode === value ? 'border-zinc-400 bg-zinc-100' : 'border-zinc-200 hover:border-zinc-300'}`}>
              <input type="radio" name="metode" value={value} checked={metode === value}
                onChange={() => setMetode(value)} className="mt-1 accent-zinc-900" />
              <div className="flex-1">
                <div className="flex items-center gap-1.5 text-sm font-medium text-zinc-800"><Icon size={13} /> {label}</div>
                <p className="text-xs text-zinc-400 mt-0.5">{desc}</p>
              </div>
            </label>
          ))}
        </div>

        {metode === 'envio' && (
          <AddressPicker addresses={addresses} addressId={addressId} setAddressId={setAddressId}
            novaAdreca={novaAdreca} setNovaAdreca={setNovaAdreca} />
        )}

        {error && <p className="text-sm text-red-600 mb-3">{error}</p>}

        <div className="flex gap-2">
          <button onClick={handleAccept} disabled={saving}
            className="flex items-center gap-1.5 bg-primary hover:bg-zinc-800 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-60">
            {saving ? <Loader2 size={13} className="animate-spin" /> : metode === 'recollida_paga_botiga' ? <Check size={13} /> : <CreditCard size={13} />}
            {saving ? t('confirming') : metode === 'recollida_paga_botiga' ? t('confirm') : t('confirmAndPay')}
          </button>
          <button onClick={onClose}
            className="flex items-center gap-1.5 border border-zinc-200 text-zinc-600 px-4 py-2 rounded-lg text-sm hover:bg-zinc-50 transition-colors">
            {t('cancel')}
          </button>
        </div>
      </div>
    </div>
  );
}

function NoEsAquestModal({ peticion, onClose, onSaved }) {
  const t = useTranslations('peticions');
  const [comentari, setComentari] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const res = await authFetch(`/me/peticiones/${peticion.id}/no-es-aquest`, {
        method: 'POST', body: JSON.stringify({ comentari }),
      });
      if (res.ok) onSaved();
      else { const d = await res.json().catch(() => ({})); setError(d.detail || t('couldNotSend')); }
    } finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-xl max-w-md w-full p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-serif italic text-xl">{t('notTheRightRecord')}</h2>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600"><X size={18} /></button>
        </div>
        <p className="text-sm text-zinc-500 mb-4">
          {t('explainWhatYouWereLookingFor')}
        </p>
        <form onSubmit={handleSubmit} className="space-y-3">
          <textarea value={comentari} onChange={e => setComentari(e.target.value)} required rows={3}
            placeholder={t('correctionPlaceholder')}
            className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex gap-2 pt-1">
            <button type="submit" disabled={saving}
              className="flex items-center gap-1.5 bg-primary hover:bg-zinc-800 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-60">
              {saving ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
              {saving ? t('sendingEllipsis') : t('sendCorrection')}
            </button>
            <button type="button" onClick={onClose}
              className="flex items-center gap-1.5 border border-zinc-200 text-zinc-600 px-4 py-2 rounded-lg text-sm hover:bg-zinc-50 transition-colors">
              {t('cancel')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function PeticioCard({ p, onRefresh }) {
  const t = useTranslations('peticions');
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [showAccept, setShowAccept] = useState(false);
  const [showNoEsAquest, setShowNoEsAquest] = useState(false);
  const stColor = ESTAT_COLOR[p.status] || 'text-zinc-500 bg-zinc-100 border-zinc-200';
  const stLabel = t.has(`estat.${p.status}`) ? t(`estat.${p.status}`) : p.status;

  async function rebutjar() {
    setBusy(true);
    try {
      await authFetch(`/me/peticiones/${p.id}/rechazar`, { method: 'POST' });
      onRefresh();
    } finally { setBusy(false); }
  }

  async function cancelar() {
    setBusy(true);
    try {
      await authFetch(`/me/peticiones/${p.id}`, { method: 'DELETE' });
      onRefresh();
    } finally { setBusy(false); }
  }

  async function comprar() {
    setBusy(true);
    try {
      const res = await authFetch(`/me/peticiones/${p.id}/comprar`, { method: 'POST' });
      if (res.ok) router.push('/carret');
    } finally { setBusy(false); }
  }

  async function reintentarPagament() {
    setBusy(true);
    try {
      const res = await authFetch(`/me/peticiones/${p.id}/reintentar-pagament`, { method: 'POST' });
      if (res.ok) {
        const { order_id } = await res.json();
        await iniciarPagamentRedsys(order_id);
      }
    } finally { setBusy(false); }
  }

  return (
    <div className="bg-white shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] rounded-xl p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          {p.imagen_url ? (
            <img src={p.imagen_url} alt="" className="w-12 h-12 rounded-lg object-cover shrink-0 bg-zinc-100" />
          ) : (
            <div className="w-12 h-12 rounded-lg bg-zinc-100 flex items-center justify-center shrink-0">
              <Bell size={16} className="text-zinc-300" />
            </div>
          )}
          <div className="min-w-0">
            <p className="font-medium text-sm text-zinc-800 truncate">{p.titulo}</p>
            <p className="text-xs text-zinc-500 truncate">{p.artista}</p>
          </div>
        </div>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full border shrink-0 ${stColor}`}>{stLabel}</span>
      </div>

      {p.client_notes && <p className="text-xs text-zinc-400 mt-2">{p.client_notes}</p>}

      {p.status === 'pendent_acceptacio' && (
        <div className="flex items-center gap-2 mt-3">
          <span className="text-sm font-semibold text-zinc-900 mr-auto">{Number(p.estimated_price).toFixed(2)} €</span>
          <button onClick={() => setShowAccept(true)} disabled={busy}
            className="flex items-center gap-1.5 bg-primary hover:bg-zinc-800 text-white px-3 py-1.5 rounded-lg text-xs font-medium transition-colors disabled:opacity-60">
            {t('accept')}
          </button>
          <button onClick={rebutjar} disabled={busy}
            className="flex items-center gap-1.5 border border-zinc-200 text-zinc-600 px-3 py-1.5 rounded-lg text-xs hover:bg-zinc-50 transition-colors disabled:opacity-60">
            {t('reject')}
          </button>
        </div>
      )}
      {p.status === 'pendent_acceptacio' && (
        <button onClick={() => setShowNoEsAquest(true)} disabled={busy}
          className="text-xs text-zinc-400 hover:text-zinc-700 mt-2">
          {t('notTheRecordIWasLookingFor')}
        </button>
      )}

      {/* recollida_paga_botiga reservada/recollida ja no arriba aquí: es veu a "Les meves comandes" */}
      {p.status === 'reservada' && (
        <div className="mt-3">
          <button onClick={comprar} disabled={busy}
            className="flex items-center gap-1.5 bg-primary hover:bg-zinc-800 text-white px-3 py-1.5 rounded-lg text-xs font-medium transition-colors disabled:opacity-60">
            {busy ? <Loader2 size={12} className="animate-spin" /> : null}
            {t('buyNow')}
          </button>
        </div>
      )}

      {p.pagament_pendent && (
        <div className="mt-3 flex items-center gap-2">
          <p className="text-xs text-red-500 flex-1">{t('paymentNotCompleted')}</p>
          <button onClick={reintentarPagament} disabled={busy}
            className="flex items-center gap-1.5 bg-primary hover:bg-zinc-800 text-white px-3 py-1.5 rounded-lg text-xs font-medium transition-colors disabled:opacity-60">
            {busy ? <Loader2 size={12} className="animate-spin" /> : <CreditCard size={12} />}
            {t('retryPayment')}
          </button>
        </div>
      )}

      {(p.status === 'pendent' || p.status === 'pendent_acceptacio') && (
        <button onClick={cancelar} disabled={busy}
          className="text-xs text-zinc-400 hover:text-red-500 mt-3">
          {t('cancelRequest')}
        </button>
      )}

      {showAccept && (
        <AcceptarModal peticion={p} onClose={() => setShowAccept(false)}
          onSaved={() => { setShowAccept(false); onRefresh(); }} />
      )}
      {showNoEsAquest && (
        <NoEsAquestModal peticion={p} onClose={() => setShowNoEsAquest(false)}
          onSaved={() => { setShowNoEsAquest(false); onRefresh(); }} />
      )}
    </div>
  );
}

export default function PeticionsPage() {
  const t = useTranslations('peticions');
  const [peticiones, setPeticiones] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showNova, setShowNova] = useState(false);

  async function load() {
    const res = await authFetch('/me/peticiones');
    if (res.ok) setPeticiones(await res.json());
  }

  useEffect(() => { load().finally(() => setLoading(false)); }, []);

  return (
    <div className="max-w-2xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="font-serif italic text-2xl md:text-3xl">{t('myRequests')}</h1>
        <button onClick={() => setShowNova(true)}
          className="flex items-center gap-1.5 bg-primary hover:bg-zinc-800 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
          <Plus size={14} /> {t('cantFindItIWantIt')}
        </button>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2].map(i => <div key={i} className="animate-pulse bg-zinc-100 rounded-xl h-20" />)}
        </div>
      ) : peticiones.length === 0 ? (
        <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] p-10 text-center">
          <Bell size={32} className="text-zinc-200 mx-auto mb-3" />
          <p className="text-zinc-400 text-sm">{t('noRecordsRequestedYet')}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {peticiones.map(p => <PeticioCard key={p.id} p={p} onRefresh={load} />)}
        </div>
      )}

      {showNova && (
        <NovaPeticioModal onClose={() => setShowNova(false)}
          onSaved={() => { setShowNova(false); load(); }} />
      )}
    </div>
  );
}
