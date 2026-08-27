import { getTranslations } from 'next-intl/server';
import { Link } from '../../../../i18n/navigation';
import { notFound } from 'next/navigation';
import { api } from '../../../lib/api';
import StorefrontNav from '../../../../components/store/StorefrontNav';
import StorefrontFooter from '../../../../components/store/StorefrontFooter';

export async function generateMetadata({ params }) {
  const { slug, locale } = await params;
  try {
    const [post, config] = await Promise.all([api(`/posts/${slug}`), api('/config/public')]);
    const plain = post.content.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 160);
    return {
      title: `${post.title} — ${config.nombre}`,
      description: plain,
    };
  } catch {
    const t = await getTranslations({ locale, namespace: 'blog' });
    return { title: t('postNotFound') };
  }
}

function formatDate(iso, locale) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString(locale, {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  });
}

export default async function PostPage({ params }) {
  const { slug, locale } = await params;
  const t = await getTranslations('blog');
  let post;
  try {
    post = await api(`/posts/${slug}`);
  } catch {
    notFound();
  }

  return (
    <>
      <StorefrontNav />
      <main className="flex-1">
        {/* Header */}
        <section className="bg-zinc-50 text-zinc-900 py-14 md:py-20">
          <div className="container max-w-2xl">
            <Link
              href="/blog"
              className="inline-block text-xs text-zinc-500 hover:text-zinc-900 transition-colors mb-6"
            >
              {t('backToBlog')}
            </Link>
            <time className="block text-zinc-500 text-xs font-semibold tracking-[0.15em] uppercase mb-4">
              {formatDate(post.published_at, locale)}
            </time>
            <h1 className="font-serif italic text-3xl md:text-4xl lg:text-5xl leading-tight">
              {post.title}
            </h1>
          </div>
        </section>

        {/* Article body */}
        <article className="container max-w-2xl py-12 md:py-16">
          <div
            className="blog-content"
            dangerouslySetInnerHTML={{ __html: post.content }}
          />

          {/* Back link */}
          <div className="border-t border-zinc-100 mt-12 pt-8">
            <Link
              href="/blog"
              className="inline-flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-900 transition-colors"
            >
              {t('backToBlog')}
            </Link>
          </div>
        </article>
      </main>
      <StorefrontFooter />
    </>
  );
}
