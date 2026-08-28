import { Link } from '../../../i18n/navigation';
import { Music2, Disc, Truck, Gift, Tag, Percent, MapPin, Phone, Mail, Heart, Star, Sparkles } from 'lucide-react';

// Mapa icona->component — mateixes claus que
// api/app/blocks/registry.py::FEATURE_GRID_ICONS.
export const FEATURE_GRID_ICON_MAP = {
  music: Music2,
  disc: Disc,
  truck: Truck,
  gift: Gift,
  tag: Tag,
  percent: Percent,
  'map-pin': MapPin,
  phone: Phone,
  mail: Mail,
  heart: Heart,
  star: Star,
  sparkles: Sparkles,
};

// Bloc "feature_grid" (ver api/app/blocks/registry.py::FeatureGridProps) —
// graella d'icona+text+enllaç lliure (categories, avantatges, serveis...).
// Mateix disseny visual que GenreGrid.jsx, però amb ítems que tria l'admin
// en lloc dels gèneres reals del catàleg.
export default function FeatureGridBlock({ id, heading, items = [] }) {
  if (!items || items.length === 0) return null;

  return (
    <section
      data-block-id={id}
      style={{
        paddingTop: 'var(--spacing-density)',
        paddingBottom: 'var(--spacing-density)',
        borderTop: 'var(--section-divider, none)',
      }}
      className="px-5 md:px-16 bg-white"
    >
      <div className="max-w-[var(--content-width,1280px)] mx-auto">
        {heading && (
          <h2
            style={{ textTransform: 'var(--eyebrow-style, uppercase)' }}
            className="font-mono text-xs text-zinc-500 text-center tracking-[0.4em] mb-16 md:mb-20"
          >
            {heading}
          </h2>
        )}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-6 md:gap-8">
          {items.map((item, i) => {
            const Icon = FEATURE_GRID_ICON_MAP[item.icon] || Music2;
            const Wrapper = item.href ? Link : 'div';
            const wrapperProps = item.href ? { href: item.href } : {};
            return (
              <Wrapper
                key={i}
                {...wrapperProps}
                style={{
                  borderRadius: 'var(--radius-card, 24px)',
                  border: 'var(--border-card, 1px solid #e4e4e7)',
                }}
                className="group block bg-white py-12 text-center hover:bg-zinc-50 transition-colors"
              >
                <Icon size={32} className="mx-auto mb-6 text-zinc-500 group-hover:text-zinc-900 transition-colors" />
                <p
                  style={{ textTransform: 'var(--eyebrow-style, uppercase)' }}
                  className="text-xs tracking-widest text-zinc-900 font-medium"
                >
                  {item.label}
                </p>
              </Wrapper>
            );
          })}
        </div>
      </div>
    </section>
  );
}
