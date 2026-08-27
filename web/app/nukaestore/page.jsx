import Link from 'next/link';
import {
  Disc3,
  Flower2,
  ShoppingBag,
  ShieldCheck,
  BookOpen,
  LayoutDashboard,
  Globe,
  ArrowRight,
  Check,
  Store,
} from 'lucide-react';

export const metadata = {
  title: 'NukaeStore — la plataforma para tiendas de barrio con carácter',
  description:
    'NukaeStore es el software que convierte una tienda física con identidad propia en tienda online y comunidad, sin renunciar a lo que la hace única. Empieza con tiendas de discos, crece a cualquier vertical.',
};

const PILLARS = [
  {
    icon: Store,
    title: 'Tienda online + comunidad',
    body: 'No es un escaparate genérico. Catálogo, blog y agenda conviven en el mismo sitio, porque así es como funciona una tienda de barrio de verdad.',
  },
  {
    icon: ShieldCheck,
    title: 'Stock que no miente',
    body: 'Cada ejemplar de segunda mano es único y se reserva de forma atómica: nunca se vende dos veces la misma pieza, ni con dos pestañas abiertas a la vez.',
  },
  {
    icon: Globe,
    title: 'Pensado para vender de verdad',
    body: 'Checkout sin fricción, con o sin cuenta. Login con Google o enlace mágico por email. Nada que un cliente tenga que aprender a usar.',
  },
];

const FEATURES = [
  {
    icon: LayoutDashboard,
    title: 'Un panel, todo el negocio',
    body: 'Alta de producto, pedidos, TPV de mostrador, compras a proveedor y caja diaria. La parte online y la física del negocio comparten el mismo stock.',
  },
  {
    icon: BookOpen,
    title: 'Blog y agenda integrados',
    body: 'El contenido que ya hacías —artículos, eventos, novedades— vive junto al catálogo, no en una herramienta aparte que nadie actualiza.',
  },
  {
    icon: ShieldCheck,
    title: 'Reservas sin sobreventa',
    body: 'Carrito y checkout reservan stock con control de concurrencia real, tanto para piezas únicas como para referencias con varias unidades.',
  },
  {
    icon: Globe,
    title: 'Multi-idioma de fábrica',
    body: 'Catalán y castellano listos desde el primer día, con la estructura preparada para añadir más idiomas sin tocar el catálogo.',
  },
  {
    icon: ShoppingBag,
    title: 'Snapshots en cada pedido',
    body: 'El precio y la dirección de un pedido quedan fijados en el momento de la compra. El histórico nunca cambia aunque cambie el catálogo.',
  },
  {
    icon: LayoutDashboard,
    title: 'Multi-tenant desde el core',
    body: 'Cada tienda vive aislada de las demás en la misma plataforma, con su propio dominio, catálogo y panel — sin montar infraestructura propia.',
  },
];

const VERTICALS = [
  {
    icon: Disc3,
    name: 'Tiendas de discos',
    status: 'Disponible',
    body: 'Segunda mano copia a copia (con su propio grading) y novedades como stock agregado. Integración con Discogs para dar de alta discos en segundos.',
  },
  {
    icon: Flower2,
    name: 'Floristerías',
    status: 'Disponible',
    body: 'Catálogo adaptado a producto perecedero: color, tipo de flor, durabilidad. Mismo motor de pedidos, pagos y checkout que el resto de verticales.',
  },
  {
    icon: null,
    name: 'Tu sector',
    status: 'Próximamente',
    body: 'La arquitectura separa lo común (pedidos, pagos, blog, TPV) de lo específico de cada sector, para poder añadir verticales nuevos sin rehacer la plataforma.',
  },
];

const STEPS = [
  {
    n: '01',
    title: 'Da de alta tu catálogo',
    body: 'A mano o autocompletando desde fuentes externas según el vertical (por ejemplo Discogs para discos). Tú decides precio y condición de cada pieza.',
  },
  {
    n: '02',
    title: 'Abre tienda online',
    body: 'Catálogo con filtros, ficha de producto, carrito y checkout ya montados. Con tu dominio, en catalán y castellano.',
  },
  {
    n: '03',
    title: 'Gestiona todo desde un sitio',
    body: 'Lo que vendes en la tienda física, en mostrador o por otros canales descuenta el mismo stock que ves online. Sin cuadrar hojas de cálculo a mano.',
  },
];

export default function NukaeStoreLanding() {
  return (
    <div className="min-h-screen bg-[#faf7f2] text-[#161310] font-sans">
      {/* Nav */}
      <header className="sticky top-0 z-40 border-b border-black/10 bg-[#faf7f2]/90 backdrop-blur">
        <div className="max-w-[1200px] mx-auto px-5 md:px-8 h-16 flex items-center justify-between">
          <span className="font-serif italic text-xl tracking-tight">NukaeStore</span>
          <nav className="hidden md:flex items-center gap-8 text-sm text-[#161310]/70">
            <a href="#producto" className="hover:text-[#161310] transition-colors">Producto</a>
            <a href="#verticales" className="hover:text-[#161310] transition-colors">Verticales</a>
            <a href="#como-funciona" className="hover:text-[#161310] transition-colors">Cómo funciona</a>
          </nav>
          <a
            href="#contacto"
            className="text-xs font-mono uppercase tracking-widest border border-[#161310] rounded-full px-4 py-2 hover:bg-[#161310] hover:text-[#faf7f2] transition-colors"
          >
            Solicitar demo
          </a>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="max-w-[1200px] mx-auto px-5 md:px-8 pt-20 pb-24 md:pt-28 md:pb-32">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-[#a8622f] mb-6">
            Software para comercios con identidad
          </p>
          <h1 className="font-serif italic text-4xl md:text-6xl leading-[1.1] max-w-3xl text-balance">
            Tu tienda de barrio, con tienda online de verdad.
          </h1>
          <p className="mt-6 text-lg md:text-xl text-[#161310]/70 max-w-2xl leading-relaxed">
            NukaeStore convierte un negocio físico —con su stock, su comunidad y su forma de
            vender particular— en una tienda online completa. Nació dentro de una tienda de
            discos real en Poblenou (Barcelona) y está construido para crecer a cualquier
            sector con el mismo rigor.
          </p>
          <div className="mt-10 flex flex-wrap items-center gap-4">
            <a
              href="#contacto"
              className="inline-flex items-center gap-2 bg-[#161310] text-[#faf7f2] rounded-full px-6 py-3 text-sm font-medium hover:bg-[#2a231c] transition-colors"
            >
              Solicitar demo
              <ArrowRight size={16} />
            </a>
            <a
              href="#como-funciona"
              className="inline-flex items-center gap-2 text-sm font-medium text-[#161310]/80 hover:text-[#161310] transition-colors"
            >
              Ver cómo funciona
            </a>
          </div>
        </section>

        {/* Pillars */}
        <section id="producto" className="border-y border-black/10 bg-white">
          <div className="max-w-[1200px] mx-auto px-5 md:px-8 py-20 grid gap-12 md:grid-cols-3">
            {PILLARS.map((p) => (
              <div key={p.title}>
                <p.icon size={22} strokeWidth={1.5} className="text-[#a8622f]" />
                <h3 className="font-serif italic text-xl mt-4 mb-2">{p.title}</h3>
                <p className="text-sm text-[#161310]/65 leading-relaxed">{p.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Features */}
        <section className="max-w-[1200px] mx-auto px-5 md:px-8 py-24">
          <div className="max-w-2xl mb-16">
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-[#a8622f] mb-4">
              Todo lo que necesita un negocio real
            </p>
            <h2 className="font-serif italic text-3xl md:text-4xl">
              No solo un escaparate. La gestión entera.
            </h2>
          </div>
          <div className="grid gap-x-10 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div key={f.title}>
                <f.icon size={20} strokeWidth={1.5} className="text-[#161310]/50 mb-3" />
                <h3 className="text-base font-semibold mb-1.5">{f.title}</h3>
                <p className="text-sm text-[#161310]/65 leading-relaxed">{f.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Verticals */}
        <section id="verticales" className="bg-[#161310] text-[#faf7f2]">
          <div className="max-w-[1200px] mx-auto px-5 md:px-8 py-24">
            <div className="max-w-2xl mb-16">
              <p className="font-mono text-xs uppercase tracking-[0.2em] text-[#d98a52] mb-4">
                Arquitectura por sectores
              </p>
              <h2 className="font-serif italic text-3xl md:text-4xl">
                Lo común, resuelto una vez. Lo específico, a medida de tu sector.
              </h2>
              <p className="mt-4 text-[#faf7f2]/60 leading-relaxed">
                Pedidos, pagos, checkout, blog y TPV son el mismo motor para cualquier
                tienda. Lo que cambia según el sector es el catálogo: cómo se describe,
                cómo se agrupa y cómo se reserva cada producto.
              </p>
            </div>
            <div className="grid gap-6 md:grid-cols-3">
              {VERTICALS.map((v) => (
                <div
                  key={v.name}
                  className="border border-[#faf7f2]/15 rounded-2xl p-6 flex flex-col"
                >
                  <div className="flex items-center justify-between mb-6">
                    {v.icon ? (
                      <v.icon size={24} strokeWidth={1.5} className="text-[#d98a52]" />
                    ) : (
                      <span className="text-[#d98a52] text-xl leading-none">+</span>
                    )}
                    <span
                      className={`text-[10px] font-mono uppercase tracking-widest px-2 py-1 rounded-full ${
                        v.status === 'Disponible'
                          ? 'bg-[#d98a52]/15 text-[#d98a52]'
                          : 'bg-[#faf7f2]/10 text-[#faf7f2]/50'
                      }`}
                    >
                      {v.status}
                    </span>
                  </div>
                  <h3 className="font-serif italic text-xl mb-2">{v.name}</h3>
                  <p className="text-sm text-[#faf7f2]/60 leading-relaxed">{v.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* How it works */}
        <section id="como-funciona" className="max-w-[1200px] mx-auto px-5 md:px-8 py-24">
          <div className="max-w-2xl mb-16">
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-[#a8622f] mb-4">
              De catálogo a venta
            </p>
            <h2 className="font-serif italic text-3xl md:text-4xl">Cómo funciona</h2>
          </div>
          <div className="grid gap-12 md:grid-cols-3">
            {STEPS.map((s) => (
              <div key={s.n}>
                <span className="font-mono text-sm text-[#a8622f]">{s.n}</span>
                <h3 className="font-serif italic text-xl mt-3 mb-2">{s.title}</h3>
                <p className="text-sm text-[#161310]/65 leading-relaxed">{s.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Honest positioning strip */}
        <section className="border-y border-black/10 bg-white">
          <div className="max-w-[1200px] mx-auto px-5 md:px-8 py-16 flex flex-col md:flex-row gap-8 md:items-center md:justify-between">
            <p className="max-w-xl text-sm text-[#161310]/70 leading-relaxed">
              NukaeStore está en desarrollo activo. Su primera tienda en producción es una
              tienda de discos real de Poblenou, y ahí se pone a prueba cada decisión antes
              de ofrecerla a otros negocios.
            </p>
            <ul className="flex flex-col gap-2 text-sm shrink-0">
              {['Sin datos de tarjeta guardados nunca', 'Cada pedido histórico, inmutable', 'Guest checkout, sin cuenta obligatoria'].map(
                (item) => (
                  <li key={item} className="flex items-center gap-2 text-[#161310]/70">
                    <Check size={14} className="text-[#a8622f] shrink-0" />
                    {item}
                  </li>
                ),
              )}
            </ul>
          </div>
        </section>

        {/* CTA */}
        <section id="contacto" className="max-w-[1200px] mx-auto px-5 md:px-8 py-24 text-center">
          <h2 className="font-serif italic text-3xl md:text-5xl max-w-2xl mx-auto text-balance">
            ¿Tienes un negocio con carácter propio?
          </h2>
          <p className="mt-5 text-[#161310]/65 max-w-xl mx-auto leading-relaxed">
            Hablemos de cómo sería tu tienda online sin perder lo que te hace diferente.
          </p>
          <div className="mt-8">
            <a
              href="mailto:hola@nukaestore.com"
              className="inline-flex items-center gap-2 bg-[#161310] text-[#faf7f2] rounded-full px-7 py-3.5 text-sm font-medium hover:bg-[#2a231c] transition-colors"
            >
              Escríbenos
              <ArrowRight size={16} />
            </a>
          </div>
        </section>
      </main>

      <footer className="border-t border-black/10">
        <div className="max-w-[1200px] mx-auto px-5 md:px-8 py-10 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-[#161310]/50">
          <span className="font-serif italic text-base text-[#161310]/80">NukaeStore</span>
          <span>© {new Date().getFullYear()} NukaeStore. Todos los derechos reservados.</span>
          <Link href="/" className="hover:text-[#161310]/80 transition-colors">
            Ir a una tienda
          </Link>
        </div>
      </footer>
    </div>
  );
}
