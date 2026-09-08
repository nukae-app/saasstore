'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import MIcon from '../../../components/ui/m-icon';
import { authFetch } from '../../lib/auth';

function formatDate(iso) {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString('ca-ES', { day: 'numeric', month: 'short', year: 'numeric' });
}

export default function AdminBlogPage() {
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [deleting, setDeleting] = useState(null);

  async function load() {
    const params = q ? `?q=${encodeURIComponent(q)}` : '';
    const res = await authFetch(`/admin/posts${params}`);
    if (res.ok) setPosts(await res.json());
    setLoading(false);
  }

  useEffect(() => { load(); }, [q]);

  async function handleDelete(slug, title) {
    if (!confirm(`Eliminar "${title}"? Aquesta acció no es pot desfer.`)) return;
    setDeleting(slug);
    try {
      await authFetch(`/admin/posts/${slug}`, { method: 'DELETE' });
      setPosts(p => p.filter(x => x.slug !== slug));
    } finally {
      setDeleting(null);
    }
  }

  const published = posts.filter(p => p.published_at);
  const drafts = posts.filter(p => !p.published_at);

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Blog</h1>
          <p className="text-sm text-secondary mt-0.5">{posts.length} posts · {drafts.length} esborranys</p>
        </div>
        <Link
          href="/admin/blog/nou"
          className="flex items-center gap-1.5 bg-primary hover:opacity-90 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          <MIcon name="add" size={15} /> Nou post
        </Link>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <MIcon name="search" size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-secondary" />
        <input
          type="text"
          placeholder="Cercar per títol…"
          value={q}
          onChange={e => setQ(e.target.value)}
          className="w-full pl-8 pr-3 py-2 text-sm border border-outline-variant rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
        />
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <MIcon name="progress_activity" size={20} className="animate-spin text-secondary" />
        </div>
      ) : posts.length === 0 ? (
        <div className="text-center py-20 text-secondary">
          <p className="mb-4">No hi ha posts encara.</p>
          <Link href="/admin/blog/nou" className="text-on-surface hover:text-on-surface-variant font-medium text-sm">
            Crea el primer post →
          </Link>
        </div>
      ) : (
        <div className="bg-card shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] rounded-xl overflow-hidden">
          {/* Esborranys primer si n'hi ha */}
          {drafts.length > 0 && (
            <>
              <div className="px-4 py-2 bg-amber-50 border-b border-amber-100 text-xs font-semibold text-amber-700 uppercase tracking-wider">
                Esborranys ({drafts.length})
              </div>
              {drafts.map(post => (
                <PostRow key={post.slug} post={post} onDelete={handleDelete} deleting={deleting} />
              ))}
            </>
          )}
          {published.length > 0 && (
            <>
              {drafts.length > 0 && (
                <div className="px-4 py-2 bg-surface-container-high border-b border-outline-variant text-xs font-semibold text-secondary uppercase tracking-wider">
                  Publicats ({published.length})
                </div>
              )}
              {published.map(post => (
                <PostRow key={post.slug} post={post} onDelete={handleDelete} deleting={deleting} />
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function PostRow({ post, onDelete, deleting }) {
  const isPublished = !!post.published_at;
  return (
    <div className="flex items-center gap-4 px-4 py-3 border-b border-outline-variant/40 last:border-0 hover:bg-surface-container-high/50 transition-colors">
      <div className="shrink-0">
        {isPublished
          ? <MIcon name="visibility" size={14} className="text-emerald-500" />
          : <MIcon name="visibility_off" size={14} className="text-secondary" />
        }
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm text-on-surface truncate">{post.title}</p>
        <div className="flex items-center gap-3 mt-0.5">
          <span className="text-xs text-secondary font-mono">{post.slug}</span>
          {isPublished && (
            <span className="text-xs text-secondary">{formatDate(post.published_at)}</span>
          )}
          <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${post.language === 'ca' ? 'bg-surface-container-high text-secondary' : 'bg-blue-50 text-blue-600'}`}>
            {post.language}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-1.5 shrink-0">
        {isPublished && (
          <a
            href={`/blog/${post.slug}`}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1.5 text-secondary hover:text-on-surface-variant rounded-lg hover:bg-surface-container-high transition-colors"
            title="Veure al web"
          >
            <MIcon name="visibility" size={13} />
          </a>
        )}
        <Link
          href={`/admin/blog/${post.slug}`}
          className="p-1.5 text-secondary hover:text-on-surface-variant rounded-lg hover:bg-surface-container-high transition-colors"
          title="Editar"
        >
          <MIcon name="edit" size={13} />
        </Link>
        <button
          onClick={() => onDelete(post.slug, post.title)}
          disabled={deleting === post.slug}
          className="p-1.5 text-secondary hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors disabled:opacity-50"
          title="Eliminar"
        >
          {deleting === post.slug
            ? <MIcon name="progress_activity" size={13} className="animate-spin" />
            : <MIcon name="delete" size={13} />
          }
        </button>
      </div>
    </div>
  );
}
