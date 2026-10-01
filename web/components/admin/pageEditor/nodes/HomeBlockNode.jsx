'use client';

// Puente craft-aware hacia el sistema de bloques viejo (`HomeBlock`) — ver
// components/store/pageTree/nodes/HomeBlockNode.jsx para el porqué (reusar
// los componentes React reales, cero reimplementación). El canvas del
// editor NUNCA carga datos en vivo (regla de oro §2, mismo criterio que
// ProductGrid/CatalogBrowse) — solo un placeholder con el nombre del bloc.
//
// Formularios de `block_props` escritos a mano contra
// api/app/blocks/registry.py (única fuente de verdad de qué props acepta
// cada `block_type`) — solo los 6 tipos que usa hoy algún tenant real
// (escaparate): hero, carousel, curator_selection, genre_grid,
// spotify_recommendations, about_strip. Los otros 8 del registro
// (text/testimonials/gallery/faq/banner/brand_strip/feature_grid/video)
// no tienen formulario todavía — añadir uno es mecánico si hace falta.
import { useNode } from '@craftjs/core';

export const BLOCK_LABELS = {
  hero: 'Hero',
  carousel: 'Carrusel',
  curator_selection: 'Selecció del curador',
  genre_grid: 'Graella de gèneres',
  spotify_recommendations: 'Recomanacions Spotify',
  about_strip: 'Franja "sobre nosaltres"',
};

const HERO_LAYOUTS = [
  'image_right', 'image_left', 'dual_featured', 'mosaic',
  'background_center', 'background_left', 'background_video',
  'solid_color', 'no_image', 'logo_tagline', 'illustration_band',
];
const ILLUSTRATION_SIZES = ['small', 'medium', 'large', 'full_bleed'];

export default function HomeBlockNode({ block_type }) {
  const { connectors: { connect, drag }, id, selected } = useNode((node) => ({ selected: node.events.selected }));
  return (
    <div
      ref={(ref) => connect(drag(ref))}
      data-node-id={id}
      style={{
        outline: selected ? '2px solid #6366f1' : '1px dashed #ccc',
        outlineOffset: -1,
        padding: 20,
        background: '#fafafa',
        fontSize: 12,
        color: '#666',
        textAlign: 'center',
      }}
    >
      Bloc: <strong>{BLOCK_LABELS[block_type] || block_type}</strong>
      <br />(vista prèvia no disponible a l&apos;editor — es veurà real al lloc públic)
    </div>
  );
}

// Sin `style`, a diferencia de los demás nodos: los componentes de
// BLOCK_COMPONENTS (HomeHero, CarouselBlock...) no aceptan un prop `style`
// de paso — tienen su propio maquetado fijo (ver
// components/store/pageTree/nodes/HomeBlockNode.jsx, el puente SSR). Un
// panel de estilo aquí no tendría ningún efecto real, así que no se
// muestra — mejor no ofrecer un control que en publicar no hace nada.
HomeBlockNode.craft = {
  displayName: 'HomeBlockNode',
  props: { block_type: 'hero', block_props: {} },
  related: { settings: HomeBlockSettings },
};

function Field({ label, value, onChange, placeholder, type = 'text' }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <label style={{ fontSize: 11, color: '#666', display: 'block', marginBottom: 2 }}>{label}</label>
      <input
        type={type}
        value={value || ''}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        style={{ width: '100%', fontSize: 12, padding: '4px 6px', border: '1px solid #ccc', borderRadius: 6 }}
      />
    </div>
  );
}

function SelectField({ label, value, options, onChange }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <label style={{ fontSize: 11, color: '#666', display: 'block', marginBottom: 2 }}>{label}</label>
      <select
        value={value || options[0]}
        onChange={(e) => onChange(e.target.value)}
        style={{ width: '100%', fontSize: 12, padding: '4px 6px', border: '1px solid #ccc', borderRadius: 6 }}
      >
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
}

function HomeBlockSettings() {
  const { block_type, block_props, actions: { setProp } } = useNode((node) => ({
    block_type: node.data.props.block_type,
    block_props: node.data.props.block_props || {},
  }));

  function setField(key, value) {
    setProp((props) => {
      props.block_props = { ...(props.block_props || {}) };
      if (value === '') delete props.block_props[key];
      else props.block_props[key] = value;
    });
  }

  return (
    <div>
      <p style={{ fontSize: 12, fontWeight: 600, color: '#333', marginBottom: 8 }}>{BLOCK_LABELS[block_type] || block_type}</p>

      {block_type === 'carousel' && (
        <>
          <Field label="Etiqueta del catàleg" value={block_props.etiqueta_slug} placeholder="novetat" onChange={(v) => setField('etiqueta_slug', v)} />
          <Field label="Títol" value={block_props.heading} onChange={(v) => setField('heading', v)} />
          <Field label="Subtítol" value={block_props.subtitle} onChange={(v) => setField('subtitle', v)} />
          <Field label="Text del botó" value={block_props.cta_label} onChange={(v) => setField('cta_label', v)} />
        </>
      )}

      {block_type === 'curator_selection' && (
        <Field label="Etiqueta del catàleg" value={block_props.etiqueta_slug} placeholder="recomanat" onChange={(v) => setField('etiqueta_slug', v)} />
      )}

      {block_type === 'hero' && (
        <>
          <SelectField label="Disposició" value={block_props.layout} options={HERO_LAYOUTS} onChange={(v) => setField('layout', v)} />
          <Field label="Text petit (eyebrow)" value={block_props.eyebrow} onChange={(v) => setField('eyebrow', v)} />
          <Field label="Títol" value={block_props.title} onChange={(v) => setField('title', v)} />
          <Field label="Subtítol" value={block_props.subtitle} onChange={(v) => setField('subtitle', v)} />
          <Field label="Text del botó" value={block_props.cta_label} onChange={(v) => setField('cta_label', v)} />
          <Field label="Enllaç del botó" value={block_props.cta_href} placeholder="/cataleg" onChange={(v) => setField('cta_href', v)} />
          <Field label="Text targeta destacada" value={block_props.featured_label} onChange={(v) => setField('featured_label', v)} />
          <Field label="Color de fons" type="color" value={block_props.background_color} onChange={(v) => setField('background_color', v)} />
          <Field label="Imatge de fons (URL)" value={block_props.background_image_url} onChange={(v) => setField('background_image_url', v)} />
          {block_props.layout === 'background_video' && (
            <Field label="Vídeo de fons (URL)" value={block_props.background_video_url} onChange={(v) => setField('background_video_url', v)} />
          )}
          {block_props.layout === 'illustration_band' && (
            <SelectField label="Mida de la il·lustració" value={block_props.illustration_size} options={ILLUSTRATION_SIZES} onChange={(v) => setField('illustration_size', v)} />
          )}
        </>
      )}

      {['genre_grid', 'spotify_recommendations', 'about_strip'].includes(block_type) && (
        <p style={{ fontSize: 11, color: '#999' }}>Aquest bloc no té propietats configurables — sempre mostra les dades reals.</p>
      )}

      <StyleSettings />
    </div>
  );
}
