import Stack from './nodes/Stack';
import TextNode from './nodes/TextNode';
import ImageNode from './nodes/ImageNode';
import ProductGrid from './nodes/ProductGrid';
import CatalogBrowse from './nodes/CatalogBrowse';
import Button from './nodes/Button';
import Spacer from './nodes/Spacer';
import HomeBlockNode from './nodes/HomeBlockNode';

// Pasado a `<Editor resolver={...}>` — las claves son los mismos `type`
// strings que nodeTypes.js y el árbol portable, ver craftTransform.js.
export const NODE_RESOLVER = { Stack, TextNode, ImageNode, ProductGrid, CatalogBrowse, Button, Spacer, HomeBlockNode };
