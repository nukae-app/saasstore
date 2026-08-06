import { notFound } from 'next/navigation';
import { getTranslations } from 'next-intl/server';
import { Link } from '../../../i18n/navigation';
import { api } from '../../lib/api';
import StorefrontNav from '../../../components/store/StorefrontNav';
import StorefrontFooter from '../../../components/store/StorefrontFooter';
import { Music2, Headphones, Disc3, CalendarDays, MapPin, ExternalLink } from 'lucide-react';
import ArchiveSidebar from '../blog/ArchiveSidebar';
import ArchiveSelect from '../blog/ArchiveSelect';

// ---------------------------------------------------------------------------
// Metadata
// ---------------------------------------------------------------------------

export async function generateMetadata({ params }) {
  const { pagina: slug } = await params;
  try {
    const p = await api(`/pagines/${slug}`);
    return { title: `${p.nom} — Ultra-Local Records` };
  } catch {
    return { title: 'Ultra-Local Records' };
  }
}

// ---------------------------------------------------------------------------
// Helpers compartits
// ---------------------------------------------------------------------------

function formatDate(iso, locale) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString(locale, { day: 'numeric', month: 'long', year: 'numeric' });
}

function hasAudio(contenido) {
  return /mixcloud\.com|bandcamp\.com|soundcloud\.com|spotify\.com|youtube(-nocookie)?\.com/i.test(contenido || '');
}

// ---------------------------------------------------------------------------
// Post card (llista-posts)
// ---------------------------------------------------------------------------

function PostCard({ post, locale, t }) {
  const audio = hasAudio(post.contenido);
  return (
    <Link href={`/blog/${post.slug}`} className="group block bg-white rounded-2xl overflow-hidden shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] hover:border-zinc-200 hover:shadow-md transition-all duration-200">
      <div className="aspect-[4/3] bg-zinc-100 overflow-hidden relative">
        {post.thumbnail_url ? (
          <img src={post.thumbnail_url} alt="" className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Disc3 size={40} className="text-zinc-200" />
          </div>
        )}
        {audio && (
          <div className="absolute top-2.5 left-2.5 flex items-center gap-1 bg-zinc-900/80 backdrop-blur-sm text-white text-[10px] font-semibold px-2 py-1 rounded-full">
            <Headphones size={9} /> {t('audio')}
          </div>
        )}
      </div>
      <div className="p-4">
        <time className="text-[11px] text-zinc-500 font-semibold tracking-wide uppercase">
          {formatDate(post.publicado_at, locale)}
        </time>
        <h2 className="font-serif italic text-lg leading-snug mt-1.5 text-zinc-900 group-hover:text-zinc-500 transition-colors line-clamp-2">
          {post.titulo}
        </h2>
        {post.excerpt && (
          <p className="text-zinc-500 text-xs leading-relaxed mt-2 line-clamp-3">{post.excerpt}</p>
        )}
      </div>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Pàgina tipus llista-posts
// ---------------------------------------------------------------------------

async function LlistaPostsPage({ pagina, searchParams, locale }) {
  const t = await getTranslations({ locale, namespace: 'pagina' });
  const sp = await searchParams;
  const page  = Number(sp?.page  ?? 1);
  const year  = sp?.year  ? Number(sp.year)  : null;
  const month = sp?.month ? Number(sp.month) : null;

  const params = new URLSearchParams({ page, page_size: 6, pagina: pagina.slug });
  if (year)  params.set('year', year);
  if (month) params.set('month', month);

  let posts = [], archive = [];
  try {
    [posts, archive] = await Promise.all([
      api(`/posts?${params}`),
      api(`/posts/archive?pagina=${pagina.slug}`),
    ]);
  } catch {}

  const heading = year && month ? `${t(`monthsLong.${month}`)} ${year}` : year ? `${year}` : pagina.nom;
  const slug = pagina.slug;

  return (
    <main className="flex-1">
      <section className="bg-zinc-50 text-zinc-900 py-14 md:py-18">
        <div className="container">
          <p className="text-zinc-500 text-xs font-semibold tracking-[0.2em] uppercase mb-3">
            Ultra-Local Records · Poblenou
          </p>
          <h1 className="font-serif italic text-4xl md:text-5xl leading-tight">{heading}</h1>
          {!year && (
            <p className="text-zinc-500 mt-3 text-base max-w-lg">
              {t('blogSubtitle')}
            </p>
          )}
        </div>
      </section>

      <div className="container py-10 md:py-14">
        <div className="flex gap-8 items-start">
          <div className="hidden lg:block">
            <ArchiveSidebar archive={archive} currentYear={year} currentMonth={month} basePath={`/${slug}`} />
          </div>
          <div className="flex-1 min-w-0">
            {archive.length > 0 && (
              <div className="lg:hidden mb-6">
                <ArchiveSelect archive={archive} defaultValue={year && month ? `${year}-${month}` : ''} basePath={`/${slug}`} />
              </div>
            )}
            {posts.length === 0 ? (
              <div className="text-center py-24">
                <Music2 size={40} className="mx-auto text-zinc-200 mb-4" />
                <p className="text-zinc-400">{t('noPostsForPeriod')}</p>
                <Link href={`/${slug}`} className="text-zinc-900 text-sm mt-2 inline-block hover:text-zinc-600">
                  {t('viewAllPosts')}
                </Link>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5">
                  {posts.map(post => <PostCard key={post.slug} post={post} locale={locale} t={t} />)}
                </div>
                <div className="flex items-center justify-between mt-10 pt-8 border-t border-zinc-100">
                  {page > 1 ? (
                    <Link href={`/${slug}?${new URLSearchParams({ ...(year ? {year} : {}), ...(month ? {month} : {}), page: page - 1 })}`}
                      className="text-sm text-zinc-600 hover:text-zinc-900 transition-colors">{t('previous')}</Link>
                  ) : <span />}
                  <span className="text-xs text-zinc-400">{t('pageN', { page })}</span>
                  {posts.length === 6 ? (
                    <Link href={`/${slug}?${new URLSearchParams({ ...(year ? {year} : {}), ...(month ? {month} : {}), page: page + 1 })}`}
                      className="text-sm text-zinc-600 hover:text-zinc-900 transition-colors">{t('next')}</Link>
                  ) : <span />}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Pàgina estàtica
// ---------------------------------------------------------------------------

async function EstaticaPage({ pagina, locale }) {
  const t = await getTranslations({ locale, namespace: 'pagina' });
  return (
    <main className="flex-1">
      <section className="bg-zinc-50 text-zinc-900 py-14 md:py-18">
        <div className="container max-w-3xl">
          <h1 className="font-serif italic text-4xl md:text-5xl leading-tight">{pagina.nom}</h1>
        </div>
      </section>
      <div className="container max-w-3xl py-12 md:py-16">
        {pagina.contingut ? (
          <div className="blog-content" dangerouslySetInnerHTML={{ __html: pagina.contingut }} />
        ) : (
          <p className="text-zinc-400 italic">{t('pageNoContentYet')}</p>
        )}
      </div>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Pàgina d'agenda
// ---------------------------------------------------------------------------

async function AgendaPage({ pagina, locale }) {
  const t = await getTranslations({ locale, namespace: 'pagina' });
  let events = [];
  try { events = await api('/events'); } catch {}

  function isThisWeek(iso) {
    const d = new Date(iso), now = new Date();
    const diff = (d - now) / 86400000;
    return diff >= 0 && diff <= 7;
  }

  return (
    <main className="flex-1">
      <section className="bg-zinc-50 text-zinc-900 py-14 md:py-18">
        <div className="container">
          <p className="text-zinc-500 text-xs font-semibold tracking-[0.2em] uppercase mb-3">
            Ultra-Local Records · Poblenou
          </p>
          <h1 className="font-serif italic text-4xl md:text-5xl leading-tight">{t('agenda')}</h1>
          <p className="text-zinc-500 mt-3 max-w-lg">{t('agendaSubtitle')}</p>
        </div>
      </section>
      <div className="container py-10 md:py-14 max-w-3xl">
        {events.length === 0 ? (
          <div className="text-center py-24">
            <CalendarDays size={40} className="mx-auto text-zinc-200 mb-4" />
            <p className="text-zinc-400">{t('noEventsScheduled')}</p>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {events.map(ev => {
              const d = new Date(ev.fecha);
              const avui = new Date().toDateString() === d.toDateString();
              const setmana = isThisWeek(ev.fecha);
              return (
                <div key={ev.id} className="flex gap-5 bg-white rounded-2xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] p-5 hover:shadow-sm transition-shadow">
                  <div className="shrink-0 w-14 text-center">
                    <p className="text-[10px] font-bold text-zinc-500 uppercase">{t(`monthsShort.${d.getMonth() + 1}`)}</p>
                    <p className="text-3xl font-bold text-zinc-900 leading-tight">{d.getDate()}</p>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap gap-1.5 mb-1">
                      {avui && <span className="text-[10px] bg-amber-100 text-amber-700 font-bold px-2 py-0.5 rounded-full">{t('today')}</span>}
                      {!avui && setmana && <span className="text-[10px] bg-zinc-100 text-zinc-600 font-semibold px-2 py-0.5 rounded-full">{t('thisWeek')}</span>}
                    </div>
                    <h2 className="font-serif italic text-lg text-zinc-900 leading-snug">{ev.titulo}</h2>
                    {ev.descripcion && <p className="text-zinc-500 text-sm mt-1">{ev.descripcion}</p>}
                    <div className="flex flex-wrap gap-4 mt-2 text-xs text-zinc-400">
                      <span className="flex items-center gap-1"><MapPin size={11} />{ev.lugar}</span>
                      {ev.link && (
                        <a href={ev.link} target="_blank" rel="noopener" className="flex items-center gap-1 text-zinc-900 hover:text-zinc-600">
                          <ExternalLink size={11} /> {t('moreInfo')}
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
        <div className="mt-16 bg-zinc-50 text-zinc-900 rounded-3xl p-8 text-center shadow-[0_2px_24px_-6px_rgba(15,23,42,0.08)]">
          <h2 className="font-serif italic text-2xl mb-2">{t('wantToHearNews')}</h2>
          <p className="text-zinc-500 text-sm mb-4">{t('notifyUpcomingEvents')}</p>
          <a href="mailto:info@ultralocalrecords.com" className="inline-block bg-primary hover:bg-zinc-800 text-white text-sm font-semibold px-6 py-2.5 rounded-full transition-colors">
            {t('subscribe')}
          </a>
        </div>
      </div>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

export default async function PaginaDinamica({ params, searchParams }) {
  const { pagina: slug, locale } = await params;

  // Pàgines especials que no estan al CMS
  if (slug === 'cataleg' || slug === 'carret' || slug === 'login' || slug === 'compte') {
    notFound();
  }

  let pagina;
  try {
    pagina = await api(`/pagines/${slug}`);
  } catch {
    notFound();
  }

  return (
    <>
      <StorefrontNav />
      {pagina.tipus === 'llista-posts' && (
        <LlistaPostsPage pagina={pagina} searchParams={searchParams} locale={locale} />
      )}
      {pagina.tipus === 'estatica' && <EstaticaPage pagina={pagina} locale={locale} />}
      {pagina.tipus === 'agenda' && <AgendaPage pagina={pagina} locale={locale} />}
      <StorefrontFooter />
    </>
  );
}
