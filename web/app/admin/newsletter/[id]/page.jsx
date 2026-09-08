'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import MIcon from '../../../../components/ui/m-icon';
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
        <MIcon name="progress_activity" size={20} className="animate-spin text-secondary-foreground" />
      </div>
    );
  }
  if (notFound) {
    return <p className="text-secondary-foreground p-6">Campanya no trobada.</p>;
  }
  return <CampaignEditor initial={campaign} />;
}
