// Metadades del constructor d'admin (etiqueta, descripció curta, si té props
// editables) — mirall parcial de api/app/blocks/registry.py::BLOCK_REGISTRY,
// però només per a la UI d'administració (web/app/admin/pagina-inici); el
// mapa que fa servir el render públic del home és blocks/registry.js.
export const BLOCK_META = {
  hero: {
    label: 'Capçalera',
    description: 'La franja principal del home: títol, subtítol i botons.',
    editable: true,
  },
  carousel: {
    label: 'Carrusel',
    description: 'Una filera de discos filtrats per una etiqueta (p. ex. "Novetats").',
    editable: true,
  },
  curator_selection: {
    label: 'Selecció del curador',
    description: 'Els discos marcats com a "recomanats".',
    editable: false,
  },
  genre_grid: {
    label: 'Explora per gènere',
    description: 'Graella d’accessos ràpids per gènere musical.',
    editable: false,
  },
  spotify_recommendations: {
    label: 'Recomanacions Spotify',
    description: 'Bloc de recomanacions basat en Spotify.',
    editable: false,
  },
  about_strip: {
    label: 'Sobre la botiga',
    description: 'Nom, adreça i enllaç a Discogs de la botiga.',
    editable: false,
  },
  text: {
    label: 'Text',
    description: 'Franja de contingut lliure: títol, text i un botó opcional.',
    editable: true,
  },
  testimonials: {
    label: 'Testimonis',
    description: 'Cites de clients amb el seu nom.',
    editable: true,
  },
};

export const BLOCK_TYPES = Object.keys(BLOCK_META);
