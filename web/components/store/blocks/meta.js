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
    description: 'Discos filtrats per una etiqueta (p. ex. "Recomanats").',
    editable: true,
  },
  genre_grid: {
    label: 'Explora per gènere',
    description: 'Graella amb els gèneres reals del teu catàleg (automàtic, sense configuració).',
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
  gallery: {
    label: 'Galeria',
    description: 'Graella d’imatges lliures, amb peu de foto i enllaç opcionals.',
    editable: true,
  },
  faq: {
    label: 'Preguntes freqüents',
    description: 'Llista de preguntes i respostes en acordió.',
    editable: true,
  },
  banner: {
    label: 'Franja d’avís',
    description: 'Un avís curt (horari especial, enviaments...) amb un enllaç opcional.',
    editable: true,
  },
  brand_strip: {
    label: 'Franja de marques',
    description: 'Fila de logos (segells, col·laboradors...) amb enllaç opcional.',
    editable: true,
  },
  feature_grid: {
    label: 'Graella de destacats',
    description: 'Icona + text + enllaç lliures (categories, avantatges, serveis...).',
    editable: true,
  },
  video: {
    label: 'Vídeo',
    description: 'Un vídeo destacat de YouTube o Vimeo.',
    editable: true,
  },
};

export const BLOCK_TYPES = Object.keys(BLOCK_META);
