'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { authFetch } from '../../../lib/auth';
import CampaignEditor from '../CampaignEditor';

export default function EditCampaignPage() {
  const { id } = useParams();
  const [campaign, setCampaign] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    authFetch(`/admin/newsletter/${id}`)
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(setCampaign)
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <Loader2 size={20} className="animate-spin text-zinc-400" />
      </div>
    );
  }
  if (notFound) {
    return <p className="text-zinc-400 p-6">Campanya no trobada.</p>;
  }
  return <CampaignEditor initial={campaign} />;
}
