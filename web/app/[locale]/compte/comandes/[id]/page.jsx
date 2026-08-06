'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { Link } from '../../../../../i18n/navigation';
import { useTranslations, useLocale } from 'next-intl';
import { ArrowLeft, Package, MapPin, Loader2 } from 'lucide-react';
import { authFetch } from '../../../../../components/store/AuthProvider';

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

const STATUS_STEP = {
  pendiente_pago: 0, pagado: 1, enviado: 2, entregado: 3, cancelado: -1,
};
const STATUS_COLOR = {
  pendiente_pago: 'text-amber-700 bg-amber-50', pagado: 'text-blue-700 bg-blue-50',
  enviado: 'text-purple-700 bg-purple-50', entregado: 'text-green-700 bg-green-50',
  cancelado: 'text-zinc-500 bg-zinc-100',
};

export default function OrderDetailPage() {
  const t = useTranslations('compte');
  const locale = useLocale();
  const STEPS = [t('stepReceived'), t('stepPaymentConfirmed'), t('stepShipped'), t('stepDelivered')];
  const { id } = useParams();
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [paying, setPaying] = useState(false);

  async function retryPayment() {
    setPaying(true);
    try {
      const r = await authFetch(`/checkout/${id}/pay/redsys/start`, { method: 'POST' });
      if (r.ok) submitToRedsys(await r.json());
    } finally {
      setPaying(false);
    }
  }

  useEffect(() => {
    authFetch(`/me/orders/${id}`)
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(setOrder)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return (
    <div className="flex justify-center py-12">
      <Loader2 size={28} className="text-zinc-900 animate-spin" />
    </div>
  );

  if (error || !order) return (
    <div className="text-center py-12">
      <p className="text-zinc-400 mb-4">{t('orderNotFound')}</p>
      <Link href="/compte/comandes" className="text-zinc-900 hover:underline text-sm">{t('backToOrders')}</Link>
    </div>
  );

  const stStep = STATUS_STEP[order.status] ?? 0;
  const stColor = STATUS_COLOR[order.status] || 'text-zinc-500 bg-zinc-100';
  const stLabel = t.has(`orderStatus.${order.status}`) ? t(`orderStatus.${order.status}`) : order.status;
  const isCancelled = order.status === 'cancelado';

  return (
    <div className="space-y-6">
      <div>
        <Link href="/compte/comandes" className="inline-flex items-center gap-1.5 text-sm text-zinc-400 hover:text-zinc-700 mb-4 transition-colors">
          <ArrowLeft size={14} /> {t('allOrders')}
        </Link>
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="font-serif italic text-2xl">
              {t('orderNumber', { number: order.id.slice(0, 8).toUpperCase() })}
            </h1>
            <p className="text-sm text-zinc-400 mt-1">
              {new Date(order.created_at).toLocaleDateString(locale, { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
            </p>
          </div>
          <span className={`text-sm font-medium px-3 py-1.5 rounded-full ${stColor}`}>
            {stLabel}
          </span>
        </div>
      </div>

      {/* Progress tracker */}
      {!isCancelled && (
        <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] p-5">
          <div className="flex items-center justify-between gap-1">
            {STEPS.map((label, i) => {
              const done = stStep > i;
              const current = stStep === i;
              return (
                <div key={label} className="flex-1 flex flex-col items-center gap-1.5 text-center">
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold border-2 transition-colors ${
                    done ? 'bg-zinc-900 border-zinc-900 text-white' :
                    current ? 'border-zinc-900 text-zinc-900 bg-zinc-100' :
                    'border-zinc-200 text-zinc-300'
                  }`}>
                    {done ? '✓' : i + 1}
                  </div>
                  <p className={`text-[10px] leading-tight ${current ? 'font-semibold text-zinc-900' : done ? 'text-zinc-500' : 'text-zinc-300'}`}>
                    {label}
                  </p>
                  {i < STEPS.length - 1 && (
                    <div className="absolute" />
                  )}
                </div>
              );
            })}
          </div>
          {order.status === 'pendiente_pago' && (
            <div className="mt-4 pt-4 border-t border-zinc-50 text-xs text-amber-700 bg-amber-50 rounded-lg px-3 py-2.5 flex items-center justify-between gap-3 flex-wrap">
              {order.metodo_pago === 'tienda' ? (
                <span>{t('payOnPickupNote')}</span>
              ) : (
                <>
                  <span>{t('paymentNotCompletedYet')}</span>
                  <button
                    onClick={retryPayment}
                    disabled={paying}
                    className="inline-flex items-center gap-1.5 bg-amber-500 hover:bg-amber-600 text-white px-3 py-1.5 rounded-lg font-medium text-xs transition-colors disabled:opacity-60"
                  >
                    {paying && <Loader2 size={12} className="animate-spin" />}
                    {paying ? t('redirecting') : t('payNow')}
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {/* Items */}
      <div>
        <h2 className="font-medium text-sm text-zinc-500 uppercase tracking-wide mb-3">{t('items')}</h2>
        <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] divide-y divide-zinc-50">
          {order.items.map((item, i) => (
            <div key={i} className="flex items-center gap-4 px-5 py-4">
              <div className="w-12 h-12 rounded-lg bg-zinc-100 shrink-0 overflow-hidden flex items-center justify-center">
                {item.imagen_url ? (
                  <img src={item.imagen_url} alt="" className="w-full h-full object-cover" />
                ) : (
                  <svg viewBox="0 0 100 100" className="w-7 h-7 text-zinc-300" fill="currentColor">
                    <circle cx="50" cy="50" r="48"/><circle cx="50" cy="50" r="34" fill="#FAF9F6"/>
                    <circle cx="50" cy="50" r="14"/><circle cx="50" cy="50" r="4" fill="#FAF9F6"/>
                  </svg>
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-sm truncate">{item.artista}</p>
                <p className="font-serif italic text-sm text-zinc-400 truncate">{item.titulo}</p>
              </div>
              <span className="font-semibold text-sm shrink-0">{item.precio.toFixed(2)} €</span>
            </div>
          ))}
          <div className="flex justify-between px-5 py-4 font-semibold">
            <span>{t('total')}</span>
            <span>{order.total.toFixed(2)} €</span>
          </div>
        </div>
      </div>

      {/* Delivery info */}
      <div className="grid sm:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] p-4">
          <div className="flex items-center gap-2 mb-2">
            <Package size={14} className="text-zinc-400" />
            <p className="text-sm font-medium text-zinc-700">{t('delivery')}</p>
          </div>
          <p className="text-sm text-zinc-500">
            {order.metodo_envio === 'envio' ? t('postalShipping') : t('storePickup')}
          </p>
        </div>

        {order.direccion_envio && (
          <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] p-4">
            <div className="flex items-center gap-2 mb-2">
              <MapPin size={14} className="text-zinc-400" />
              <p className="text-sm font-medium text-zinc-700">{t('shippingAddress')}</p>
            </div>
            <address className="not-italic text-sm text-zinc-500 leading-relaxed">
              {order.direccion_envio.nombre_destinatario}<br />
              {order.direccion_envio.linea1}<br />
              {order.direccion_envio.cp} {order.direccion_envio.ciudad}
              {order.direccion_envio.provincia && `, ${order.direccion_envio.provincia}`}
            </address>
          </div>
        )}
      </div>

      {order.notas && (
        <div className="bg-zinc-50 rounded-xl p-4 text-sm text-zinc-500">
          <span className="font-medium text-zinc-700">{t('notes')}: </span>{order.notas}
        </div>
      )}
    </div>
  );
}
