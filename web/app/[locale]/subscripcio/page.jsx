'use client';

import { useEffect, useState } from 'react';
import { useRouter } from '../../../i18n/navigation';
import { useTranslations } from 'next-intl';
import { Check, Disc3, Loader2 } from 'lucide-react';
import { useAuth, authFetch } from '../../../components/store/AuthProvider';
import { useSubscripcionsActives } from '../../../components/store/useSubscripcionsActives';
import StorefrontNav from '../../../components/store/StorefrontNav';
import StorefrontFooter from '../../../components/store/StorefrontFooter';

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

const EMPTY_ADDR = { recipient_name: '', address_line1: '', address_line2: '', city: '', postal_code: '', province: '', country: 'ES', phone: '' };

export default function SubscripcioPage() {
  const t = useTranslations('subscripcio');
  const LABEL_PERIODICITAT = {
    1: t('everyMonth'), 2: t('every2Months'), 3: t('every3Months'), 6: t('every6Months'), 12: t('everyYear'),
  };
  const { user } = useAuth();
  const subscripcionsActives = useSubscripcionsActives();
  const router = useRouter();

  const [config, setConfig] = useState(null);
  const [addresses, setAddresses] = useState([]);
  const [generes, setGeneres] = useState([]);
  const [generesPreferits, setGeneresPreferits] = useState([]);
  const [periodicitat, setPeriodicitat] = useState(null);
  const [quantitat, setQuantitat] = useState(null);
  const [addressId, setAddressId] = useState('');
  const [novaAdreca, setNovaAdreca] = useState(EMPTY_ADDR);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (subscripcionsActives === false) return;
    fetch('/api/subscripcions/config').then(r => (r.ok ? r.json() : null)).then(d => {
      if (!d) return;
      setConfig(d);
      setPeriodicitat(d.periodicitats_mesos_disponibles[0]);
      setQuantitat(d.quantitats_disponibles[0]);
    });
    fetch('/api/subscripcions/generes').then(r => (r.ok ? r.json() : [])).then(setGeneres);
  }, [subscripcionsActives]);

  useEffect(() => {
    if (!user) return;
    authFetch('/me/addresses').then(r => r.json()).then(list => {
      setAddresses(list);
      const def = list.find(a => a.is_default) || list[0];
      if (def) setAddressId(def.id);
    });
  }, [user]);

  function toggleGenere(g) {
    setGeneresPreferits(s => (s.includes(g) ? s.filter(x => x !== g) : [...s, g]));
  }

  async function confirmar() {
    if (!user) {
      router.push('/login?next=/subscripcio');
      return;
    }
    setError('');
    setSubmitting(true);
    try {
      let finalAddressId = addressId;
      if (!finalAddressId) {
        if (!novaAdreca.recipient_name || !novaAdreca.address_line1 || !novaAdreca.city || !novaAdreca.postal_code) {
          setError(t('fillShippingAddress'));
          setSubmitting(false);
          return;
        }
        const rAddr = await authFetch('/me/addresses', { method: 'POST', body: JSON.stringify(novaAdreca) });
        if (!rAddr.ok) { setError(t('couldNotSaveAddress')); setSubmitting(false); return; }
        finalAddressId = (await rAddr.json()).id;
      }

      const r = await authFetch('/subscripcions/alta', {
        method: 'POST',
        body: JSON.stringify({
          periodicitat_mesos: periodicitat, quantitat, address_id: finalAddressId,
          generes_preferits: generesPreferits,
        }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        setError(d.detail || t('couldNotCompleteSignup'));
        setSubmitting(false);
        return;
      }
      const form = await r.json();
      submitToRedsys(form);
    } catch {
      setError(t('connectionError'));
      setSubmitting(false);
    }
  }

  if (subscripcionsActives === false) {
    return (
      <>
        <StorefrontNav />
        <main className="flex-1 container py-16 text-center text-zinc-500">{t('clubNotAvailable')}</main>
        <StorefrontFooter />
      </>
    );
  }

  const preuTotal = config && quantitat ? (parseFloat(config.preu_per_disc) * quantitat).toFixed(2) : null;

  return (
    <>
      <StorefrontNav />
      <main className="flex-1 container py-12 md:py-16 max-w-2xl">
        <div className="text-center mb-10">
          <Disc3 size={32} className="mx-auto text-zinc-300 mb-3" />
          <h1 className="font-serif italic text-4xl mb-3">{t('recordClub')}</h1>
          <p className="text-zinc-500 max-w-md mx-auto">
            {t('recordClubSubtitle')}
          </p>
        </div>

        {!config ? (
          <div className="py-12 flex justify-center"><Loader2 className="animate-spin text-zinc-400" /></div>
        ) : (
          <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] p-6 space-y-6">
            {generes.length > 0 && (
              <div>
                <p className="text-sm font-medium text-zinc-700 mb-2">{t('whatMusicInterestsYou')}</p>
                <p className="text-xs text-zinc-400 mb-2">{t('noGenreMarkedNote')}</p>
                <div className="flex flex-wrap gap-2">
                  {generes.map(g => (
                    <button key={g} type="button" onClick={() => toggleGenere(g)}
                      className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                        generesPreferits.includes(g) ? 'bg-zinc-900 text-white border-transparent' : 'border-zinc-200 text-zinc-600 hover:bg-zinc-50'
                      }`}
                    >
                      {g}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div>
              <p className="text-sm font-medium text-zinc-700 mb-2">{t('howOftenReceive')}</p>
              <div className="flex flex-wrap gap-2">
                {config.periodicitats_mesos_disponibles.map(m => (
                  <button key={m} type="button" onClick={() => setPeriodicitat(m)}
                    className={`px-4 py-2 rounded-full text-sm font-medium border transition-colors ${
                      periodicitat === m ? 'bg-zinc-900 text-white border-transparent' : 'border-zinc-200 text-zinc-600 hover:bg-zinc-50'
                    }`}>
                    {LABEL_PERIODICITAT[m] || t('everyNMonths', { n: m })}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <p className="text-sm font-medium text-zinc-700 mb-2">{t('howManyRecordsPerShipment')}</p>
              <div className="flex flex-wrap gap-2">
                {config.quantitats_disponibles.map(q => (
                  <button key={q} type="button" onClick={() => setQuantitat(q)}
                    className={`w-11 h-11 rounded-full text-sm font-medium border transition-colors ${
                      quantitat === q ? 'bg-zinc-900 text-white border-transparent' : 'border-zinc-200 text-zinc-600 hover:bg-zinc-50'
                    }`}>
                    {q}
                  </button>
                ))}
              </div>
            </div>

            {preuTotal && (
              <div className="border-t border-zinc-100 pt-4">
                <p className="text-sm text-zinc-500">{t('pricePerShipment')}</p>
                <p className="text-2xl font-serif italic">{preuTotal} €</p>
              </div>
            )}

            <div>
              <p className="text-sm font-medium text-zinc-700 mb-2">{t('shippingAddress')}</p>
              {addresses.length > 0 && (
                <select value={addressId} onChange={e => setAddressId(e.target.value)}
                  className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-zinc-900">
                  {addresses.map(a => (
                    <option key={a.id} value={a.id}>{a.recipient_name} — {a.address_line1}, {a.city}</option>
                  ))}
                  <option value="">{t('newAddressOption')}</option>
                </select>
              )}
              {!addressId && (
                <div className="grid grid-cols-2 gap-2">
                  <input placeholder={t('recipientName')} value={novaAdreca.recipient_name}
                    onChange={e => setNovaAdreca(a => ({ ...a, recipient_name: e.target.value }))}
                    className="col-span-2 border border-zinc-200 rounded-lg px-3 py-2 text-sm" />
                  <input placeholder={t('address')} value={novaAdreca.address_line1}
                    onChange={e => setNovaAdreca(a => ({ ...a, address_line1: e.target.value }))}
                    className="col-span-2 border border-zinc-200 rounded-lg px-3 py-2 text-sm" />
                  <input placeholder={t('postalCode')} value={novaAdreca.postal_code}
                    onChange={e => setNovaAdreca(a => ({ ...a, postal_code: e.target.value }))}
                    className="border border-zinc-200 rounded-lg px-3 py-2 text-sm" />
                  <input placeholder={t('city')} value={novaAdreca.city}
                    onChange={e => setNovaAdreca(a => ({ ...a, city: e.target.value }))}
                    className="border border-zinc-200 rounded-lg px-3 py-2 text-sm" />
                </div>
              )}
            </div>

            {error && <p className="text-red-500 text-sm">{error}</p>}

            <button onClick={confirmar} disabled={submitting}
              className="flex items-center gap-2 bg-primary hover:bg-zinc-800 text-white px-6 py-3 rounded-full font-medium text-sm transition-colors disabled:opacity-60">
              {submitting ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
              {submitting ? t('redirectingToPayment') : user ? t('confirmAndPay') : t('loginAndContinue')}
            </button>
          </div>
        )}
      </main>
      <StorefrontFooter />
    </>
  );
}
