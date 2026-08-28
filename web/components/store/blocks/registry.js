// Registre de blocs del home constructible — mirall exacte de
// api/app/blocks/registry.py::BLOCK_REGISTRY (mateixes claus). Afegir un
// bloc nou és afegir una entrada aquí + el seu component, sense tocar
// [locale]/page.jsx.
import HomeHero from '../HomeHero';
import CarouselBlock from './CarouselBlock';
import CuratorSelection from '../CuratorSelection';
import GenreGrid from '../GenreGrid';
import SpotifyRecommendations from '../SpotifyRecommendations';
import AboutStripBlock from './AboutStripBlock';
import TextBlock from './TextBlock';
import TestimonialsBlock from './TestimonialsBlock';

export const BLOCK_COMPONENTS = {
  hero: HomeHero,
  carousel: CarouselBlock,
  curator_selection: CuratorSelection,
  genre_grid: GenreGrid,
  spotify_recommendations: SpotifyRecommendations,
  about_strip: AboutStripBlock,
  text: TextBlock,
  testimonials: TestimonialsBlock,
};
