'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import MIcon from '../../../../components/ui/m-icon';
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
        <MIcon name="progress_activity" size={20} className="animate-spin text-secondary" />
      </div>
    );
  }
  if (notFound) {
    return <p className="text-secondary p-6">Post no trobat.</p>;
  }
  return <PostEditor initial={post} />;
}
