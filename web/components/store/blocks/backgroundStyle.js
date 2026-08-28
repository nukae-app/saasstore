// Estil de fons compartit per hero/text/testimonials — ver
// api/app/blocks/registry.py::BackgroundProps i BackgroundFieldset.jsx. La
// imatge, si n'hi ha, mana sobre el color (mateix ordre que PreviewBridge.jsx
// aplica en directe). El degradat blanc translúcid manté el text fosc
// llegible sense haver de triar un color de text a part.
export function backgroundStyle(background_color, background_image_url) {
  if (background_image_url) {
    return {
      backgroundImage: `linear-gradient(rgba(255,255,255,0.55), rgba(255,255,255,0.55)), url(${background_image_url})`,
      backgroundSize: 'cover',
      backgroundPosition: 'center',
    };
  }
  if (background_color) return { backgroundColor: background_color };
  return undefined;
}
