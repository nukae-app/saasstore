'use client';

import { useEffect, useState } from 'react';
import { Link } from '../../../i18n/navigation';
import { useSearchParams } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import { ShoppingBag, ChevronRight, Package, Music2, Loader2, Unlink } from 'lucide-react';
import { useAuth } from '../../../components/store/AuthProvider';
import { authFetch } from '../../../components/store/AuthProvider';
import { useSpotifyEnabled } from '../../../components/store/useSpotifyEnabled';

const STATUS_COLOR = {
  pendiente_pago: 'text-amber-600 bg-amber-50',
  pagado: 'text-blue-600 bg-blue-50',
  enviado: 'text-purple-600 bg-purple-50',
  entregado: 'text-green-600 bg-green-50',
  cancelado: 'text-zinc-500 bg-zinc-100',
};

function SpotifySection() {
  const t = useTranslations('compte');
  const searchParams = useSearchParams();
  const enabled = useSpotifyEnabled();
  const [status, setStatus] = useState('loading'); // loading | connected | disconnected
  const [displayName, setDisplayName] = useState('');
  const [connecting, setConnecting] = useState(false);
  const [flash, setFlash] = useState('');

  useEffect(() => {
    if (!enabled) return;

    const sp = searchParams.get('spotify');
    if (sp === 'ok') setFlash(t('spotifyConnected'));
    if (sp === 'error') setFlash(t('spotifyConnectError'));

    authFetch('/api/auth/spotify/status')
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (!d) { setStatus('disconnected'); return; }
        setStatus(d.connected ? 'connected' : 'disconnected');
        if (d.display_name) setDisplayName(d.display_name);
      })
      .catch(() => setStatus('disconnected'));
  }, [enabled, searchParams]);

  if (!enabled) return null;

  async function connect() {
    setConnecting(true);
    try {
      const r = await authFetch('/api/auth/spotify/init', { method: 'POST' });
      if (!r.ok) { setFlash(t('spotifyNotConfigured')); return; }
      const { url } = await r.json();
      window.location.href = url;
    } catch {
      setFlash(t('spotifyConnectStartError'));
    } finally {
      setConnecting(false);
    }
  }

  async function disconnect() {
    if (!confirm(t('spotifyDisconnectConfirm'))) return;
    await authFetch('/api/auth/spotify/disconnect', { method: 'DELETE' });
    setStatus('disconnected');
    setDisplayName('');
    setFlash(t('spotifyDisconnected'));
  }

  return (
    <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] p-5">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-8 h-8 rounded-full bg-[#1DB954] flex items-center justify-center shrink-0">
          <Music2 size={16} className="text-black" />
        </div>
        <div>
          <h3 className="font-medium text-zinc-900 text-sm">Spotify</h3>
          <p className="text-xs text-zinc-400">{t('spotifyRecommendationsSubtitle')}</p>
        </div>
      </div>

      {flash && (
        <div className={`text-xs rounded-lg px-3 py-2 mb-3 ${flash.includes('Error') ? 'bg-red-50 text-red-600' : 'bg-emerald-50 text-emerald-700'}`}>
          {flash}
        </div>
      )}

      {status === 'loading' && (
        <div className="flex items-center gap-2 text-zinc-400 text-xs">
          <Loader2 size={12} className="animate-spin" /> {t('loadingEllipsis')}
        </div>
      )}

      {status === 'connected' && (
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#1DB954]" />
            <span className="text-sm text-zinc-700">
              {displayName ? t('spotifyConnectedAs', { name: displayName }) : t('spotifyConnectedPlain')}
            </span>
          </div>
          <button
            onClick={disconnect}
            className="flex items-center gap-1.5 text-xs text-zinc-400 hover:text-red-500 transition-colors"
          >
            <Unlink size={12} /> {t('disconnect')}
          </button>
        </div>
      )}

      {status === 'disconnected' && (
        <button
          onClick={connect}
          disabled={connecting}
          className="flex items-center gap-2 bg-[#1DB954] hover:bg-[#1ed760] disabled:opacity-60 text-black font-semibold px-4 py-2 rounded-full text-sm transition-colors"
        >
          {connecting ? <Loader2 size={14} className="animate-spin" /> : <Music2 size={14} />}
          {connecting ? t('spotifyConnecting') : t('spotifyConnect')}
        </button>
      )}
    </div>
  );
}

export default function ComptePage() {
  const t = useTranslations('compte');
  const locale = useLocale();
  const { user } = useAuth();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    authFetch('/me/orders')
      .then(r => r.ok ? r.json() : [])
      .then(setOrders)
      .catch(() => setOrders([]))
      .finally(() => setLoading(false));
  }, []);

  const pending = orders.filter(o => o.status === 'pendiente_pago');
  const recent = orders.slice(0, 3);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif italic text-2xl md:text-3xl">
          {user?.name?.split(' ')[0] ? t('helloName', { name: user.name.split(' ')[0] }) : t('helloAgain')}
        </h1>
        <p className="text-zinc-500 text-sm mt-1">{t('welcomeToAccount')}</p>
      </div>

      {/* Spotify */}
      <SpotifySection />

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] p-4">
          <p className="text-2xl font-semibold text-zinc-900">{orders.length}</p>
          <p className="text-sm text-zinc-400 mt-0.5">{t('totalOrders')}</p>
        </div>
        <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] p-4">
          <p className="text-2xl font-semibold text-amber-600">{pending.length}</p>
          <p className="text-sm text-zinc-400 mt-0.5">{t('pendingPayment')}</p>
        </div>
      </div>

      {/* Pending alert */}
      {pending.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center gap-3">
          <Package size={18} className="text-amber-600 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-amber-800">
              {t('pendingOrdersCount', { count: pending.length })}
            </p>
            <p className="text-xs text-amber-600 mt-0.5">{t('completePaymentOrPickup')}</p>
          </div>
          <Link href="/compte/comandes" className="text-amber-700 hover:text-amber-900 shrink-0">
            <ChevronRight size={16} />
          </Link>
        </div>
      )}

      {/* Recent orders */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-medium text-zinc-900">{t('latestOrders')}</h2>
          {orders.length > 3 && (
            <Link href="/compte/comandes" className="text-xs text-zinc-400 hover:text-zinc-700 transition-colors">
              {t('seeAll')}
            </Link>
          )}
        </div>

        {loading ? (
          <div className="space-y-3">
            {[1, 2].map(i => (
              <div key={i} className="animate-pulse bg-zinc-100 rounded-xl h-16" />
            ))}
          </div>
        ) : recent.length === 0 ? (
          <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] p-8 text-center">
            <ShoppingBag size={32} className="text-zinc-200 mx-auto mb-3" />
            <p className="text-zinc-400 text-sm mb-4">{t('noOrdersYet')}</p>
            <Link
              href="/cataleg"
              className="inline-flex items-center gap-2 bg-primary hover:bg-zinc-800 text-white px-5 py-2.5 rounded-full text-sm font-medium transition-colors"
            >
              {t('exploreCatalog')}
            </Link>
          </div>
        ) : (
          <div className="space-y-2">
            {recent.map(order => {
              const color = STATUS_COLOR[order.status] || 'text-zinc-500 bg-zinc-100';
              const label = t.has(`orderStatus.${order.status}`) ? t(`orderStatus.${order.status}`) : order.status;
              return (
                <Link
                  key={order.id}
                  href={`/compte/comandes/${order.id}`}
                  className="flex items-center gap-4 bg-white shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] rounded-xl px-4 py-3.5 hover:border-zinc-200 transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-zinc-800">
                      #{order.id.toString().slice(0, 8).toUpperCase()}
                    </p>
                    <p className="text-xs text-zinc-400 mt-0.5">
                      {new Date(order.created_at).toLocaleDateString(locale)} · {t('itemCount', { count: order.num_items })}
                    </p>
                  </div>
                  <span className={`text-xs font-medium px-2 py-1 rounded-full ${color}`}>
                    {label}
                  </span>
                  <span className="font-semibold text-sm text-zinc-900 shrink-0">
                    {order.total.toFixed(2)} €
                  </span>
                  <ChevronRight size={14} className="text-zinc-300 shrink-0" />
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
