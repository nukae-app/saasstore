'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { authFetch } from '../../../lib/auth';
import PostEditor from '../PostEditor';

export default function EditPostPage() {
  const { slug } = useParams();
  const [post, setPost] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    authFetch(`/admin/posts/${slug}`)
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(setPost)
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [slug]);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <Loader2 size={20} className="animate-spin text-zinc-400" />
      </div>
    );
  }
  if (notFound) {
    return <p className="text-zinc-400 p-6">Post no trobat.</p>;
  }
  return <PostEditor initial={post} />;
}
