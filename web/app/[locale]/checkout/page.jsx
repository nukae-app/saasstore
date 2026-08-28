'use client';

import { Link } from '../../../i18n/navigation';
import Image from 'next/image';
import { useLocale, useTranslations } from 'next-intl';
import { useState, useEffect } from 'react';
import { Check, ChevronRight, CreditCard, Loader2, Package, Store, Timer } from 'lucide-react';
import { useCart } from '../../../components/store/CartProvider';
import { useAuth, authFetch } from '../../../components/store/AuthProvider';
import StorefrontNav from '../../../components/store/StorefrontNav';
import StorefrontFooter from '../../../components/store/StorefrontFooter';
import { useTenantConfig } from '../../../components/store/useTenantConfig';

// Redirige el navegador a Redsys con un POST real (Ds_MerchantParameters no
// cabe en una URL y Redsys exige POST): se construye un <form> oculto y se
// envía, no hay respuesta que gestionar aquí, el navegador navega fuera.
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

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function StepIndicator({ current }) {
  const t = useTranslations('checkout');
  const STEPS = [t('stepCart'), t('stepDetails'), t('stepConfirm')];
  return (
    <div className="flex items-center gap-2 mb-10">
      {STEPS.map((label, i) => (
        <div key={label} className="flex items-center gap-2">
          <div className={`flex items-center justify-center w-7 h-7 rounded-full text-xs font-semibold border ${
            i < current ? 'bg-zinc-900 border-zinc-900 text-white' :
            i === current ? 'border-zinc-900 text-zinc-900 bg-zinc-100' :
            'border-zinc-200 text-zinc-500'
          }`}>
            {i < current ? <Check size={12} /> : i + 1}
          </div>
          <span className={`text-sm ${i === current ? 'font-medium text-zinc-900' : 'text-zinc-500'}`}>
            {label}
          </span>
          {i < STEPS.length - 1 && <ChevronRight size={14} className="text-zinc-300 ml-1" />}
        </div>
      ))}
    </div>
  );
}

// Cuenta atrás visible de la reserva de stock (~20 min, `minutos_reserva` en
// la respuesta de /checkout/start): solo informativa, quien decide de verdad
// si el ejemplar sigue reservado es el backend (ver 409 en handleConfirm).
function ReservationCountdown({ startedAt, minutes }) {
  const t = useTranslations('checkout');
  const [remainingMs, setRemainingMs] = useState(() => startedAt + minutes * 60_000 - Date.now());

  useEffect(() => {
    const deadline = startedAt + minutes * 60_000;
    const tick = () => setRemainingMs(deadline - Date.now());
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startedAt, minutes]);

  if (remainingMs <= 0) {
    return (
      <p className="flex items-center gap-1.5 text-xs text-red-500 font-medium mb-6">
        <Timer size={13} /> {t('reservationExpired')}
      </p>
    );
  }

  const totalSeconds = Math.ceil(remainingMs / 1000);
  const mm = String(Math.floor(totalSeconds / 60)).padStart(2, '0');
  const ss = String(totalSeconds % 60).padStart(2, '0');

  return (
    <p className="flex items-center gap-1.5 text-xs text-zinc-500 mb-6">
      <Timer size={13} /> {t('itemsReservedFor', { mm, ss })}
    </p>
  );
}

export default function CheckoutPage() {
  const locale = useLocale();
  const t = useTranslations('checkout');
  const tCountries = useTranslations('checkout.countries');
  const tenantConfig = useTenantConfig();
  const { items, total, refresh } = useCart();
  const { user } = useAuth();
  const [step, setStep] = useState(0);
  const [reserving, setReserving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState('');
  const [orderId, setOrderId] = useState(null);
  const [savedAddresses, setSavedAddresses] = useState([]);
  const [reservedAt, setReservedAt] = useState(null);
  const [reservaMinutes, setReservaMinutes] = useState(20);
  const [costeEnviament, setCosteEnviament] = useState(0);
  const [paisosDisponibles, setPaisosDisponibles] = useState([]);

  useEffect(() => {
    if (user) {
      authFetch('/me/addresses').then(r => r.ok ? r.json() : []).then(setSavedAddresses).catch(() => {});
    }
  }, [user]);

  // Si l'usuari ja ha iniciat sessió, omple l'email automàticament. Cobreix
  // també el cas d'un reload directe a /checkout on `user` encara no s'ha
  // resolt en el moment del useState inicial; el guard `f.email ? f : ...`
  // evita trepitjar un email que un client convidat ja hagi escrit.
  useEffect(() => {
    if (user?.email) {
      setForm(f => (f.email ? f : { ...f, email: user.email }));
    }
  }, [user]);

  // Països a on avui es pot triar "Enviament" (depèn dels trams configurats
  // a l'admin, no d'una llista fixa aquí): si s'hi afegeix un país nou, el
  // desplegable el reflecteix sense tocar el frontend.
  useEffect(() => {
    fetch('/api/checkout/paisos-enviament', { credentials: 'include' })
      .then(res => (res.ok ? res.json() : null))
      .then(body => {
        if (!body?.paisos?.length) return;
        setPaisosDisponibles(body.paisos);
        setForm(f => (body.paisos.includes(f.pais) ? f : { ...f, pais: body.paisos[0] }));
      })
      .catch(() => {});
  }, []);

  const [form, setForm] = useState({
    email: user?.email || '',
    metodo_envio: 'envio',
    metodo_pago: 'redsys',
    nombre: '',
    linea1: '',
    ciudad: '',
    cp: '',
    provincia: '',
    pais: 'ES',
    telefono: '',
    notas: '',
  });

  function setField(key, val) {
    setForm(f => ({ ...f, [key]: val }));
  }

  // Preview del cost real (calculat al servidor a partir dels trams de pes
  // configurats a l'admin): recogida_tienda sempre 0, envio depèn del pes
  // total del carret. El cost que realment es cobra es recalcula igual a
  // /checkout/confirm, això és només perquè el client el vegi abans.
  useEffect(() => {
    if (items.length === 0) return;
    const params = new URLSearchParams({ metodo_envio: form.metodo_envio });
    if (form.metodo_envio === 'envio') params.set('pais', form.pais);
    fetch(`/api/checkout/coste-envio?${params}`, { credentials: 'include' })
      .then(res => (res.ok ? res.json() : null))
      .then(body => { if (body) setCosteEnviament(parseFloat(body.coste_envio)); })
      .catch(() => {});
  }, [form.metodo_envio, form.pais, items.length]);

  function handleStep1Submit(e) {
    e.preventDefault();
    if (!form.email || !EMAIL_RE.test(form.email)) {
      setError(t('invalidEmail'));
      return;
    }
    if (form.metodo_envio === 'envio' && (!form.nombre || !form.linea1 || !form.ciudad || !form.cp)) {
      setError(t('fillRequiredAddress'));
      return;
    }
    setError('');
    setStep(2);
  }

  async function handleReserve() {
    setReserving(true);
    setError('');
    try {
      const res = await fetch('/api/checkout/start', {
        method: 'POST',
        credentials: 'include',
      });
      if (res.ok) {
        const body = await res.json();
        setReservedAt(Date.now());
        setReservaMinutes(body.minutos_reserva || 20);
        setStep(1);
      } else if (res.status === 409) {
        const body = await res.json();
        const list = body.detail?.items?.join(', ') || '';
        setError(t('itemsNotAvailable', { list }));
        await refresh();
      } else if (res.status === 403) {
        setError(t('maintenanceError'));
      } else {
        setError(t('reserveError'));
      }
    } catch {
      setError(t('connectionError'));
    } finally {
      setReserving(false);
    }
  }

  async function handleConfirm() {
    setConfirming(true);
    setError('');
    try {
      const payload = {
        contact_email: form.email,
        shipping_method: form.metodo_envio,
        payment_method: form.metodo_envio === 'recogida_tienda' ? form.metodo_pago : 'redsys',
        notes: form.notas || null,
        shipping_address: form.metodo_envio === 'envio' ? {
          recipient_name: form.nombre,
          address_line1: form.linea1,
          city: form.ciudad,
          postal_code: form.cp,
          province: form.provincia || null,
          country: form.pais,
          phone: form.telefono || null,
        } : null,
        language: locale,
      };
      const res = await fetch('/api/checkout/confirm', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.detail || t('confirmError'));
        return;
      }
      const order = await res.json();
      await refresh();

      if (order.payment_method === 'tienda') {
        setOrderId(order.id);
        setStep(3);
        return;
      }

      // metodo_pago === 'redsys': iniciamos el pago y salimos hacia la
      // pasarela; el navegador ya no vuelve aquí (Redsys redirige a
      // /checkout/pago-ok o /checkout/pago-ko cuando termina).
      const payRes = await fetch(`/api/checkout/${order.id}/pay/redsys/start`, {
        method: 'POST',
        credentials: 'include',
      });
      if (!payRes.ok) {
        setError(t('paymentStartError'));
        return;
      }
      submitToRedsys(await payRes.json());
    } catch {
      setError(t('connectionError'));
    } finally {
      setConfirming(false);
    }
  }

  if (step === 3) {
    return (
      <>
        <StorefrontNav />
        <main className="flex-1 container py-16 max-w-lg text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <Check size={28} className="text-green-600" />
          </div>
          <h1 className="font-serif italic text-3xl mb-3">{t('orderReserved')}</h1>
          <p className="text-zinc-500 mb-2">
            {t('reference')}: <span className="font-mono text-zinc-700">{orderId?.toString().slice(0, 8).toUpperCase()}</span>
          </p>
          <p className="text-zinc-500 mb-8 text-sm">
            {t('pickupInstructions', { email: form.email, shopName: tenantConfig.nombre })}
          </p>
          <Link
            href="/cataleg"
            className="inline-flex items-center gap-2 bg-primary hover:bg-zinc-800 text-white px-6 py-3 rounded-full font-medium text-sm transition-colors"
          >
            {t('continueExploring')}
          </Link>
        </main>
        <StorefrontFooter />
      </>
    );
  }

  return (
    <>
      <StorefrontNav />

      <main className="flex-1 container py-10 max-w-2xl">
        <h1 className="font-serif italic text-3xl mb-2">{t('checkoutTitle')}</h1>
        <StepIndicator current={step === 0 ? 0 : step === 1 ? 1 : 2} />

        {step >= 1 && step < 3 && reservedAt && (
          <ReservationCountdown startedAt={reservedAt} minutes={reservaMinutes} />
        )}

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="grid md:grid-cols-[1fr_260px] gap-8 items-start">
          <div>
            {/* Step 0: Review cart */}
            {step === 0 && (
              <div>
                <h2 className="font-medium mb-4">{t('reviewItems')}</h2>
                <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] divide-y divide-zinc-50">
                  {items.length === 0 ? (
                    <div className="p-8 text-center text-zinc-500">
                      <p className="mb-3">{t('cartEmpty')}</p>
                      <Link href="/cataleg" className="text-zinc-900 hover:underline text-sm">
                        {t('backToCatalog')}
                      </Link>
                    </div>
                  ) : (
                    items.map(item => (
                      <div key={item.item_id} className="flex items-center gap-3 px-4 py-3">
                        <div style={{ borderRadius: 'var(--radius-card, 4px)' }} className="relative w-10 h-10 bg-zinc-100 shrink-0 overflow-hidden">
                          {item.image_url && (
                            <Image src={item.image_url} alt="" fill sizes="40px" className="object-cover" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{item.artista}</p>
                          <p className="text-xs text-zinc-500 truncate font-serif italic">{item.title}</p>
                        </div>
                        <span className="text-sm font-semibold shrink-0">
                          {parseFloat(item.price).toFixed(2)} €
                        </span>
                      </div>
                    ))
                  )}
                </div>
                {items.length > 0 && (
                  <button
                    onClick={handleReserve}
                    disabled={reserving}
                    className="mt-6 w-full flex items-center justify-center gap-2 bg-primary hover:bg-zinc-800 text-white px-6 py-3.5 rounded-full font-medium text-sm transition-colors disabled:opacity-60"
                  >
                    {reserving ? <Loader2 size={16} className="animate-spin" /> : null}
                    {reserving ? t('reserving') : t('reserveAndContinue')}
                  </button>
                )}
              </div>
            )}

            {/* Step 1: Form */}
            {step === 1 && (
              <form onSubmit={handleStep1Submit} className="space-y-5">
                <h2 className="font-medium">{t('contactDetails')}</h2>

                <div>
                  <label className="block text-sm font-medium text-zinc-700 mb-1.5">
                    Email <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="email"
                    required
                    value={form.email}
                    onChange={e => setField('email', e.target.value)}
                    placeholder="tu@exemple.com"
                    className="w-full border border-zinc-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-zinc-700 mb-2">
                    {t('deliveryMethod')} <span className="text-red-400">*</span>
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { value: 'envio', label: t('shipping'), icon: Package, sub: t('postalMail') },
                      { value: 'recogida_tienda', label: t('pickup'), icon: Store, sub: 'Pujades 113' },
                    ].map(({ value, label, icon: Icon, sub }) => (
                      <button
                        key={value}
                        type="button"
                        onClick={() => setForm(f => ({
                          ...f,
                          metodo_envio: value,
                          // Pagar a la botiga només té sentit si es recull en persona
                          metodo_pago: value === 'envio' ? 'redsys' : f.metodo_pago,
                        }))}
                        className={`flex items-center gap-3 p-3.5 rounded-xl border text-left transition-colors ${
                          form.metodo_envio === value
                            ? 'border-zinc-900 bg-zinc-100'
                            : 'border-zinc-200 hover:border-zinc-300'
                        }`}
                      >
                        <Icon size={18} className={form.metodo_envio === value ? 'text-zinc-900' : 'text-zinc-500'} />
                        <div>
                          <p className="text-sm font-medium">{label}</p>
                          <p className="text-xs text-zinc-500">{sub}</p>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                {form.metodo_envio === 'recogida_tienda' && (
                  <div>
                    <label className="block text-sm font-medium text-zinc-700 mb-2">
                      {t('paymentMethod')} <span className="text-red-400">*</span>
                    </label>
                    <div className="grid grid-cols-2 gap-3">
                      {[
                        { value: 'redsys', label: t('card'), icon: CreditCard, sub: t('onlinePayment') },
                        { value: 'tienda', label: t('atTheShop'), icon: Store, sub: t('payOnPickup') },
                      ].map(({ value, label, icon: Icon, sub }) => (
                        <button
                          key={value}
                          type="button"
                          onClick={() => setField('metodo_pago', value)}
                          className={`flex items-center gap-3 p-3.5 rounded-xl border text-left transition-colors ${
                            form.metodo_pago === value
                              ? 'border-zinc-900 bg-zinc-100'
                              : 'border-zinc-200 hover:border-zinc-300'
                          }`}
                        >
                          <Icon size={18} className={form.metodo_pago === value ? 'text-zinc-900' : 'text-zinc-500'} />
                          <div>
                            <p className="text-sm font-medium">{label}</p>
                            <p className="text-xs text-zinc-500">{sub}</p>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {form.metodo_envio === 'envio' && (
                  <div className="space-y-4 border-t border-zinc-100 pt-4">
                    <h3 className="text-sm font-medium text-zinc-700">{t('shippingAddress')}</h3>

                    {savedAddresses.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-xs text-zinc-500">{t('savedAddresses')}:</p>
                        {savedAddresses.map(addr => (
                          <button
                            key={addr.id}
                            type="button"
                            onClick={() => setForm(f => ({
                              ...f,
                              nombre: addr.recipient_name,
                              linea1: addr.address_line1,
                              ciudad: addr.city,
                              cp: addr.postal_code,
                              provincia: addr.province || '',
                              pais: addr.country,
                              telefono: addr.phone || '',
                            }))}
                            className="w-full text-left px-3 py-2.5 rounded-lg border border-zinc-200 hover:border-zinc-400 hover:bg-zinc-50 transition-colors text-sm"
                          >
                            <p className="font-medium text-zinc-800">{addr.recipient_name}</p>
                            <p className="text-zinc-500 text-xs">{addr.address_line1}, {addr.postal_code} {addr.city}</p>
                          </button>
                        ))}
                        <div className="relative my-1">
                          <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-zinc-100" /></div>
                          <div className="relative flex justify-center text-xs text-zinc-500"><span className="bg-background px-2">{t('orEnterManually')}</span></div>
                        </div>
                      </div>
                    )}
                    {[
                      { key: 'nombre', label: t('recipientName'), required: true },
                      { key: 'linea1', label: t('address'), required: true, placeholder: t('addressPlaceholder') },
                      { key: 'ciudad', label: t('city'), required: true },
                      { key: 'cp', label: t('postalCode'), required: true },
                      { key: 'provincia', label: t('province') },
                    ].map(({ key, label, required, placeholder }) => (
                      <div key={key}>
                        <label className="block text-sm font-medium text-zinc-700 mb-1.5">
                          {label} {required && <span className="text-red-400">*</span>}
                        </label>
                        <input
                          type="text"
                          value={form[key]}
                          onChange={e => setField(key, e.target.value)}
                          placeholder={placeholder}
                          className="w-full border border-zinc-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
                        />
                      </div>
                    ))}
                    <div>
                      <label className="block text-sm font-medium text-zinc-700 mb-1.5">
                        {t('country')} <span className="text-red-400">*</span>
                      </label>
                      <select
                        value={form.pais}
                        onChange={e => setField('pais', e.target.value)}
                        disabled={paisosDisponibles.length === 0}
                        className="w-full border border-zinc-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white"
                      >
                        {paisosDisponibles.map(code => (
                          <option key={code} value={code}>{tCountries.has(code) ? tCountries(code) : code}</option>
                        ))}
                      </select>
                      <p className="text-xs text-zinc-400 mt-1">
                        {t('shipOnlyToTheseCountries')}
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-zinc-700 mb-1.5">{t('phone')}</label>
                      <input
                        type="text"
                        value={form.telefono}
                        onChange={e => setField('telefono', e.target.value)}
                        placeholder={t('phoneForCarrier')}
                        className="w-full border border-zinc-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
                      />
                    </div>
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-zinc-700 mb-1.5">
                    {t('notesOptional')}
                  </label>
                  <textarea
                    rows={2}
                    value={form.notas}
                    onChange={e => setField('notas', e.target.value)}
                    placeholder={t('notesPlaceholder')}
                    className="w-full border border-zinc-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 resize-none"
                  />
                </div>

                <button
                  type="submit"
                  className="w-full bg-primary hover:bg-zinc-800 text-white px-6 py-3.5 rounded-full font-medium text-sm transition-colors"
                >
                  {t('reviewOrder')}
                </button>
              </form>
            )}

            {/* Step 2: Confirm */}
            {step === 2 && (
              <div>
                <h2 className="font-medium mb-4">{t('confirmOrder')}</h2>

                <div className="bg-zinc-50 rounded-xl p-4 text-sm space-y-2 mb-6">
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Email</span>
                    <span className="font-medium">{form.email}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-500">{t('delivery')}</span>
                    <span className="font-medium">
                      {form.metodo_envio === 'envio' ? t('postalShipping') : t('storePickup')}
                    </span>
                  </div>
                  {form.metodo_envio === 'envio' && (
                    <div className="flex justify-between">
                      <span className="text-zinc-500">{t('address')}</span>
                      <span className="font-medium text-right">
                        {form.nombre}<br />
                        {form.linea1}, {form.cp} {form.ciudad}
                      </span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-zinc-500">{t('payment')}</span>
                    <span className="font-medium">
                      {form.metodo_envio === 'recogida_tienda' && form.metodo_pago === 'tienda'
                        ? t('atShopOnPickup')
                        : t('cardRedsys')}
                    </span>
                  </div>
                  {form.notas && (
                    <div className="flex justify-between">
                      <span className="text-zinc-500">{t('notes')}</span>
                      <span className="font-medium text-right max-w-[200px]">{form.notas}</span>
                    </div>
                  )}
                  <div className="flex justify-between pt-2 border-t border-zinc-200">
                    <span className="text-zinc-500">{t('shipping')}</span>
                    <span className="font-medium">
                      {form.metodo_envio === 'recogida_tienda' ? t('free') : `${costeEnviament.toFixed(2)} €`}
                    </span>
                  </div>
                  <div className="flex justify-between font-semibold">
                    <span>{t('total')}</span>
                    <span>{(parseFloat(total || 0) + (form.metodo_envio === 'recogida_tienda' ? 0 : costeEnviament)).toFixed(2)} €</span>
                  </div>
                </div>

                <div className="bg-zinc-100 border border-zinc-200 rounded-xl p-4 text-sm text-zinc-800 mb-6">
                  {form.metodo_envio === 'recogida_tienda' && form.metodo_pago === 'tienda' ? (
                    <><strong>{t('payAtShopLabel')}:</strong> {t('payAtShopExplanation')}</>
                  ) : (
                    <><strong>{t('cardPaymentLabel')}:</strong> {t('cardPaymentExplanation')}</>
                  )}
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={() => setStep(1)}
                    className="flex-1 border border-zinc-200 text-zinc-700 hover:bg-zinc-50 px-4 py-3 rounded-full font-medium text-sm transition-colors"
                  >
                    {t('edit')}
                  </button>
                  <button
                    onClick={handleConfirm}
                    disabled={confirming}
                    className="flex-2 flex items-center justify-center gap-2 bg-zinc-900 hover:bg-zinc-800 text-white px-6 py-3 rounded-full font-medium text-sm transition-colors disabled:opacity-60"
                  >
                    {confirming ? <Loader2 size={16} className="animate-spin" /> : null}
                    {confirming ? t('confirming') : t('confirmOrderButton')}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Order summary sidebar */}
          <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] p-5 sticky top-24">
            <h3 className="text-sm font-medium text-zinc-700 mb-3">{t('summary')}</h3>
            <div className="space-y-2 text-sm mb-4">
              {items.map(item => (
                <div key={item.item_id} className="flex justify-between gap-2">
                  <span className="text-zinc-500 truncate">{item.artista} — {item.title}</span>
                  <span className="shrink-0 font-medium">{parseFloat(item.price).toFixed(2)} €</span>
                </div>
              ))}
            </div>
            <div className="border-t border-zinc-100 pt-3 space-y-1.5">
              <div className="flex justify-between text-sm text-zinc-500">
                <span>{t('subtotal')}</span>
                <span>{parseFloat(total || 0).toFixed(2)} €</span>
              </div>
              <div className="flex justify-between text-sm text-zinc-500">
                <span>{t('shipping')}</span>
                <span>
                  {form.metodo_envio === 'recogida_tienda' ? t('free') : `${costeEnviament.toFixed(2)} €`}
                </span>
              </div>
              <div className="flex justify-between font-semibold text-zinc-900 pt-1">
                <span>{t('total')}</span>
                <span>{(parseFloat(total || 0) + (form.metodo_envio === 'recogida_tienda' ? 0 : costeEnviament)).toFixed(2)} €</span>
              </div>
            </div>
          </div>
        </div>
      </main>

      <StorefrontFooter />
    </>
  );
}
