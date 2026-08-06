'use client';

import { useEffect, useState } from 'react';
import { Link } from '../../../../i18n/navigation';
import { useTranslations, useLocale } from 'next-intl';
import { ShoppingBag, ChevronRight, Store, Clock } from 'lucide-react';
import { authFetch } from '../../../../components/store/AuthProvider';

const STATUS_COLOR = {
  pendiente_pago: 'text-amber-700 bg-amber-50 border-amber-200',
  pagado:         'text-blue-700 bg-blue-50 border-blue-200',
  enviado:        'text-purple-700 bg-purple-50 border-purple-200',
  entregado:      'text-green-700 bg-green-50 border-green-200',
  cancelado:      'text-zinc-500 bg-zinc-100 border-zinc-200',
  reservada:      'text-amber-700 bg-amber-50 border-amber-200',
  recollida:      'text-green-700 bg-green-50 border-green-200',
};

function horesRestants(reservedUntil) {
  const ms = new Date(reservedUntil).getTime() - Date.now();
  if (ms <= 0) return null;
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor((ms % 3_600_000) / 60_000);
  return `${h}h ${m}m`;
}

export default function ComandesPage() {
  const t = useTranslations('compte');
  const locale = useLocale();
  const METODE = { envio: t('postalShipping'), recogida_tienda: t('storePickup') };
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    authFetch('/me/orders')
      .then(r => r.ok ? r.json() : [])
      .then(setOrders)
      .catch(() => [])
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h1 className="font-serif italic text-2xl md:text-3xl mb-6">{t('myOrdersTitle')}</h1>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map(i => <div key={i} className="animate-pulse bg-zinc-100 rounded-xl h-20" />)}
        </div>
      ) : orders.length === 0 ? (
        <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] p-12 text-center">
          <ShoppingBag size={36} className="text-zinc-200 mx-auto mb-4" />
          <p className="text-zinc-400 mb-5">{t('noOrdersYet')}</p>
          <Link href="/cataleg" className="inline-flex items-center gap-2 bg-primary hover:bg-zinc-800 text-white px-5 py-2.5 rounded-full text-sm font-medium transition-colors">
            {t('exploreCatalog')}
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {orders.map(order => {
            if (order.tipo === 'comanda') {
              const color = STATUS_COLOR[order.status] || 'text-zinc-500 bg-zinc-100 border-zinc-200';
              const label = t.has(`orderStatus.${order.status}`) ? t(`orderStatus.${order.status}`) : order.status;
              return (
                <Link
                  key={order.id}
                  href={`/compte/comandes/${order.id}`}
                  className="flex items-center gap-4 bg-white shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] rounded-xl px-5 py-4 hover:border-zinc-200 hover:shadow-sm transition-all"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <p className="font-mono text-sm font-medium text-zinc-800">
                        #{order.id.toString().slice(0, 8).toUpperCase()}
                      </p>
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${color}`}>
                        {label}
                      </span>
                    </div>
                    <p className="text-xs text-zinc-400">
                      {new Date(order.created_at).toLocaleDateString(locale, { day: 'numeric', month: 'long', year: 'numeric' })}
                      {' · '}{METODE[order.metodo_envio] || order.metodo_envio}
                      {' · '}{t('itemCount', { count: order.num_items })}
                    </p>
                  </div>
                  <span className="font-semibold text-zinc-900 shrink-0">{order.total.toFixed(2)} €</span>
                  <ChevronRight size={15} className="text-zinc-300 shrink-0" />
                </Link>
              );
            }

            // reserva_botiga | venda_botiga: petició Via 2, sense Order real.
            const color = STATUS_COLOR[order.status] || 'text-zinc-500 bg-zinc-100 border-zinc-200';
            const label = t.has(`orderStatus.${order.status}`) ? t(`orderStatus.${order.status}`) : order.status;
            const restant = order.tipo === 'reserva_botiga' && order.reserved_until ? horesRestants(order.reserved_until) : null;
            return (
              <div key={order.id}
                className="flex items-center gap-4 bg-white shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] rounded-xl px-5 py-4">
                {order.imagen_url ? (
                  <img src={order.imagen_url} alt="" className="w-10 h-10 rounded-lg object-cover shrink-0 bg-zinc-100" />
                ) : (
                  <div className="w-10 h-10 rounded-lg bg-zinc-100 flex items-center justify-center shrink-0">
                    <Store size={15} className="text-zinc-300" />
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <p className="text-sm font-medium text-zinc-800 truncate">{order.titulo}</p>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full border shrink-0 ${color}`}>
                      {label}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-400 truncate">
                    {order.artista}
                    {order.tipo === 'reserva_botiga' && (
                      <span className="text-amber-600"> · {t('comeCollectAndPayAtShop')}</span>
                    )}
                  </p>
                  {restant && (
                    <p className="flex items-center gap-1 text-xs text-red-500 mt-0.5"><Clock size={11} /> {t('timeRemaining', { time: restant })}</p>
                  )}
                </div>
                <span className="font-semibold text-zinc-900 shrink-0">{order.total.toFixed(2)} €</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
