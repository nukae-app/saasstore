'use client';

import { useEffect, useState } from 'react';
import { Link } from '../../../../i18n/navigation';
import { useTranslations } from 'next-intl';
import { Disc3, Loader2, Pause, Play, X } from 'lucide-react';
import { authFetch } from '../../../../components/store/AuthProvider';

export default function ComptesSubscripcioPage() {
  const t = useTranslations('subscripcioCompte');
  const ESTAT_LABEL = { activa: t('active'), pausada: t('paused'), cancel_lada: t('cancelled') };
  const LABEL_PERIODICITAT = {
    1: t('monthly'), 2: t('every2Months'), 3: t('every3Months'), 6: t('every6Months'), 12: t('yearly'),
  };
  const [sub, setSub] = useState(undefined); // undefined = carregant, null = sense subscripció
  const [generes, setGeneres] = useState([]);
  const [acting, setActing] = useState(false);

  async function load() {
    const [rs, rGen] = await Promise.all([
      authFetch('/me/subscripcio'),
      fetch('/api/subscripcions/generes'),
    ]);
    setSub(rs.status === 404 ? null : await rs.json());
    setGeneres(rGen.ok ? await rGen.json() : []);
  }

  useEffect(() => { load(); }, []);

  async function toggleEstat() {
    setActing(true);
    try {
      await authFetch('/me/subscripcio', {
        method: 'PATCH',
        body: JSON.stringify({ estat: sub.estat === 'activa' ? 'pausada' : 'activa' }),
      });
      await load();
    } finally {
      setActing(false);
    }
  }

  async function cancelar() {
    if (!confirm(t('cancelConfirm'))) return;
    setActing(true);
    try {
      await authFetch('/me/subscripcio/cancelar', { method: 'POST' });
      await load();
    } finally {
      setActing(false);
    }
  }

  async function toggleGenere(g) {
    const actuals = sub.generes_preferits || [];
    const noves = actuals.includes(g) ? actuals.filter(x => x !== g) : [...actuals, g];
    setSub(s => ({ ...s, generes_preferits: noves }));
    await authFetch('/me/subscripcio', { method: 'PATCH', body: JSON.stringify({ generes_preferits: noves }) });
  }

  if (sub === undefined) {
    return <div className="py-16 flex justify-center"><Loader2 className="animate-spin text-zinc-400" /></div>;
  }

  if (sub === null) {
    return (
      <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] p-8 text-center">
        <Disc3 size={32} className="mx-auto text-zinc-300 mb-3" />
        <h1 className="font-serif italic text-2xl mb-2">{t('notInClubYet')}</h1>
        <p className="text-zinc-500 text-sm mb-6 max-w-sm mx-auto">
          {t('everyPeriodWeSend')}
        </p>
        <Link href="/subscripcio" className="inline-flex items-center gap-2 bg-primary hover:bg-zinc-800 text-white px-6 py-3 rounded-full font-medium text-sm transition-colors">
          {t('discoverTheClub')}
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] p-6">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <h1 className="font-serif italic text-2xl mb-1">
              {t('recordCount', { count: sub.quantitat })} — {LABEL_PERIODICITAT[sub.periodicitat_mesos] || t('everyNMonths', { n: sub.periodicitat_mesos })}
            </h1>
            <p className="text-sm text-zinc-500 mb-2">{t('pricePerShipment', { price: sub.preu_periode })}</p>
            <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${
              sub.estat === 'activa' ? 'bg-emerald-100 text-emerald-700' : sub.estat === 'pausada' ? 'bg-amber-100 text-amber-700' : 'bg-zinc-100 text-zinc-500'
            }`}>
              {ESTAT_LABEL[sub.estat] || sub.estat}
            </span>
          </div>
          {sub.estat !== 'cancel_lada' && (
            <div className="flex gap-2">
              <button onClick={toggleEstat} disabled={acting}
                className="flex items-center gap-1.5 border border-zinc-200 text-zinc-600 px-3 py-2 rounded-lg text-sm hover:bg-zinc-50 transition-colors disabled:opacity-60">
                {sub.estat === 'activa' ? <Pause size={14} /> : <Play size={14} />}
                {sub.estat === 'activa' ? t('pause') : t('resume')}
              </button>
              <button onClick={cancelar} disabled={acting}
                className="flex items-center gap-1.5 border border-zinc-200 text-red-500 px-3 py-2 rounded-lg text-sm hover:bg-red-50 transition-colors disabled:opacity-60">
                <X size={14} /> {t('cancel')}
              </button>
            </div>
          )}
        </div>
        {sub.estat === 'activa' && (
          <p className="text-sm text-zinc-500 mt-4">
            {t('nextBilling')}: <span className="text-zinc-900 font-medium">{sub.proxima_facturacio}</span>
          </p>
        )}
      </div>

      {sub.estat !== 'cancel_lada' && (
        <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] p-6">
          <h2 className="font-medium text-zinc-900 mb-3">{t('musicalTaste')}</h2>
          <p className="text-xs text-zinc-400 mb-3">{t('noGenreMarkedNote')}</p>
          <div className="flex flex-wrap gap-2">
            {generes.map(g => (
              <button key={g} onClick={() => toggleGenere(g)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                  (sub.generes_preferits || []).includes(g)
                    ? 'bg-zinc-900 text-white border-transparent' : 'border-zinc-200 text-zinc-600 hover:bg-zinc-50'
                }`}
              >
                {g}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] p-6">
        <h2 className="font-medium text-zinc-900 mb-3">{t('recordsReceived')}</h2>
        {sub.discos_rebuts.length === 0 ? (
          <p className="text-sm text-zinc-400">{t('noRecordsReceivedYet')}</p>
        ) : (
          <ul className="divide-y divide-zinc-100">
            {sub.discos_rebuts.map(d => (
              <li key={d.release_id} className="py-2.5 flex items-center gap-3 text-sm">
                {d.imagen_url ? (
                  <img src={d.imagen_url} alt="" className="w-10 h-10 rounded object-cover" />
                ) : (
                  <div className="w-10 h-10 rounded bg-zinc-100 flex items-center justify-center"><Disc3 size={16} className="text-zinc-300" /></div>
                )}
                <span className="text-zinc-700">{d.artista} — {d.titulo}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
