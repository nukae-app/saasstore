'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { authFetch } from '../../lib/auth';
import {
  TrendingUp, TrendingDown, Calculator, Landmark, Clock, AlertCircle,
  Receipt, BookText, Boxes, Library, Truck, ArrowRight,
} from 'lucide-react';

function fmtEur(v) {
  return v != null ? parseFloat(v).toFixed(2) + ' €' : '—';
}
function fmtDate(d) {
  if (!d) return '—';
  return new Date(d + 'T00:00:00').toLocaleDateString('ca-ES', { day: '2-digit', month: '2-digit' });
}

const ACCESSOS = [
  { href: '/admin/despeses', label: 'Despeses', icon: Receipt },
  { href: '/admin/banc', label: 'Banc', icon: Landmark },
  { href: '/admin/proveidors', label: 'Proveïdors', icon: Truck },
  { href: '/admin/pla-comptes', label: 'Pla de comptes', icon: BookText },
  { href: '/admin/actius', label: 'Actius', icon: Boxes },
  { href: '/admin/llibres', label: 'Llibres', icon: Library },
];

export default function ComptabilitatResumPage() {
  const [pyg, setPyg] = useState(null);
  const [aeat, setAeat] = useState(null);
  const [pendents, setPendents] = useState([]);
  const [saldoBanc, setSaldoBanc] = useState(null);
  const [diari, setDiari] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const now = new Date();
    const year = now.getFullYear();
    const mes = now.getMonth() + 1;
    const trimestre = Math.ceil(mes / 3);

    // allSettled, no all: una targeta caient (p.ex. sessió caducada just en
    // aquesta crida concreta) no ha de deixar tota la pantalla penjada a
    // "Carregant..." per sempre — cada targeta es degrada per separat.
    Promise.allSettled([
      authFetch(`/admin/compte-resultats/${year}/${mes}`).then(r => (r.ok ? r.json() : null)),
      authFetch(`/admin/aeat/303/${year}/${trimestre}`).then(r => (r.ok ? r.json() : null)),
      authFetch('/admin/despeses/pendents').then(r => (r.ok ? r.json() : [])),
      authFetch(`/admin/llibre-major/${year}?compte=572`).then(r => (r.ok ? r.json() : null)),
      authFetch(`/admin/llibre-diari/${year}/${mes}`).then(r => (r.ok ? r.json() : null)),
    ]).then(([pygRes, aeatRes, pendentsRes, majorRes, diariRes]) => {
      setPyg(pygRes.status === 'fulfilled' ? pygRes.value : null);
      setAeat(aeatRes.status === 'fulfilled' ? aeatRes.value : null);
      setPendents(pendentsRes.status === 'fulfilled' ? pendentsRes.value ?? [] : []);
      setSaldoBanc(majorRes.status === 'fulfilled' ? majorRes.value?.saldo_final ?? null : null);
      setDiari(diariRes.status === 'fulfilled' ? diariRes.value : null);
      setLoading(false);
    });
  }, []);

  if (loading) return <div className="p-12 text-center text-zinc-400 text-sm">Carregant...</div>;

  const resultatPositiu = pyg && parseFloat(pyg.resultat) >= 0;
  const vencudes = pendents.filter(d => d.payment_status === 'vencut');
  const properesAVencer = pendents
    .filter(d => d.payment_status !== 'vencut')
    .sort((a, b) => (a.due_date || '9999').localeCompare(b.due_date || '9999'))
    .slice(0, 5);
  const ultimsAssentaments = diari?.assentaments?.slice(-5).reverse() || [];

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold text-zinc-900">Comptabilitat</h2>
        <p className="text-sm text-zinc-500 mt-1">Resum del mes en curs — un cop d&apos;ull abans d&apos;entrar al detall.</p>
      </div>

      {/* Targes resum */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className={`rounded-xl p-4 border ${resultatPositiu ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
          <div className={`flex items-center gap-1.5 text-xs mb-1 ${resultatPositiu ? 'text-green-600' : 'text-red-600'}`}>
            {resultatPositiu ? <TrendingUp size={13} /> : <TrendingDown size={13} />} Resultat del mes
          </div>
          <div className={`text-xl font-bold ${resultatPositiu ? 'text-green-700' : 'text-red-700'}`}>
            {pyg ? fmtEur(pyg.resultat) : '—'}
          </div>
        </div>

        <div className="rounded-xl p-4 border bg-blue-50 border-blue-200">
          <div className="flex items-center gap-1.5 text-xs mb-1 text-blue-600"><Calculator size={13} /> IVA trimestre actual</div>
          <div className="text-xl font-bold text-blue-700">{aeat ? fmtEur(aeat.casella_64_resultat_liquidacio) : '—'}</div>
        </div>

        <div className="rounded-xl p-4 border bg-zinc-50 border-zinc-200">
          <div className="flex items-center gap-1.5 text-xs mb-1 text-zinc-500"><Landmark size={13} /> Saldo banc (572)</div>
          <div className="text-xl font-bold text-zinc-800">{saldoBanc != null ? fmtEur(saldoBanc) : '—'}</div>
        </div>

        <div className={`rounded-xl p-4 border ${vencudes.length ? 'bg-red-50 border-red-200' : 'bg-zinc-50 border-zinc-200'}`}>
          <div className={`flex items-center gap-1.5 text-xs mb-1 ${vencudes.length ? 'text-red-600' : 'text-zinc-500'}`}>
            <AlertCircle size={13} /> Factures vençudes
          </div>
          <div className={`text-xl font-bold ${vencudes.length ? 'text-red-700' : 'text-zinc-800'}`}>{vencudes.length}</div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {/* Pendents de pagament */}
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
          <div className="px-4 py-2.5 bg-zinc-50 border-b border-zinc-200 flex items-center justify-between">
            <span className="text-sm font-semibold text-zinc-700 flex items-center gap-1.5"><Clock size={14} /> Properes a vèncer</span>
            <Link href="/admin/despeses" className="text-xs text-zinc-400 hover:text-zinc-700 flex items-center gap-0.5">
              Veure totes <ArrowRight size={11} />
            </Link>
          </div>
          {properesAVencer.length === 0 ? (
            <div className="p-6 text-center text-zinc-400 text-xs">Cap factura pendent</div>
          ) : (
            <div className="divide-y divide-zinc-100">
              {properesAVencer.map(d => (
                <div key={d.id} className="px-4 py-2.5 flex items-center justify-between text-sm">
                  <div>
                    <div className="text-zinc-800">{d.supplier_name}</div>
                    <div className="text-xs text-zinc-400">Venç {fmtDate(d.due_date)}</div>
                  </div>
                  <div className="font-semibold text-zinc-900">{fmtEur(d.total)}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Últims assentaments */}
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
          <div className="px-4 py-2.5 bg-zinc-50 border-b border-zinc-200 flex items-center justify-between">
            <span className="text-sm font-semibold text-zinc-700 flex items-center gap-1.5"><Library size={14} /> Últims assentaments</span>
            <Link href="/admin/llibres" className="text-xs text-zinc-400 hover:text-zinc-700 flex items-center gap-0.5">
              Veure llibres <ArrowRight size={11} />
            </Link>
          </div>
          {ultimsAssentaments.length === 0 ? (
            <div className="p-6 text-center text-zinc-400 text-xs">Cap assentament aquest mes</div>
          ) : (
            <div className="divide-y divide-zinc-100">
              {ultimsAssentaments.map(a => (
                <div key={a.id} className="px-4 py-2.5 flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-zinc-400">#{a.entry_number}</span>
                    <span className="text-zinc-800">{a.description}</span>
                  </div>
                  <span className="text-xs text-zinc-400">{fmtDate(a.date)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Accessos ràpids */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
        {ACCESSOS.map(({ href, label, icon: Icon }) => (
          <Link key={href} href={href}
            className="flex flex-col items-center gap-1.5 p-4 bg-white border border-zinc-200 rounded-xl hover:border-zinc-400 hover:shadow-sm transition-all text-center">
            <Icon size={20} className="text-zinc-500" />
            <span className="text-xs font-medium text-zinc-700">{label}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
