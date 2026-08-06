export default function robots() {
  return {
    rules: [
      { userAgent: '*', allow: '/', disallow: ['/login', '/checkout', '/compte', '/carret', '/admin'] },
    ],
    sitemap: 'https://labotigaaquesta.com/sitemap.xml',
  };
}
