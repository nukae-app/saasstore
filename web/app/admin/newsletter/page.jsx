'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Plus, Pencil, Trash2, Loader2, Send, Mail } from 'lucide-react';
import { authFetch } from '../../lib/auth';

function formatDate(iso) {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString('ca-ES', { day: 'numeric', month: 'short', year: 'numeric' });
}

const ESTAT_STYLES = {
  esborrany: 'bg-amber-50 border-amber-200 text-amber-700',
  enviant: 'bg-blue-50 border-blue-200 text-blue-700',
  enviada: 'bg-emerald-50 border-emerald-200 text-emerald-700',
};

const ESTAT_LABELS = {
  esborrany: 'Esborrany',
  enviant: 'Enviant…',
  enviada: 'Enviada',
};

export default function AdminNewsletterPage() {
  const [campaigns, setCampaigns] = useState([]);
  const [recipients, setRecipients] = useState(null);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(null);

  async function load() {
    const [resCampaigns, resRecipients] = await Promise.all([
      authFetch('/admin/newsletter'),
      authFetch('/admin/newsletter/recipients/count'),
    ]);
    if (resCampaigns.ok) setCampaigns(await resCampaigns.json());
    if (resRecipients.ok) setRecipients((await resRecipients.json()).total);
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  // Poll mentre hi hagi campanyes enviant-se, per veure el progrés des del llistat
  useEffect(() => {
    if (!campaigns.some(c => c.status === 'enviant')) return;
    const id = setInterval(load, 4000);
    return () => clearInterval(id);
  }, [campaigns]);

  async function handleDelete(id, subject) {
    if (!confirm(`Eliminar l'esborrany "${subject}"? Aquesta acció no es pot desfer.`)) return;
    setDeleting(id);
    try {
      await authFetch(`/admin/newsletter/${id}`, { method: 'DELETE' });
      setCampaigns(cs => cs.filter(c => c.id !== id));
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Newsletter</h1>
          <p className="text-sm text-zinc-500 mt-0.5 flex items-center gap-1.5">
            <Mail size={13} />
            {recipients === null ? '…' : recipients} subscriptors actius
          </p>
        </div>
        <Link
          href="/admin/newsletter/nou"
          className="flex items-center gap-1.5 bg-primary hover:bg-zinc-800 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          <Plus size={15} /> Nova campanya
        </Link>
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 size={20} className="animate-spin text-zinc-400" />
        </div>
      ) : campaigns.length === 0 ? (
        <div className="text-center py-20 text-zinc-400">
          <p className="mb-4">Encara no hi ha cap campanya.</p>
          <Link href="/admin/newsletter/nou" className="text-zinc-900 hover:text-zinc-600 font-medium text-sm">
            Crea la primera →
          </Link>
        </div>
      ) : (
        <div className="bg-white shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] rounded-xl overflow-hidden">
          {campaigns.map(c => (
            <CampaignRow key={c.id} campaign={c} onDelete={handleDelete} deleting={deleting} />
          ))}
        </div>
      )}
    </div>
  );
}

function CampaignRow({ campaign, onDelete, deleting }) {
  const { pendent, enviat, error } = campaign.counts;
  const total = pendent + enviat + error;
  return (
    <div className="flex items-center gap-4 px-4 py-3 border-b border-zinc-50 last:border-0 hover:bg-zinc-50/50 transition-colors">
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm text-zinc-900 truncate">{campaign.subject}</p>
        <div className="flex items-center gap-3 mt-0.5">
          <span className="text-xs text-zinc-400">{formatDate(campaign.created_at)}</span>
          <span className={`text-xs px-1.5 py-0.5 rounded font-medium border ${ESTAT_STYLES[campaign.status]}`}>
            {ESTAT_LABELS[campaign.status]}
          </span>
          {total > 0 && (
            <span className="text-xs text-zinc-400">
              {enviat}/{total} enviats{error > 0 ? ` · ${error} errors` : ''}
            </span>
          )}
        </div>
      </div>
      <div className="flex items-center gap-1.5 shrink-0">
        <Link
          href={`/admin/newsletter/${campaign.id}`}
          className="p-1.5 text-zinc-400 hover:text-zinc-700 rounded-lg hover:bg-zinc-100 transition-colors"
          title={campaign.status === 'esborrany' ? 'Editar' : 'Veure'}
        >
          {campaign.status === 'esborrany' ? <Pencil size={13} /> : <Send size={13} />}
        </Link>
        {campaign.status === 'esborrany' && (
          <button
            onClick={() => onDelete(campaign.id, campaign.subject)}
            disabled={deleting === campaign.id}
            className="p-1.5 text-zinc-300 hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors disabled:opacity-50"
            title="Eliminar"
          >
            {deleting === campaign.id
              ? <Loader2 size={13} className="animate-spin" />
              : <Trash2 size={13} />
            }
          </button>
        )}
      </div>
    </div>
  );
}
