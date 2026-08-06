'use client';

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { authFetch } from '../../lib/auth';
import { useT } from '../../lib/i18n';
import { Button } from '../../../components/ui/button';
import ReturnSaleModal from '../../../components/admin/ReturnSaleModal';
import { useSortFilter } from '../../../components/admin/table/useSortFilter';
import { SortableTh } from '../../../components/admin/table/SortableTh';
import { Search, X, Disc3, RotateCcw, ChevronDown, ChevronRight, Clock, Bell, Printer, Check, User as UserIcon, UserPlus } from 'lucide-react';

const CANAL_COLOR = {
  mostrador: 'bg-amber-100 text-amber-700',
  discogs:   'bg-blue-100 text-blue-700',
  otro:      'bg-zinc-100 text-zinc-700',
};
const CANAL_KEY = {
  mostrador: 'tpv.canal.counter',
  discogs:   'tpv.canal.discogs',
  otro:      'tpv.canal.other',
};

// Mètodes de pagament disponibles al TPV (venda de mostrador). Bizum i bono
// cultural s'hi van afegir perquè el Control de caixa (/admin/resultat) els
// pugui omplir automàticament — abans només hi havia efectiu/targeta i la
// resta de mètodes s'havien d'apuntar a mà.
const METODES_PAGAMENT = [
  { val: 'efectivo',      key: 'tpv.pago.cash',         label_ca: 'Efectiu',        color: 'bg-green-500',  badge: 'bg-green-100 text-green-700',  btn: '' },
  { val: 'tarjeta',       key: 'tpv.pago.card',         label_ca: 'Targeta',        color: 'bg-indigo-500', badge: 'bg-indigo-100 text-indigo-700', btn: 'bg-indigo-600 hover:bg-indigo-700' },
  { val: 'bizum',         key: 'tpv.pago.bizum',        label_ca: 'Bizum',          color: 'bg-pink-500',   badge: 'bg-pink-100 text-pink-700',    btn: 'bg-pink-600 hover:bg-pink-700' },
  { val: 'bono_cultural', key: 'tpv.pago.bono_cultural', label_ca: 'Bono cultural', color: 'bg-purple-500', badge: 'bg-purple-100 text-purple-700', btn: 'bg-purple-600 hover:bg-purple-700' },
];
function metodePagamentInfo(val) {
  return METODES_PAGAMENT.find(m => m.val === val) || METODES_PAGAMENT[0];
}

// ─── helpers ────────────────────────────────────────────────────────────────

function startOfDay(d) {
  const r = new Date(d); r.setHours(0, 0, 0, 0); return r;
}
function addDays(d, n) {
  const r = new Date(d); r.setDate(r.getDate() + n); return r;
}

// Dades fiscals de la botiga per a la capçalera del tiquet imprès.
function useShopConfig() {
  const [config, setConfig] = useState(null);
  useEffect(() => {
    authFetch('/admin/configuracio')
      .then(r => (r.ok ? r.json() : null))
      .then(setConfig)
      .catch(() => {});
  }, []);
  return config;
}

// ─── Page ───────────────────────────────────────────────────────────────────

export default function TpvPage() {
  const t = useT();
  const [tab, setTab] = useState('venda');

  const TABS = [
    { key: 'venda', label: t('tpv.tab.venda') },
    { key: 'reserves', label: 'Reserves web' },
    { key: 'resum', label: t('tpv.tab.resum') },
    { key: 'caixa', label: t('tpv.tab.caixa') },
  ];

  return (
    <div className="space-y-5 max-w-4xl mx-auto">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-2xl font-bold text-zinc-900">{t('tpv.title')}</h2>
        <div className="flex gap-1 bg-zinc-100 p-1 rounded-xl">
          {TABS.map(({ key, label }) => (
            <button key={key} onClick={() => setTab(key)}
              className={`px-5 py-1.5 rounded-lg text-sm font-medium transition-colors ${tab === key ? 'bg-white text-zinc-900 shadow-sm' : 'text-zinc-600 hover:text-zinc-900'}`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {tab === 'venda' && <VendaTab />}
      {tab === 'reserves' && <ReservesWebTab />}
      {tab === 'resum' && <ResumTab />}
      {tab === 'caixa' && <CaixaTab />}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB 1 — Venda
// ═══════════════════════════════════════════════════════════════════════════

// Un identificador local únic per a les línies de la cistella que no vénen
// d'un item de catàleg (articles manuals): no tenen item_id fins que no
// s'envien al backend.
let _manualSeq = 0;
function _manualKey() { return `manual-${Date.now()}-${_manualSeq++}`; }

function VendaTab() {
  const t = useT();
  const [q, setQ] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  // Línia de catàleg: { key: item_id, id: item_id, artista, titulo, imagen_url, estado_disco, precio }
  // Línia manual:     { key, manual: true, descripcion, precio, tipus_iva_id, tipus_iva_nom }
  const [cart, setCart] = useState([]);
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [lastSale, setLastSale] = useState(null);
  const [error, setError] = useState('');
  const [tiposIva, setTiposIva] = useState([]);
  const [manualOpen, setManualOpen] = useState(false);
  const [manualDesc, setManualDesc] = useState('');
  const [manualPrecio, setManualPrecio] = useState('');
  const [manualTipusIvaId, setManualTipusIvaId] = useState('');
  const searchRef = useRef(null);
  const debounce = useRef(null);
  const shopConfig = useShopConfig();

  useEffect(() => { searchRef.current?.focus(); }, []);

  useEffect(() => {
    authFetch('/admin/tipus-iva?nomes_actius=true')
      .then(r => (r.ok ? r.json() : []))
      .then(tipos => {
        // El règim REBU calcula l'IVA sobre el marge (venda - cost
        // d'adquisició), que un article manual no té: no es pot triar aquí.
        const seleccionables = tipos.filter(tp => !tp.es_rebu);
        setTiposIva(seleccionables);
        setManualTipusIvaId(prev => prev || (seleccionables[0]?.id ?? ''));
      })
      .catch(() => {});
  }, []);

  async function search(query) {
    if (!query.trim()) { setResults([]); return; }
    setSearching(true);
    setError('');
    try {
      const r = await authFetch(`/catalog?q=${encodeURIComponent(query)}&page_size=20`);
      if (!r.ok) throw new Error();
      const data = await r.json();
      const items = (data.results ?? []).flatMap(rel =>
        (rel.items ?? [])
          .filter(it => it.condicion === 'nou'
            ? it.status === 'disponible' && (it.cantidad - it.cantidad_reservada) > 0
            : it.status === 'disponible')
          .map(it => ({ ...it, artista: rel.artista, titulo: rel.titulo, imagen_url: rel.imagen_url }))
      );
      setResults(items);
    } catch {
      setResults([]);
      setError(t('tpv.search_error'));
    } finally {
      setSearching(false);
    }
  }

  function handleQ(val) {
    setQ(val);
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => search(val), 300);
  }

  // Segona mà: cada resultat és una còpia física única, així que "vendre
  // vàries unitats d'un mateix disc" és afegir-hi vàries còpies diferents
  // (cadascuna amb el seu propi item_id) — no s'ajunten mai en una línia.
  // Nou (stock agregat): tornar a afegir el mateix item suma unitats a la
  // mateixa línia, sense superar `cantidad - cantidad_reservada`.
  function addToCart(item) {
    setCart(c => {
      if (item.condicion === 'nou') {
        const existing = c.find(l => l.key === item.id);
        const disponible = item.cantidad - item.cantidad_reservada;
        if (existing) {
          if (existing.cantidad >= disponible) return c;
          return c.map(l => l.key === item.id ? { ...l, cantidad: l.cantidad + 1 } : l);
        }
        return [...c, { ...item, key: item.id, precio: item.precio, cantidad: 1, disponible }];
      }
      return c.some(l => l.key === item.id) ? c : [...c, { ...item, key: item.id, precio: item.precio, cantidad: 1 }];
    });
    setQ('');
    setResults([]);
    searchRef.current?.focus();
  }

  function updateCartCantidad(key, delta) {
    setCart(c => c.map(l => {
      if (l.key !== key) return l;
      const next = l.cantidad + delta;
      if (next < 1 || (l.disponible != null && next > l.disponible)) return l;
      return { ...l, cantidad: next };
    }));
  }

  function addManualToCart() {
    if (!manualDesc.trim() || !manualPrecio || !manualTipusIvaId) return;
    const tipus = tiposIva.find(tp => tp.id === Number(manualTipusIvaId));
    setCart(c => [...c, {
      key: _manualKey(),
      manual: true,
      descripcion: manualDesc.trim(),
      precio: manualPrecio,
      cantidad: 1,
      tipus_iva_id: Number(manualTipusIvaId),
      tipus_iva_nom: tipus?.nom,
    }]);
    setManualDesc('');
    setManualPrecio('');
    setManualOpen(false);
  }

  function removeFromCart(key) {
    setCart(c => c.filter(l => l.key !== key));
  }

  function updateCartPrecio(key, precio) {
    setCart(c => c.map(l => (l.key === key ? { ...l, precio } : l)));
  }

  const cartTotal = cart.reduce((s, l) => s + (parseFloat(l.precio) || 0) * (l.cantidad || 1), 0);

  async function checkout(nombreCliente, metodoPago, userId) {
    const r = await authFetch('/admin/ventas-externas/lote', {
      method: 'POST',
      body: JSON.stringify({
        // precio_venta és el TOTAL de la línia (preu unitari × cantidad).
        lineas: cart.map(l => l.manual
          ? { descripcion: l.descripcion, tipus_iva_id: l.tipus_iva_id, precio_venta: parseFloat(l.precio) }
          : { item_id: l.id, precio_venta: parseFloat(l.precio) * (l.cantidad || 1), cantidad: l.cantidad || 1 }
        ),
        canal: 'mostrador',
        metodo_pago: metodoPago,
        fecha: new Date().toISOString(),
        nombre_cliente: nombreCliente || null,
        user_id: userId || null,
      }),
    });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      throw new Error(body.detail || t('tpv.sell_error'));
    }
    const ventas = await r.json();
    const items = ventas.map(v => ({ ...v, estado_disco: cart.find(l => l.id === v.item_id)?.estado_disco }));
    setCheckoutOpen(false);
    setCart([]);
    setLastSale({ items, metodo_pago: metodoPago, nombre_cliente: nombreCliente || null, fecha: new Date().toISOString() });
  }

  return (
    <div className="space-y-4">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-2.5">{error}</div>
      )}

      {/* Search */}
      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6 space-y-4">
        <div className="relative">
          <Search size={20} className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-400" />
          <input ref={searchRef} value={q} onChange={e => handleQ(e.target.value)}
            placeholder={t('tpv.search_ph')}
            className="w-full pl-12 pr-4 py-4 border-2 border-zinc-200 rounded-xl text-base focus:outline-none focus:border-zinc-900 transition-colors" />
        </div>

        {searching && <div className="text-center text-sm text-zinc-400 py-2">{t('common.searching')}</div>}

        {results.length > 0 && (
          <div className="space-y-2">
            {results.map(item => (
              <button key={item.id} onClick={() => addToCart(item)}
                className="w-full flex items-center gap-4 p-4 rounded-xl border-2 border-zinc-100 hover:border-zinc-300 hover:bg-zinc-50 transition-all text-left">
                {item.imagen_url
                  ? <img src={item.imagen_url} alt="" className="w-14 h-14 rounded-xl object-cover shrink-0" />
                  : <div className="w-14 h-14 rounded-xl bg-zinc-100 flex items-center justify-center text-zinc-400 shrink-0"><Disc3 size={24} /></div>
                }
                <div className="flex-1 min-w-0">
                  <div className="font-bold text-zinc-900 text-base">{item.artista}</div>
                  <div className="text-zinc-600">{item.titulo}</div>
                  <div className="flex items-center gap-2 mt-0.5">
                    {item.condicion === 'nou'
                      ? <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-700">{t('common.condition.new')}</span>
                      : <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-zinc-100 text-zinc-600">{t('common.condition.used')}</span>
                    }
                    {item.condicion !== 'nou' && (
                      <span className="text-xs text-zinc-400">{[item.estado_disco, item.estado_funda].filter(Boolean).join(' / ')}</span>
                    )}
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-2xl font-bold text-zinc-900">{item.precio} €</div>
                  <div className="text-xs text-green-600 font-semibold mt-0.5">{t('tpv.available')}</div>
                </div>
              </button>
            ))}
          </div>
        )}

        {q && !searching && results.length === 0 && (
          <div className="text-center text-sm text-zinc-400 py-4">{t('tpv.no_results')}</div>
        )}

        {/* Article manual (no ve del catàleg: llibres, samarretes, merxandatge...) */}
        {!manualOpen ? (
          <button onClick={() => setManualOpen(true)}
            className="text-sm text-zinc-500 hover:text-zinc-900 font-medium">
            + Article manual
          </button>
        ) : (
          <div className="bg-zinc-50 rounded-xl p-4 space-y-3">
            <div className="text-sm font-semibold text-zinc-700">Article manual</div>
            <input value={manualDesc} onChange={e => setManualDesc(e.target.value)}
              placeholder="Descripció (p.ex. Samarreta talla M)"
              className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-zinc-900" />
            <div className="flex gap-2">
              <input type="number" step="0.01" min="0" value={manualPrecio} onChange={e => setManualPrecio(e.target.value)}
                placeholder="Preu final (€)"
                className="flex-1 border border-zinc-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-zinc-900" />
              <select value={manualTipusIvaId} onChange={e => setManualTipusIvaId(e.target.value)}
                className="flex-1 border border-zinc-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:border-zinc-900">
                {tiposIva.length === 0 && <option value="">Cap tipus d'IVA configurat</option>}
                {tiposIva.map(tp => (
                  <option key={tp.id} value={tp.id}>{tp.nom} ({parseFloat(tp.percentatge)}%)</option>
                ))}
              </select>
            </div>
            <div className="flex gap-2">
              <Button type="button" onClick={addManualToCart}
                disabled={!manualDesc.trim() || !manualPrecio || !manualTipusIvaId}>
                Afegir a la cistella
              </Button>
              <button type="button" onClick={() => { setManualOpen(false); setManualDesc(''); setManualPrecio(''); }}
                className="px-3 py-1.5 text-sm text-zinc-500 hover:text-zinc-700">
                {t('common.cancel')}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Cistella */}
      {cart.length > 0 && (
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
          <div className="px-5 py-3 border-b border-zinc-100 flex items-center justify-between">
            <span className="text-sm font-semibold text-zinc-700">
              Cistella · {cart.length} {cart.length === 1 ? 'article' : 'articles'}
            </span>
            <button onClick={() => setCart([])} className="text-xs text-zinc-400 hover:text-red-600 font-medium">
              Buidar
            </button>
          </div>
          <div className="divide-y divide-zinc-100">
            {cart.map(l => (
              <div key={l.key} className="flex items-center gap-3 p-3">
                {l.manual
                  ? <div className="w-10 h-10 rounded-lg bg-amber-50 flex items-center justify-center text-amber-600 shrink-0 text-xs font-bold">M</div>
                  : l.imagen_url
                    ? <img src={l.imagen_url} alt="" className="w-10 h-10 rounded-lg object-cover shrink-0" />
                    : <div className="w-10 h-10 rounded-lg bg-zinc-100 flex items-center justify-center text-zinc-400 shrink-0"><Disc3 size={16} /></div>
                }
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-zinc-900 text-sm truncate">
                    {l.manual ? l.descripcion : `${l.artista} — ${l.titulo}`}
                  </div>
                  {l.manual
                    ? <div className="text-xs text-zinc-400 truncate">IVA {l.tipus_iva_nom}</div>
                    : l.estado_disco && <div className="text-xs text-zinc-400 truncate">{l.estado_disco}</div>
                  }
                </div>
                {!l.manual && l.condicion === 'nou' && l.disponible > 1 && (
                  <div className="flex items-center border border-zinc-200 rounded-lg shrink-0">
                    <button type="button" onClick={() => updateCartCantidad(l.key, -1)} disabled={l.cantidad <= 1}
                      className="w-7 h-7 flex items-center justify-center text-zinc-500 hover:text-zinc-900 disabled:opacity-40">−</button>
                    <span className="w-6 text-center text-sm font-medium tabular-nums">{l.cantidad}</span>
                    <button type="button" onClick={() => updateCartCantidad(l.key, 1)} disabled={l.cantidad >= l.disponible}
                      className="w-7 h-7 flex items-center justify-center text-zinc-500 hover:text-zinc-900 disabled:opacity-40">+</button>
                  </div>
                )}
                <div className="flex items-center gap-1 shrink-0">
                  <input type="number" step="0.01" min="0" value={l.precio}
                    onChange={e => updateCartPrecio(l.key, e.target.value)}
                    className="w-20 border border-zinc-200 rounded-lg px-2 py-1 text-sm text-right font-semibold focus:outline-none focus:border-zinc-900" />
                  <span className="text-xs text-zinc-400">€</span>
                  {l.cantidad > 1 && (
                    <span className="text-xs text-zinc-400 whitespace-nowrap">
                      = {((parseFloat(l.precio) || 0) * l.cantidad).toFixed(2)} €
                    </span>
                  )}
                </div>
                <button onClick={() => removeFromCart(l.key)} className="text-zinc-300 hover:text-red-600 shrink-0">
                  <X size={16} />
                </button>
              </div>
            ))}
          </div>
          <div className="px-5 py-4 bg-zinc-50 flex items-center justify-between">
            <div>
              <div className="text-xs text-zinc-500">Total</div>
              <div className="text-2xl font-bold text-zinc-900">{cartTotal.toFixed(2)} €</div>
            </div>
            <Button onClick={() => setCheckoutOpen(true)}>Cobrar</Button>
          </div>
        </div>
      )}

      {checkoutOpen && (
        <CartCheckoutModal cart={cart} total={cartTotal}
          onConfirm={(client, pago, userId) => checkout(client, pago, userId)}
          onClose={() => setCheckoutOpen(false)} />
      )}

      {lastSale && (
        <SaleDoneModal sale={lastSale} shopConfig={shopConfig} onClose={() => setLastSale(null)} />
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB 1b — Reserves web (peticions de client a recollir i pagar a botiga)
// ═══════════════════════════════════════════════════════════════════════════

function horesRestants(reservedUntil) {
  const ms = new Date(reservedUntil).getTime() - Date.now();
  if (ms <= 0) return null;
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor((ms % 3_600_000) / 60_000);
  return { h, m, urgent: ms < 12 * 3_600_000 };
}

function ReservesWebTab() {
  const [reserves, setReserves] = useState([]);
  const [loading, setLoading] = useState(true);
  const [confirmReserva, setConfirmReserva] = useState(null);

  async function load() {
    setLoading(true);
    const r = await authFetch('/admin/peticiones/reserves-recollida');
    setReserves(r.ok ? await r.json() : []);
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  return (
    <div className="space-y-8">
      <OrdersTiendaSection />

      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-zinc-700">Peticions de client</h3>
        <ReservesList reserves={reserves} loading={loading} confirmReserva={confirmReserva}
          setConfirmReserva={setConfirmReserva} onSold={load} />
      </div>
    </div>
  );
}

function ReservesList({ reserves, loading, confirmReserva, setConfirmReserva, onSold }) {

  async function sell(reserva, precio, nombreCliente, metodoPago, userId) {
    const r = await authFetch('/admin/ventas-externas', {
      method: 'POST',
      body: JSON.stringify({
        item_id: reserva.item_id,
        canal: 'mostrador',
        metodo_pago: metodoPago,
        precio_venta: parseFloat(precio),
        fecha: new Date().toISOString(),
        nombre_cliente: nombreCliente || null,
        user_id: userId || null,
      }),
    });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      throw new Error(body.detail || 'No s\'ha pogut registrar la venda.');
    }
    setConfirmReserva(null);
    onSold();
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-500">
        Ja disponibles a botiga, pendents de recollir i pagar. Es reserven 72 hores.
      </p>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-10 text-center text-zinc-400 text-sm">Carregant…</div>
        ) : reserves.length === 0 ? (
          <div className="p-10 text-center text-zinc-400 text-sm">
            <Bell size={28} className="text-zinc-200 mx-auto mb-3" />
            Cap reserva pendent de recollir.
          </div>
        ) : (
          <div className="divide-y divide-zinc-100">
            {reserves.map(r => {
              const restant = r.reserved_until ? horesRestants(r.reserved_until) : null;
              return (
                <div key={r.peticion_id} className="flex items-center gap-4 p-4">
                  {r.imagen_url
                    ? <img src={r.imagen_url} alt="" className="w-14 h-14 rounded-xl object-cover shrink-0" />
                    : <div className="w-14 h-14 rounded-xl bg-zinc-100 flex items-center justify-center text-zinc-400 shrink-0"><Disc3 size={24} /></div>
                  }
                  <div className="flex-1 min-w-0">
                    <div className="font-bold text-zinc-900 text-base">{r.artista}</div>
                    <div className="text-zinc-600">{r.titulo}</div>
                    <div className="text-xs text-zinc-400 mt-0.5">{r.user_nombre || r.user_email}</div>
                  </div>
                  {restant && (
                    <div className={`flex items-center gap-1 text-xs font-medium shrink-0 ${restant.urgent ? 'text-red-600' : 'text-zinc-400'}`}>
                      <Clock size={12} /> {restant.h}h {restant.m}m
                    </div>
                  )}
                  <div className="text-right shrink-0">
                    <div className="text-xl font-bold text-zinc-900 mb-1">{r.precio} €</div>
                    <button onClick={() => setConfirmReserva(r)}
                      className="bg-primary hover:bg-zinc-800 text-white text-sm font-semibold px-4 py-1.5 rounded-lg transition-colors">
                      Vendre
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {confirmReserva && (
        <ConfirmModal
          item={{
            id: confirmReserva.item_id, artista: confirmReserva.artista, titulo: confirmReserva.titulo,
            imagen_url: confirmReserva.imagen_url, estado_disco: confirmReserva.estado_disco, precio: confirmReserva.precio,
          }}
          initialUser={{ id: confirmReserva.user_id, nombre: confirmReserva.user_nombre, email: confirmReserva.user_email }}
          onConfirm={(precio, client, pago, userId) => sell(confirmReserva, precio, client, pago, userId)}
          onClose={() => setConfirmReserva(null)} />
      )}
    </div>
  );
}

function OrdersTiendaSection() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [payOrder, setPayOrder] = useState(null);
  const [error, setError] = useState('');

  async function load() {
    setLoading(true);
    const r = await authFetch('/admin/orders/pendientes-tienda');
    setOrders(r.ok ? await r.json() : []);
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  async function cobrar(order, metodoPago, precio) {
    const payload = { metodo_pago: metodoPago };
    if (precio != null) payload.precio = parseFloat(precio);
    const r = await authFetch(`/admin/orders/${order.order_id}/marcar-pagado-tienda`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      throw new Error(body.detail || 'No s\'ha pogut cobrar la comanda.');
    }
    setPayOrder(null);
    load();
  }

  if (!loading && orders.length === 0) return null;

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-zinc-700">Comandes web · paga en recollir</h3>
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-2.5">{error}</div>
      )}
      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-10 text-center text-zinc-400 text-sm">Carregant…</div>
        ) : (
          <div className="divide-y divide-zinc-100">
            {orders.map(o => {
              const restant = o.reserved_until ? horesRestants(o.reserved_until) : null;
              return (
                <div key={o.order_id} className="flex items-center gap-4 p-4">
                  <div className="flex-1 min-w-0">
                    {o.items.map((it, idx) => (
                      <div key={it.item_id || idx} className="text-sm">
                        <span className="font-bold text-zinc-900">{it.artista}</span>
                        <span className="text-zinc-600"> — {it.titulo}</span>
                      </div>
                    ))}
                    <div className="text-xs text-zinc-400 mt-0.5">{o.email}</div>
                  </div>
                  {restant && (
                    <div className={`flex items-center gap-1 text-xs font-medium shrink-0 ${restant.urgent ? 'text-red-600' : 'text-zinc-400'}`}>
                      <Clock size={12} /> {restant.h}h {restant.m}m
                    </div>
                  )}
                  <div className="text-right shrink-0">
                    <div className="text-xl font-bold text-zinc-900 mb-1">{parseFloat(o.total).toFixed(2)} €</div>
                    <button onClick={() => setPayOrder(o)}
                      className="bg-primary hover:bg-zinc-800 text-white text-sm font-semibold px-4 py-1.5 rounded-lg transition-colors">
                      Cobrar
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {payOrder && (payOrder.items.length === 1 ? (
        <ConfirmModal
          item={{
            id: payOrder.items[0].item_id, artista: payOrder.items[0].artista, titulo: payOrder.items[0].titulo,
            imagen_url: payOrder.items[0].imagen_url, estado_disco: payOrder.items[0].estado_disco,
            precio: payOrder.items[0].precio,
          }}
          initialUser={payOrder.user_id ? { id: payOrder.user_id, nombre: payOrder.user_nombre, email: payOrder.email } : null}
          onConfirm={(precio, client, pago) => cobrar(payOrder, pago, precio)}
          onClose={() => setPayOrder(null)} />
      ) : (
        <OrderPaymentModal order={payOrder}
          onConfirm={(metodoPago) => cobrar(payOrder, metodoPago)}
          onClose={() => setPayOrder(null)} />
      ))}
    </div>
  );
}

function OrderPaymentModal({ order, onConfirm, onClose }) {
  const [pago, setPago] = useState('efectivo');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function handle() {
    setSaving(true);
    setError('');
    try {
      await onConfirm(pago);
    } catch (err) {
      setError(err.message || 'No s\'ha pogut cobrar la comanda.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm">
        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-200">
          <h3 className="font-bold text-zinc-900">Cobrar comanda</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 p-1 rounded-lg hover:bg-zinc-100"><X size={20} /></button>
        </div>
        <div className="p-5 space-y-4">
          <div className="bg-zinc-50 rounded-xl p-4 space-y-1">
            {order.items.map((it, idx) => (
              <div key={it.item_id || idx} className="text-sm text-zinc-700">
                <span className="font-medium">{it.artista}</span> — {it.titulo}
              </div>
            ))}
            <div className="text-xs text-zinc-400">{order.email}</div>
          </div>
          <div className="text-center text-3xl font-bold text-zinc-900">
            {parseFloat(order.total).toFixed(2)} €
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-700 mb-2">Mètode de pagament</label>
            <div className="grid grid-cols-2 gap-2">
              {[['efectivo', 'Efectiu', 'bg-green-500'], ['tarjeta', 'Targeta', 'bg-indigo-500']].map(([val, label, color]) => (
                <button key={val} type="button" onClick={() => setPago(val)}
                  className={`py-3 rounded-xl font-semibold text-sm transition-all border-2 ${
                    pago === val
                      ? `${color} text-white border-transparent shadow-md`
                      : 'bg-white text-zinc-600 border-zinc-200 hover:border-zinc-300'
                  }`}>
                  {label}
                </button>
              ))}
            </div>
          </div>
          {error && <p className="text-red-500 text-sm">{error}</p>}
          <div className="flex gap-3 pt-1">
            <Button type="button" variant="secondary" className="flex-1" onClick={onClose}>Cancel·lar</Button>
            <Button type="button" className={`flex-1 ${pago === 'efectivo' ? '' : 'bg-indigo-600 hover:bg-indigo-700'}`}
              disabled={saving} onClick={handle}>
              {saving ? 'Cobrant…' : `Cobrar · ${pago === 'efectivo' ? 'Efectiu' : 'Targeta'}`}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB 2 — Resum vendes
// ═══════════════════════════════════════════════════════════════════════════

const DATE_FILTERS = [
  { key: 'today',   label: k => k('tpv.resum.filter.today') },
  { key: 'days7',   label: k => k('tpv.resum.filter.days7') },
  { key: 'days30',  label: k => k('tpv.resum.filter.days30') },
  { key: 'all',     label: k => k('tpv.resum.filter.all_time') },
];

// Agrupa les línies planes de /admin/ventas-externas en tiquets (mateix
// ticket_id = mateixa operació de cobrament al TPV), a l'estil capçalera +
// línies de SAP: una venda individual és un tiquet d'1 línia, una cistella
// és un tiquet de N línies que comparteixen data/client/canal/pagament.
function agruparEnTiquets(sales) {
  const map = new Map();
  for (const v of sales) {
    let tk = map.get(v.ticket_id);
    if (!tk) {
      tk = {
        ticket_id: v.ticket_id, fecha: v.fecha, canal: v.canal, metodo_pago: v.metodo_pago,
        nombre_cliente: v.nombre_cliente, user_id: v.user_id, user_nom: v.user_nom,
        lines: [], total: 0, retornades: 0,
      };
      map.set(v.ticket_id, tk);
    }
    tk.lines.push(v);
    tk.total += parseFloat(v.precio_venta) || 0;
    if (v.devuelta) tk.retornades += 1;
  }
  return [...map.values()];
}

// Vincula (o desvincula) un usuari registrat a totes les línies d'un tiquet
// ja cobrat — útil quan al moment de vendre no es va triar client i es vol
// lligar més tard, per exemple per activar-li avantatges de fidelització.
function LinkUserModal({ ticket, onClose, onSaved }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [userQ, setUserQ] = useState('');
  const [userResults, setUserResults] = useState([]);
  const [selected, setSelected] = useState(null);
  const userDebounce = useRef(null);

  const actual = ticket.user_id ? { id: ticket.user_id, nombre: ticket.user_nom } : null;

  function handleUserQ(val) {
    setUserQ(val);
    setSelected(null);
    clearTimeout(userDebounce.current);
    if (val.length < 2) { setUserResults([]); return; }
    userDebounce.current = setTimeout(async () => {
      const r = await authFetch(`/admin/users/search?q=${encodeURIComponent(val)}`);
      setUserResults(r.ok ? await r.json() : []);
    }, 300);
  }

  async function desar(userId) {
    setSaving(true);
    setError('');
    try {
      const r = await authFetch(`/admin/ventas-externas/tickets/${ticket.ticket_id}/usuari`, {
        method: 'PATCH',
        body: JSON.stringify({ user_id: userId }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        setError(body.detail || 'No s\'ha pogut desar.');
        return;
      }
      onSaved();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm">
        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-200">
          <h3 className="font-bold text-zinc-900">Vincular a usuari</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 p-1 rounded-lg hover:bg-zinc-100"><X size={20} /></button>
        </div>
        <div className="p-5 space-y-4">
          <div className="text-sm text-zinc-500">Tiquet #{ticket.ticket_id.slice(0, 8)} · {ticket.total.toFixed(2)} €</div>

          {actual && (
            <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2">
              <div className="w-6 h-6 rounded-full bg-amber-200 text-amber-800 flex items-center justify-center text-xs font-bold shrink-0">
                {(actual.nombre || '?')[0].toUpperCase()}
              </div>
              <div className="flex-1 min-w-0 text-sm font-medium text-zinc-900 truncate">{actual.nombre ?? 'Usuari vinculat'}</div>
              <button type="button" disabled={saving} onClick={() => desar(null)}
                className="text-xs text-red-600 hover:underline shrink-0 disabled:opacity-50">
                Desvincular
              </button>
            </div>
          )}

          <div className="relative">
            <input value={userQ} onChange={e => handleUserQ(e.target.value)}
              placeholder={actual ? "Cerca per canviar d'usuari..." : 'Cerca per nom o email...'} autoFocus
              className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-zinc-900" />
            {userResults.length > 0 && (
              <div className="absolute z-10 w-full mt-1 bg-white border border-zinc-200 rounded-xl shadow-lg overflow-hidden max-h-56 overflow-y-auto">
                {userResults.map(u => (
                  <button key={u.id} type="button" onClick={() => { setSelected(u); setUserQ(u.nombre || u.email); setUserResults([]); }}
                    className="w-full text-left px-3 py-2.5 hover:bg-zinc-50 flex items-center gap-2 border-b border-zinc-50 last:border-0">
                    <div className="w-6 h-6 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center text-xs font-bold shrink-0">
                      {(u.nombre || u.email)[0].toUpperCase()}
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm text-zinc-900 truncate">{u.nombre || u.email}</div>
                      {u.nombre && <div className="text-xs text-zinc-400 truncate">{u.email}</div>}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {error && <p className="text-red-500 text-sm">{error}</p>}
          <div className="flex gap-3 pt-1">
            <Button type="button" variant="secondary" className="flex-1" onClick={onClose}>Cancel·lar</Button>
            <Button type="button" className="flex-1" disabled={!selected || saving} onClick={() => desar(selected.id)}>
              {saving ? 'Desant...' : 'Vincular'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ResumTab() {
  const t = useT();
  const shopConfig = useShopConfig();
  const [sales, setSales] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dateFilter, setDateFilter] = useState('days7');
  const [canalFilter, setCanalFilter] = useState('all');
  const [q, setQ] = useState('');
  const [returnVenta, setReturnVenta] = useState(null);
  const [expanded, setExpanded] = useState(new Set());
  const [linkTicket, setLinkTicket] = useState(null);
  const [printSale, setPrintSale] = useState(null);

  useEffect(() => {
    if (printSale) window.print();
  }, [printSale]);

  const load = useCallback(async () => {
    setLoading(true);
    let url = '/admin/ventas-externas';
    const params = new URLSearchParams();

    const now = new Date();
    if (dateFilter === 'today') params.set('desde', startOfDay(now).toISOString());
    else if (dateFilter === 'days7') params.set('desde', startOfDay(addDays(now, -7)).toISOString());
    else if (dateFilter === 'days30') params.set('desde', startOfDay(addDays(now, -30)).toISOString());
    if (canalFilter !== 'all') params.set('canal', canalFilter);
    if (q.trim()) params.set('q', q.trim());
    const qs = params.toString();
    if (qs) url += '?' + qs;

    const r = await authFetch(url);
    setSales(r.ok ? await r.json() : []);
    setLoading(false);
  }, [dateFilter, canalFilter, q]);

  useEffect(() => { load(); }, [load]);

  const tickets = useMemo(() => agruparEnTiquets(sales), [sales]);

  const columns = useMemo(() => ({
    fecha: { sortValue: tk => tk.fecha ?? '' },
    nombre_cliente: { sortValue: tk => (tk.nombre_cliente ?? '').toLowerCase() },
    metodo_pago: {
      sortValue: tk => t(metodePagamentInfo(tk.metodo_pago).key),
      filterValue: tk => t(metodePagamentInfo(tk.metodo_pago).key),
    },
    total: { sortValue: tk => tk.total },
  }), [t]);

  const { rows: ticketsSorted, sort, toggleSort, filters, setFilter, distinctValues } = useSortFilter(tickets, columns);

  function toggleExpand(id) {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex gap-1 bg-zinc-100 p-1 rounded-xl">
          {DATE_FILTERS.map(({ key, label }) => (
            <button key={key} onClick={() => setDateFilter(key)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${dateFilter === key ? 'bg-white text-zinc-900 shadow-sm' : 'text-zinc-500 hover:text-zinc-900'}`}>
              {label(t)}
            </button>
          ))}
        </div>
        <div className="flex gap-1 bg-zinc-100 p-1 rounded-xl">
          {[['all', '—'], ...Object.keys(CANAL_KEY).map(k => [k, t(CANAL_KEY[k])])].map(([key, label]) => (
            <button key={key} onClick={() => setCanalFilter(key)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${canalFilter === key ? 'bg-white text-zinc-900 shadow-sm' : 'text-zinc-500 hover:text-zinc-900'}`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
        <input value={q} onChange={e => setQ(e.target.value)}
          placeholder={t('tpv.resum.search_ph')}
          className="w-full pl-9 pr-4 py-2 border border-zinc-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-white" />
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-10 text-center text-zinc-400 text-sm">{t('common.loading')}</div>
        ) : tickets.length === 0 ? (
          <div className="p-10 text-center text-zinc-400 text-sm">{t('tpv.resum.no_sales')}</div>
        ) : (
          <>
            <div className="px-5 py-3 border-b border-zinc-100 flex items-center justify-between">
              <span className="text-sm text-zinc-500">
                {ticketsSorted.length} {t('tpv.resum.tickets_count')} · {sales.length} {t('tpv.resum.sales_count')}
              </span>
              <span className="font-bold text-zinc-900 whitespace-nowrap">{t('tpv.resum.total')}: {ticketsSorted.reduce((s, tk) => s + tk.total, 0).toFixed(2)} €</span>
            </div>
            <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-100">
                <tr>
                  <th className="px-2 py-2.5 w-8" />
                  <SortableTh label={t('tpv.col.datetime')} sortKey="fecha" sort={sort} onSort={toggleSort} />
                  <th className="px-4 py-2.5 text-left font-medium">{t('tpv.col.ticket')}</th>
                  <th className="px-4 py-2.5 text-left font-medium">{t('tpv.col.record')}</th>
                  <SortableTh label={t('tpv.col.client')} sortKey="nombre_cliente" sort={sort} onSort={toggleSort} />
                  <th className="px-4 py-2.5 text-left font-medium">{t('tpv.col.canal')}</th>
                  <SortableTh label={t('tpv.col.pago')} sortKey="metodo_pago" sort={sort} onSort={toggleSort}
                    filterOptions={distinctValues.metodo_pago} selected={filters.metodo_pago} onFilterChange={setFilter} />
                  <SortableTh label={t('tpv.col.price')} sortKey="total" sort={sort} onSort={toggleSort} align="right" />
                  <th className="px-2 py-2.5 w-10" />
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {ticketsSorted.flatMap(tk => {
                  const isOpen = expanded.has(tk.ticket_id);
                  const rows = [
                    <tr key={tk.ticket_id} className="hover:bg-zinc-50 cursor-pointer" onClick={() => toggleExpand(tk.ticket_id)}>
                      <td className="px-2 py-2.5 text-zinc-400">
                        {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                      </td>
                      <td className="px-4 py-2.5 text-zinc-500 whitespace-nowrap">
                        {new Date(tk.fecha).toLocaleString(undefined, { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-xs text-zinc-400">#{tk.ticket_id.slice(0, 8)}</td>
                      <td className="px-4 py-2.5">
                        {tk.lines.length === 1 ? (
                          tk.lines[0].artista ? (
                            <>
                              <span className="font-medium text-zinc-900">{tk.lines[0].artista}</span>
                              <span className="text-zinc-500"> — {tk.lines[0].titulo}</span>
                            </>
                          ) : (
                            <span className="text-zinc-900">{tk.lines[0].descripcion ?? '—'}</span>
                          )
                        ) : (
                          <span className="text-zinc-900">{tk.lines.length} {t('tpv.resum.articles')}</span>
                        )}
                        {tk.retornades > 0 && (
                          <span className="ml-2 text-xs text-amber-600">· {tk.retornades} {t('return.returned').toLowerCase()}</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-zinc-500">
                        <div>{tk.nombre_cliente ?? '—'}</div>
                        <button onClick={(e) => { e.stopPropagation(); setLinkTicket(tk); }}
                          className={`mt-0.5 inline-flex items-center gap-1 text-xs hover:underline ${tk.user_nom ? 'text-amber-700' : 'text-zinc-400'}`}>
                          {tk.user_nom ? <><UserIcon size={11} /> {tk.user_nom}</> : <><UserPlus size={11} /> Vincular</>}
                        </button>
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${CANAL_COLOR[tk.canal]}`}>
                          {t(CANAL_KEY[tk.canal])}
                        </span>
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${metodePagamentInfo(tk.metodo_pago).badge}`}>
                          {t(metodePagamentInfo(tk.metodo_pago).key)}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right font-semibold whitespace-nowrap">{tk.total.toFixed(2)} €</td>
                      <td className="px-2 py-2.5 text-right">
                        <button onClick={(e) => { e.stopPropagation(); setPrintSale({ items: tk.lines, metodo_pago: tk.metodo_pago, nombre_cliente: tk.nombre_cliente, fecha: tk.fecha }); }}
                          title="Imprimir tiquet"
                          className="text-zinc-400 hover:text-zinc-700 p-1 rounded-lg hover:bg-zinc-100">
                          <Printer size={14} />
                        </button>
                      </td>
                    </tr>,
                  ];
                  if (isOpen) {
                    rows.push(
                      <tr key={`${tk.ticket_id}-detail`}>
                        <td colSpan={9} className="bg-zinc-50/70 p-0">
                          <table className="w-full text-sm">
                            <tbody className="divide-y divide-zinc-100">
                              {tk.lines.map(v => (
                                <tr key={v.id}>
                                  <td className="pl-12 pr-4 py-2 w-1/2">
                                    {v.artista ? (
                                      <>
                                        <span className="font-medium text-zinc-900">{v.artista}</span>
                                        <span className="text-zinc-500"> — {v.titulo}</span>
                                      </>
                                    ) : (
                                      <span className="text-zinc-900">{v.descripcion ?? '—'}</span>
                                    )}
                                  </td>
                                  <td className="px-4 py-2 text-right font-medium text-zinc-700 whitespace-nowrap">{v.precio_venta} €</td>
                                  <td className="px-4 py-2 text-right w-32">
                                    {v.devuelta ? (
                                      <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-zinc-100 text-zinc-500">
                                        {t('return.returned')}
                                      </span>
                                    ) : v.item_id ? (
                                      <button onClick={(e) => { e.stopPropagation(); setReturnVenta(v); }}
                                        className="flex items-center gap-1 text-xs font-semibold text-amber-600 hover:text-amber-700 border border-amber-200 rounded-lg px-2 py-1 hover:bg-amber-50 transition-colors ml-auto">
                                        <RotateCcw size={12} /> {t('return.btn')}
                                      </button>
                                    ) : null}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </td>
                      </tr>,
                    );
                  }
                  return rows;
                })}
              </tbody>
            </table>
            </div>
          </>
        )}
      </div>

      {returnVenta && (
        <ReturnSaleModal
          sale={{ item_id: returnVenta.item_id, artista: returnVenta.artista, titulo: returnVenta.titulo,
                  precio: returnVenta.precio_venta, nombre_cliente: returnVenta.nombre_cliente,
                  venta_externa_id: returnVenta.id }}
          onClose={() => setReturnVenta(null)}
          onSaved={() => { setReturnVenta(null); load(); }} />
      )}

      {linkTicket && (
        <LinkUserModal ticket={linkTicket} onClose={() => setLinkTicket(null)}
          onSaved={() => { setLinkTicket(null); load(); }} />
      )}

      {printSale && <ReceiptPrintArea sale={printSale} shopConfig={shopConfig} />}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB 3 — Caixa
// ═══════════════════════════════════════════════════════════════════════════

function CaixaTab() {
  const t = useT();
  const [activa, setActiva] = useState(undefined); // undefined=loading, null=cap
  const [sessions, setSessions] = useState([]);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [fondo, setFondo] = useState('');
  const [conteo, setConteo] = useState('');
  const [notas, setNotas] = useState('');
  const [saving, setSaving] = useState(false);
  const [moviments, setMoviments] = useState([]);
  const [showMovForm, setShowMovForm] = useState(false);
  const [movTipo, setMovTipo] = useState('entrada');
  const [movConcepto, setMovConcepto] = useState('');
  const [movImporte, setMovImporte] = useState('');
  const [savingMov, setSavingMov] = useState(false);
  const [error, setError] = useState('');

  async function loadAll() {
    try {
      const [rA, rS, rM] = await Promise.all([
        authFetch('/admin/caja/activa'),
        authFetch('/admin/caja/sessions'),
        authFetch('/admin/caja/movimientos'),
      ]);
      if (!rA.ok || !rS.ok || !rM.ok) throw new Error();
      setActiva((await rA.json()) ?? null);
      setSessions(await rS.json());
      setMoviments(await rM.json());
      setError('');
    } catch {
      setActiva(null);
      setError(t('caixa.load_error'));
    } finally {
      setLoadingSessions(false);
    }
  }

  useEffect(() => { loadAll(); }, []);

  const sessionsTancades = useMemo(() => sessions.filter(s => s.fecha_cierre), [sessions]);
  const sessionsColumns = useMemo(() => ({
    fecha_apertura: { sortValue: s => s.fecha_apertura ?? '' },
    fondo_inicial: { sortValue: s => parseFloat(s.fondo_inicial) || 0 },
    total_ventas_efectivo: { sortValue: s => parseFloat(s.total_ventas_efectivo) || 0 },
    total_entradas: { sortValue: s => parseFloat(s.total_entradas) || 0 },
    total_salidas: { sortValue: s => parseFloat(s.total_salidas) || 0 },
    conteo_real: { sortValue: s => s.conteo_real != null ? parseFloat(s.conteo_real) : null },
    diferencia: { sortValue: s => s.diferencia != null ? parseFloat(s.diferencia) : null },
  }), []);
  const { rows: sessionsSorted, sort: sessionsSort, toggleSort: toggleSessionsSort } = useSortFilter(sessionsTancades, sessionsColumns);

  // Vendes en efectiu d'aquesta sessió (per mostrar la llista)
  const [ventesHui, setVentesHui] = useState([]);
  useEffect(() => {
    if (!activa) return;
    authFetch(`/admin/ventas-externas?metodo_pago=efectivo&desde=${encodeURIComponent(activa.fecha_apertura)}`)
      .then(r => (r.ok ? r.json() : []))
      .then(setVentesHui);
  }, [activa]);

  // Totals per calcular l'esperat en caixa
  const totalEfectiu = ventesHui.reduce((s, v) => s + parseFloat(v.precio_venta), 0);
  const totalEntrades = activa ? parseFloat(activa.total_entradas || 0) : 0;
  const totalSortides = activa ? parseFloat(activa.total_salidas || 0) : 0;
  const efectiuEsper = activa
    ? parseFloat(activa.fondo_inicial) + totalEfectiu + totalEntrades - totalSortides
    : 0;

  async function obrir(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    const r = await authFetch('/admin/caja/apertura', {
      method: 'POST',
      body: JSON.stringify({ fecha_apertura: new Date().toISOString(), fondo_inicial: parseFloat(fondo), notas: notas || null }),
    });
    setSaving(false);
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      setError(body.detail || t('caixa.save_error'));
      return;
    }
    setFondo(''); setNotas('');
    loadAll();
  }

  async function tancar(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    const r = await authFetch(`/admin/caja/cierre/${activa.id}`, {
      method: 'POST',
      body: JSON.stringify({ conteo_real: parseFloat(conteo), notas: notas || null }),
    });
    setSaving(false);
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      setError(body.detail || t('caixa.save_error'));
      return;
    }
    setConteo(''); setNotas('');
    loadAll();
  }

  async function addMoviment(e) {
    e.preventDefault();
    setSavingMov(true);
    setError('');
    const r = await authFetch('/admin/caja/movimientos', {
      method: 'POST',
      body: JSON.stringify({
        tipo: movTipo,
        concepto: movConcepto,
        importe: parseFloat(movImporte),
        fecha: new Date().toISOString(),
      }),
    });
    setSavingMov(false);
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      setError(body.detail || t('caixa.save_error'));
      return;
    }
    setShowMovForm(false);
    setMovConcepto(''); setMovImporte('');
    loadAll();
  }

  if (activa === undefined) {
    return <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading')}</div>;
  }

  return (
    <div className="space-y-5">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-2.5">{error}</div>
      )}

      {/* Sessió activa o formulari d'obertura */}
      {activa === null ? (
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm p-6">
          <div className="text-sm text-zinc-500 mb-4">{t('caixa.no_session')}</div>
          <form onSubmit={obrir} className="space-y-4 max-w-xs">
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('caixa.fondo_inicial')}</label>
              <input type="number" step="0.01" min="0" required value={fondo} onChange={e => setFondo(e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('common.notes')}</label>
              <input value={notas} onChange={e => setNotas(e.target.value)}
                className="w-full border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
            </div>
            <Button type="submit" disabled={saving}>{saving ? t('caixa.opening') : t('caixa.open')}</Button>
          </form>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
          {/* Capçalera sessió */}
          <div className="px-5 py-4 bg-green-50 border-b border-green-100 flex items-center justify-between">
            <div>
              <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-green-100 text-green-700 mr-2">
                {t('caixa.status.open')}
              </span>
              <span className="text-sm text-zinc-600">
                {t('caixa.opened_at')} {new Date(activa.fecha_apertura).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          </div>

          {/* Stats */}
          <div className="p-5 grid grid-cols-2 sm:grid-cols-5 gap-3 border-b border-zinc-100">
            <CaixaStat label={t('caixa.col.fondo')} value={`${parseFloat(activa.fondo_inicial).toFixed(2)} €`} />
            <CaixaStat label={t('caixa.total_ventas')} value={`${totalEfectiu.toFixed(2)} €`} highlight />
            <CaixaStat label={t('caixa.col.entrades')} value={`+${totalEntrades.toFixed(2)} €`} color="green" />
            <CaixaStat label={t('caixa.col.sortides')} value={`−${totalSortides.toFixed(2)} €`} color="red" />
            <CaixaStat label={t('caixa.active_session')} value={`${efectiuEsper.toFixed(2)} €`} />
          </div>

          {/* Vendes d'aquesta sessió */}
          {ventesHui.length > 0 && (
            <div className="px-5 pb-1">
              <div className="text-xs text-zinc-400 font-medium pt-3 pb-2 uppercase tracking-wide">
                {ventesHui.length} {t('tpv.resum.sales_count')}
              </div>
              <div className="space-y-0.5">
                {ventesHui.map(v => (
                  <div key={v.id} className="flex items-center gap-3 text-sm py-1">
                    <span className="text-zinc-400 w-12 shrink-0 text-xs">{new Date(v.fecha).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}</span>
                    <span className="font-medium text-zinc-900 flex-1 truncate">{v.artista ? `${v.artista} — ${v.titulo}` : v.descripcion}</span>
                    {v.nombre_cliente && <span className="text-zinc-400 text-xs truncate max-w-[100px]">{v.nombre_cliente}</span>}
                    <span className="font-semibold text-zinc-900 shrink-0">{parseFloat(v.precio_venta).toFixed(2)} €</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Moviments de caixa */}
          <div className="px-5 py-4 border-t border-zinc-100">
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs font-semibold text-zinc-500 uppercase tracking-wide">{t('caixa.mov.title')}</div>
              {!showMovForm && (
                <button onClick={() => setShowMovForm(true)}
                  className="text-xs text-amber-600 hover:text-amber-700 font-medium">
                  + {t('caixa.mov.new')}
                </button>
              )}
            </div>

            {showMovForm && (
              <form onSubmit={addMoviment} className="bg-zinc-50 rounded-xl p-4 mb-3 space-y-3">
                {/* Tipus entrada/sortida */}
                <div className="flex gap-2">
                  {['entrada', 'salida'].map(tipo => (
                    <button key={tipo} type="button"
                      onClick={() => setMovTipo(tipo)}
                      className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors border ${
                        movTipo === tipo
                          ? tipo === 'entrada'
                            ? 'bg-green-50 border-green-400 text-green-700'
                            : 'bg-red-50 border-red-400 text-red-700'
                          : 'border-zinc-200 text-zinc-500 hover:border-zinc-300'
                      }`}>
                      {t(`caixa.mov.${tipo}`)}
                    </button>
                  ))}
                </div>
                <div className="flex gap-2">
                  <input
                    placeholder={t('caixa.mov.concepto_ph')}
                    required value={movConcepto} onChange={e => setMovConcepto(e.target.value)}
                    className="flex-1 border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
                  <input type="number" step="0.01" min="0.01" required placeholder="0.00"
                    value={movImporte} onChange={e => setMovImporte(e.target.value)}
                    className="w-28 border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900" />
                </div>
                <div className="flex gap-2">
                  <Button type="submit" disabled={savingMov}>
                    {savingMov ? t('caixa.mov.adding') : t('caixa.mov.add')}
                  </Button>
                  <button type="button" onClick={() => { setShowMovForm(false); setMovConcepto(''); setMovImporte(''); }}
                    className="px-3 py-1.5 text-sm text-zinc-500 hover:text-zinc-700">
                    {t('common.cancel')}
                  </button>
                </div>
              </form>
            )}

            {moviments.length === 0 && !showMovForm ? (
              <div className="text-xs text-zinc-400 py-1">{t('caixa.mov.no_movements')}</div>
            ) : (
              <div className="space-y-1">
                {moviments.map(m => (
                  <div key={m.id} className="flex items-center gap-3 text-sm py-1">
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium shrink-0 ${
                      m.tipo === 'entrada' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                    }`}>
                      {t(`caixa.mov.${m.tipo}`)}
                    </span>
                    <span className="flex-1 text-zinc-700">{m.concepto}</span>
                    <span className="text-xs text-zinc-400 shrink-0">
                      {new Date(m.fecha).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                    </span>
                    <span className={`font-semibold shrink-0 ${m.tipo === 'entrada' ? 'text-green-700' : 'text-red-600'}`}>
                      {m.tipo === 'entrada' ? '+' : '−'}{parseFloat(m.importe).toFixed(2)} €
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Formulari de tancament */}
          <div className="px-5 py-4 bg-zinc-50 border-t border-zinc-100">
            <div className="text-sm font-semibold text-zinc-700 mb-3">{t('caixa.close')}</div>
            <form onSubmit={tancar} className="flex items-end gap-3 flex-wrap">
              <div>
                <label className="block text-xs text-zinc-500 mb-1">{t('caixa.conteo_real')}</label>
                <input type="number" step="0.01" min="0" required value={conteo} onChange={e => setConteo(e.target.value)}
                  className="border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 w-36" />
              </div>
              <div>
                <label className="block text-xs text-zinc-500 mb-1">{t('common.notes')}</label>
                <input value={notas} onChange={e => setNotas(e.target.value)}
                  className="border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 w-48" />
              </div>
              <Button type="submit" variant="danger" disabled={saving}>
                {saving ? t('caixa.closing') : t('caixa.close')}
              </Button>
            </form>
          </div>
        </div>
      )}

      {/* Historial */}
      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-zinc-100">
          <h3 className="font-semibold text-zinc-900 text-sm">{t('caixa.history')}</h3>
        </div>
        {loadingSessions ? (
          <div className="p-8 text-center text-zinc-400 text-sm">{t('common.loading')}</div>
        ) : sessionsTancades.length === 0 ? (
          <div className="p-8 text-center text-zinc-400 text-sm">{t('caixa.no_history')}</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[600px]">
              <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-100">
                <tr>
                  <SortableTh label={t('caixa.col.date')} sortKey="fecha_apertura" sort={sessionsSort} onSort={toggleSessionsSort} />
                  <SortableTh label={t('caixa.col.fondo')} sortKey="fondo_inicial" sort={sessionsSort} onSort={toggleSessionsSort} align="right" />
                  <SortableTh label={t('caixa.col.ventas')} sortKey="total_ventas_efectivo" sort={sessionsSort} onSort={toggleSessionsSort} align="right" />
                  <SortableTh label={t('caixa.col.entrades')} sortKey="total_entradas" sort={sessionsSort} onSort={toggleSessionsSort} align="right" />
                  <SortableTh label={t('caixa.col.sortides')} sortKey="total_salidas" sort={sessionsSort} onSort={toggleSessionsSort} align="right" />
                  <SortableTh label={t('caixa.col.conteo')} sortKey="conteo_real" sort={sessionsSort} onSort={toggleSessionsSort} align="right" />
                  <SortableTh label={t('caixa.col.diferencia')} sortKey="diferencia" sort={sessionsSort} onSort={toggleSessionsSort} align="right" />
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {sessionsSorted.map(s => {
                  const difNum = s.diferencia !== null ? parseFloat(s.diferencia) : null;
                  return (
                    <tr key={s.id} className="hover:bg-zinc-50">
                      <td className="px-4 py-2.5 text-zinc-500">
                        {new Date(s.fecha_apertura).toLocaleDateString(undefined, { day: '2-digit', month: '2-digit', year: '2-digit' })}
                        <span className="text-zinc-400 ml-1 text-xs">
                          {new Date(s.fecha_apertura).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right">{parseFloat(s.fondo_inicial).toFixed(2)} €</td>
                      <td className="px-4 py-2.5 text-right">{s.total_ventas_efectivo ? parseFloat(s.total_ventas_efectivo).toFixed(2) : '0.00'} €</td>
                      <td className="px-4 py-2.5 text-right text-green-700">
                        {s.total_entradas && parseFloat(s.total_entradas) > 0 ? `+${parseFloat(s.total_entradas).toFixed(2)} €` : '—'}
                      </td>
                      <td className="px-4 py-2.5 text-right text-red-600">
                        {s.total_salidas && parseFloat(s.total_salidas) > 0 ? `−${parseFloat(s.total_salidas).toFixed(2)} €` : '—'}
                      </td>
                      <td className="px-4 py-2.5 text-right">{s.conteo_real ? parseFloat(s.conteo_real).toFixed(2) : '—'} €</td>
                      <td className={`px-4 py-2.5 text-right font-semibold ${difNum === null ? '' : difNum < 0 ? 'text-red-600' : difNum > 0 ? 'text-amber-600' : 'text-green-600'}`}>
                        {difNum === null ? '—' : `${difNum >= 0 ? '+' : ''}${difNum.toFixed(2)} €`}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function CaixaStat({ label, value, highlight, color }) {
  const bg = highlight ? 'bg-amber-50' : color === 'green' ? 'bg-green-50' : color === 'red' ? 'bg-red-50' : 'bg-zinc-50';
  const text = highlight ? 'text-amber-700' : color === 'green' ? 'text-green-700' : color === 'red' ? 'text-red-600' : 'text-zinc-900';
  return (
    <div className={`rounded-xl p-3 ${bg}`}>
      <div className="text-xs text-zinc-500 mb-1 truncate">{label}</div>
      <div className={`text-lg font-bold ${text}`}>{value}</div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Modals shared
// ═══════════════════════════════════════════════════════════════════════════

function ConfirmModal({ item, onConfirm, onClose, initialUser = null }) {
  const t = useT();
  const [precio, setPrecio] = useState(item.precio);
  const [client, setClient] = useState(initialUser ? (initialUser.nombre || '') : '');
  const [pago, setPago] = useState('efectivo');
  const [selling, setSelling] = useState(false);
  const [error, setError] = useState('');
  // Selector d'usuari registrat
  const [userQ, setUserQ] = useState('');
  const [userResults, setUserResults] = useState([]);
  const [linkedUser, setLinkedUser] = useState(initialUser); // { id, nombre, email }
  const userDebounce = useRef(null);

  function handleUserQ(val) {
    setUserQ(val);
    setLinkedUser(null);
    clearTimeout(userDebounce.current);
    if (val.length < 2) { setUserResults([]); return; }
    userDebounce.current = setTimeout(async () => {
      const r = await authFetch(`/admin/users/search?q=${encodeURIComponent(val)}`);
      setUserResults(r.ok ? await r.json() : []);
    }, 300);
  }

  function selectUser(u) {
    setLinkedUser(u);
    setUserQ(u.nombre || u.email);
    setUserResults([]);
    if (!client) setClient(u.nombre || '');
  }

  function clearUser() {
    setLinkedUser(null);
    setUserQ('');
    setUserResults([]);
  }

  async function handle(e) {
    e.preventDefault();
    setSelling(true);
    setError('');
    try {
      await onConfirm(precio, client, pago, linkedUser?.id || null);
    } catch (err) {
      setError(err.message || t('tpv.sell_error'));
    } finally {
      setSelling(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm">
        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-200">
          <h3 className="font-bold text-zinc-900">{t('tpv.confirm.title')}</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 p-1 rounded-lg hover:bg-zinc-100"><X size={20} /></button>
        </div>
        <div className="p-5 space-y-4">
          <div className="flex items-center gap-4 p-4 bg-zinc-50 rounded-xl">
            {item.imagen_url
              ? <img src={item.imagen_url} alt="" className="w-16 h-16 rounded-xl object-cover shrink-0" />
              : <div className="w-16 h-16 rounded-xl bg-zinc-200 flex items-center justify-center text-zinc-400 shrink-0"><Disc3 size={28} /></div>
            }
            <div>
              <div className="font-bold text-zinc-900">{item.artista}</div>
              <div className="text-zinc-600 text-sm">{item.titulo}</div>
              <div className="text-xs text-zinc-400 mt-1">{item.estado_disco ?? '—'}</div>
            </div>
          </div>
          <form onSubmit={handle} className="space-y-4">
            {/* Mètode de pagament */}
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-2">{t('tpv.confirm.pago')}</label>
              <div className="grid grid-cols-2 gap-2">
                {METODES_PAGAMENT.map(({ val, key, color }) => (
                  <button key={val} type="button" onClick={() => setPago(val)}
                    className={`py-3 rounded-xl font-semibold text-sm transition-all border-2 ${
                      pago === val
                        ? `${color} text-white border-transparent shadow-md`
                        : 'bg-white text-zinc-600 border-zinc-200 hover:border-zinc-300'
                    }`}>
                    {t(key)}
                  </button>
                ))}
              </div>
            </div>
            {/* Preu */}
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-2">{t('tpv.confirm.price')}</label>
              <input type="number" step="0.01" min="0" required value={precio} onChange={e => setPrecio(e.target.value)}
                className="w-full border-2 border-zinc-200 rounded-xl px-4 py-3 text-xl font-bold text-center focus:outline-none focus:border-zinc-900" />
            </div>
            {/* Vinclar a usuari registrat */}
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">Usuari registrat <span className="text-zinc-400 font-normal">(opcional)</span></label>
              {linkedUser ? (
                <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2">
                  <div className="w-6 h-6 rounded-full bg-amber-200 text-amber-800 flex items-center justify-center text-xs font-bold shrink-0">
                    {(linkedUser.nombre || linkedUser.email)[0].toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-zinc-900 truncate">{linkedUser.nombre || linkedUser.email}</div>
                    {linkedUser.nombre && <div className="text-xs text-zinc-400 truncate">{linkedUser.email}</div>}
                  </div>
                  <button type="button" onClick={clearUser} className="text-zinc-400 hover:text-zinc-600 shrink-0">
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <div className="relative">
                  <input value={userQ} onChange={e => handleUserQ(e.target.value)}
                    placeholder="Cerca per nom o email..."
                    className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-zinc-900" />
                  {userResults.length > 0 && (
                    <div className="absolute z-10 w-full mt-1 bg-white border border-zinc-200 rounded-xl shadow-lg overflow-hidden">
                      {userResults.map(u => (
                        <button key={u.id} type="button" onClick={() => selectUser(u)}
                          className="w-full text-left px-3 py-2.5 hover:bg-zinc-50 flex items-center gap-2 border-b border-zinc-50 last:border-0">
                          <div className="w-6 h-6 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center text-xs font-bold shrink-0">
                            {(u.nombre || u.email)[0].toUpperCase()}
                          </div>
                          <div className="min-w-0">
                            <div className="text-sm text-zinc-900 truncate">{u.nombre || u.email}</div>
                            {u.nombre && <div className="text-xs text-zinc-400 truncate">{u.email}</div>}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
            {/* Nom client manual */}
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('tpv.confirm.client')} <span className="text-zinc-400 font-normal">(opcional)</span></label>
              <input value={client} onChange={e => setClient(e.target.value)}
                placeholder={t('tpv.confirm.client_ph')}
                className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-zinc-900" />
            </div>
            {error && <p className="text-red-500 text-sm">{error}</p>}
            <div className="flex gap-3 pt-1">
              <Button type="button" variant="secondary" className="flex-1" onClick={onClose}>{t('common.cancel')}</Button>
              <Button type="submit" className={`flex-1 ${metodePagamentInfo(pago).btn}`} disabled={selling}>
                {selling ? t('tpv.confirm.selling') : `${t('tpv.confirm.sell')} · ${t(metodePagamentInfo(pago).key)}`}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

// Cobrament de la cistella sencera: mateix formulari de pagament/client que
// ConfirmModal, però amb el llistat de la cistella (preus ja fixats allà)
// en lloc d'un únic ítem amb el seu propi camp de preu.
function CartCheckoutModal({ cart, total, onConfirm, onClose }) {
  const t = useT();
  const [client, setClient] = useState('');
  const [pago, setPago] = useState('efectivo');
  const [selling, setSelling] = useState(false);
  const [error, setError] = useState('');
  const [userQ, setUserQ] = useState('');
  const [userResults, setUserResults] = useState([]);
  const [linkedUser, setLinkedUser] = useState(null);
  const userDebounce = useRef(null);

  function handleUserQ(val) {
    setUserQ(val);
    setLinkedUser(null);
    clearTimeout(userDebounce.current);
    if (val.length < 2) { setUserResults([]); return; }
    userDebounce.current = setTimeout(async () => {
      const r = await authFetch(`/admin/users/search?q=${encodeURIComponent(val)}`);
      setUserResults(r.ok ? await r.json() : []);
    }, 300);
  }

  function selectUser(u) {
    setLinkedUser(u);
    setUserQ(u.nombre || u.email);
    setUserResults([]);
    if (!client) setClient(u.nombre || '');
  }

  function clearUser() {
    setLinkedUser(null);
    setUserQ('');
    setUserResults([]);
  }

  async function handle(e) {
    e.preventDefault();
    setSelling(true);
    setError('');
    try {
      await onConfirm(client, pago, linkedUser?.id || null);
    } catch (err) {
      setError(err.message || t('tpv.sell_error'));
    } finally {
      setSelling(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-200 shrink-0">
          <h3 className="font-bold text-zinc-900">Cobrar cistella</h3>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 p-1 rounded-lg hover:bg-zinc-100"><X size={20} /></button>
        </div>
        <div className="p-5 space-y-4 overflow-y-auto">
          <div className="bg-zinc-50 rounded-xl p-4 space-y-2">
            {cart.map(l => (
              <div key={l.key} className="flex items-center justify-between gap-3 text-sm">
                <span className="text-zinc-700 truncate">{l.manual ? l.descripcion : `${l.artista} — ${l.titulo}`}</span>
                <span className="font-semibold text-zinc-900 shrink-0">{(parseFloat(l.precio) || 0).toFixed(2)} €</span>
              </div>
            ))}
            <div className="border-t border-zinc-200 pt-2 flex items-center justify-between font-bold text-zinc-900">
              <span>Total · {cart.length} {cart.length === 1 ? 'article' : 'articles'}</span>
              <span>{total.toFixed(2)} €</span>
            </div>
          </div>
          <form onSubmit={handle} className="space-y-4">
            {/* Mètode de pagament */}
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-2">{t('tpv.confirm.pago')}</label>
              <div className="grid grid-cols-2 gap-2">
                {METODES_PAGAMENT.map(({ val, key, color }) => (
                  <button key={val} type="button" onClick={() => setPago(val)}
                    className={`py-3 rounded-xl font-semibold text-sm transition-all border-2 ${
                      pago === val
                        ? `${color} text-white border-transparent shadow-md`
                        : 'bg-white text-zinc-600 border-zinc-200 hover:border-zinc-300'
                    }`}>
                    {t(key)}
                  </button>
                ))}
              </div>
            </div>
            {/* Vinclar a usuari registrat */}
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">Usuari registrat <span className="text-zinc-400 font-normal">(opcional)</span></label>
              {linkedUser ? (
                <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2">
                  <div className="w-6 h-6 rounded-full bg-amber-200 text-amber-800 flex items-center justify-center text-xs font-bold shrink-0">
                    {(linkedUser.nombre || linkedUser.email)[0].toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-zinc-900 truncate">{linkedUser.nombre || linkedUser.email}</div>
                    {linkedUser.nombre && <div className="text-xs text-zinc-400 truncate">{linkedUser.email}</div>}
                  </div>
                  <button type="button" onClick={clearUser} className="text-zinc-400 hover:text-zinc-600 shrink-0">
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <div className="relative">
                  <input value={userQ} onChange={e => handleUserQ(e.target.value)}
                    placeholder="Cerca per nom o email..."
                    className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-zinc-900" />
                  {userResults.length > 0 && (
                    <div className="absolute z-10 w-full mt-1 bg-white border border-zinc-200 rounded-xl shadow-lg overflow-hidden">
                      {userResults.map(u => (
                        <button key={u.id} type="button" onClick={() => selectUser(u)}
                          className="w-full text-left px-3 py-2.5 hover:bg-zinc-50 flex items-center gap-2 border-b border-zinc-50 last:border-0">
                          <div className="w-6 h-6 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center text-xs font-bold shrink-0">
                            {(u.nombre || u.email)[0].toUpperCase()}
                          </div>
                          <div className="min-w-0">
                            <div className="text-sm text-zinc-900 truncate">{u.nombre || u.email}</div>
                            {u.nombre && <div className="text-xs text-zinc-400 truncate">{u.email}</div>}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
            {/* Nom client manual */}
            <div>
              <label className="block text-sm font-medium text-zinc-700 mb-1">{t('tpv.confirm.client')} <span className="text-zinc-400 font-normal">(opcional)</span></label>
              <input value={client} onChange={e => setClient(e.target.value)}
                placeholder={t('tpv.confirm.client_ph')}
                className="w-full border border-zinc-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-zinc-900" />
            </div>
            {error && <p className="text-red-500 text-sm">{error}</p>}
            <div className="flex gap-3 pt-1">
              <Button type="button" variant="secondary" className="flex-1" onClick={onClose}>{t('common.cancel')}</Button>
              <Button type="submit" className={`flex-1 ${metodePagamentInfo(pago).btn}`} disabled={selling}>
                {selling ? t('tpv.confirm.selling') : `${t('tpv.confirm.sell')} · ${total.toFixed(2)} €`}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

// sale = { items: [VentaExternaOut...], metodo_pago, nombre_cliente, fecha }
// items pot ser 1 (una sola còpia) o més (venda de cistella): el tiquet
// s'imprimeix sempre com un únic rebut amb totes les línies.
// sale = { items: [VentaExternaOut...], metodo_pago, nombre_cliente, fecha }.
// Reutilitzat des de SaleDoneModal (just després de cobrar) i des de Resum
// vendes (reimprimir un tiquet ja fet): contingut invisible en pantalla,
// mostrat només via window.print() (veure @media print a globals.css).
function ReceiptPrintArea({ sale, shopConfig }) {
  const fecha = new Date(sale.fecha || Date.now());
  const items = sale.items ?? [];
  const total = items.reduce((s, it) => s + parseFloat(it.precio_venta ?? 0), 0);
  const ivaTotal = items.reduce((s, it) => s + (it.iva_import != null ? parseFloat(it.iva_import) : 0), 0);

  // Desglossament per tipus d'IVA (base imposable + quota), agrupat per
  // percentatge — una venda pot barrejar línies al 21% i al 4% (p.ex. un
  // disc + un llibre) en un mateix tiquet.
  const ivaPerTipus = {};
  for (const it of items) {
    if (it.iva_pct == null || it.iva_import == null) continue;
    const pct = parseFloat(it.iva_pct);
    const quota = parseFloat(it.iva_import);
    const preu = parseFloat(it.precio_venta ?? 0);
    if (!ivaPerTipus[pct]) ivaPerTipus[pct] = { base: 0, quota: 0 };
    ivaPerTipus[pct].base += preu - quota;
    ivaPerTipus[pct].quota += quota;
  }
  const tipusIva = Object.keys(ivaPerTipus).map(Number).sort((a, b) => b - a);

  return (
    <div id="print-area">
      <div className="receipt-ticket">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/ultralocal-logo-tiquet.png" alt="Ultra-Local Records" className="receipt-logo" />
        {shopConfig && (
          <>
            {shopConfig.nif && <div className="text-center">NIF {shopConfig.nif}</div>}
            <div className="text-center">{shopConfig.adreca}</div>
            {shopConfig.telefon && <div className="text-center">{shopConfig.telefon}</div>}
            <hr />
          </>
        )}
        <div>{fecha.toLocaleDateString()} {fecha.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}</div>
        <div>Ref. {items[0]?.ticket_id ? items[0].ticket_id.slice(0, 8) : '—'}</div>
        <hr />
        {items.map((it, idx) => (
          <div key={it.id || idx} className="receipt-row">
            <div>
              {it.artista ? (
                <>
                  <div className="font-semibold">{it.artista}{it.cantidad > 1 ? ` ×${it.cantidad}` : ''}</div>
                  <div>{it.titulo}</div>
                  {it.estado_disco && <div>Estat: {it.estado_disco}</div>}
                </>
              ) : (
                <div className="font-semibold">{it.descripcion}</div>
              )}
            </div>
            <div>{parseFloat(it.precio_venta ?? 0).toFixed(2)} €</div>
          </div>
        ))}
        <hr />
        {items.length > 1 && (
          <div className="receipt-row"><span>Total</span><span>{total.toFixed(2)} €</span></div>
        )}
        {tipusIva.length > 0 && (
          <>
            <hr />
            {tipusIva.map((pct) => (
              <div key={pct}>
                <div className="receipt-row"><span>Base imposable {pct}%</span><span>{ivaPerTipus[pct].base.toFixed(2)} €</span></div>
                <div className="receipt-row"><span>Quota IVA {pct}%</span><span>{ivaPerTipus[pct].quota.toFixed(2)} €</span></div>
              </div>
            ))}
            {tipusIva.length > 1 && (
              <div className="receipt-row font-semibold"><span>Total IVA</span><span>{ivaTotal.toFixed(2)} €</span></div>
            )}
          </>
        )}
        <div className="receipt-row"><span>Pagament</span><span>{metodePagamentInfo(sale.metodo_pago).label_ca}</span></div>
        {sale.nombre_cliente && (
          <div className="receipt-row"><span>Client</span><span>{sale.nombre_cliente}</span></div>
        )}
        <hr />
        <div className="text-center">Gràcies per la compra!</div>
      </div>
    </div>
  );
}

function SaleDoneModal({ sale, shopConfig, onClose }) {
  const items = sale.items ?? [];
  const total = items.reduce((s, it) => s + parseFloat(it.precio_venta ?? 0), 0);

  return (
    <>
      <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6 text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-green-100 text-green-600 flex items-center justify-center mx-auto">
            <Check size={24} />
          </div>
          <div>
            <h3 className="font-bold text-zinc-900 text-lg">Venda registrada</h3>
            <p className="text-sm text-zinc-500 mt-1">
              {items.length === 1
                ? (items[0].artista ? `${items[0].artista} — ${items[0].titulo}` : items[0].descripcion)
                : `${items.length} articles · ${total.toFixed(2)} €`}
            </p>
          </div>
          <div className="flex gap-3">
            <button onClick={onClose}
              className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-zinc-600 border border-zinc-200 hover:bg-zinc-50">
              Tancar
            </button>
            <Button onClick={() => window.print()} className="flex-1 flex items-center justify-center gap-2">
              <Printer size={16} /> Imprimir tiquet
            </Button>
          </div>
        </div>
      </div>

      <ReceiptPrintArea sale={sale} shopConfig={shopConfig} />
    </>
  );
}

