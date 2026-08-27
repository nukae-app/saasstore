'use client';

import { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import { Plus, Pencil, Trash2, Star, Loader2, X, Check } from 'lucide-react';
import { authFetch } from '../../../../components/store/AuthProvider';

const EMPTY = {
  recipient_name: '', address_line1: '', address_line2: '',
  city: '', postal_code: '', province: '', country: 'ES', phone: '', is_default: false,
};

function AddressForm({ initial = EMPTY, onSave, onCancel, saving }) {
  const t = useTranslations('compte');
  const [form, setForm] = useState({ ...EMPTY, ...initial });
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  function handleSubmit(e) {
    e.preventDefault();
    onSave(form);
  }

  const fields = [
    { key: 'recipient_name', label: t('recipientName'), required: true, col: 'col-span-2' },
    { key: 'address_line1', label: t('address'), required: true, col: 'col-span-2', placeholder: t('addressPlaceholder') },
    { key: 'address_line2', label: t('address2'), col: 'col-span-2', placeholder: t('address2Placeholder') },
    { key: 'postal_code', label: t('postalCode'), required: true },
    { key: 'city', label: t('city'), required: true },
    { key: 'province', label: t('province') },
    { key: 'country', label: t('country'), required: true },
    { key: 'phone', label: t('phone'), placeholder: t('phoneForCarrier') },
  ];

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        {fields.map(({ key, label, required, col = '', placeholder }) => (
          <div key={key} className={col}>
            <label className="block text-xs font-medium text-zinc-600 mb-1">
              {label}{required && <span className="text-red-400 ml-0.5">*</span>}
            </label>
            <input
              type="text"
              value={form[key]}
              onChange={e => set(key, e.target.value)}
              required={required}
              placeholder={placeholder}
              className="w-full border border-zinc-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
            />
          </div>
        ))}
      </div>

      <label className="flex items-center gap-2.5 cursor-pointer">
        <input
          type="checkbox"
          checked={form.is_default}
          onChange={e => set('is_default', e.target.checked)}
          className="accent-zinc-900"
        />
        <span className="text-sm text-zinc-700">{t('setAsDefaultAddress')}</span>
      </label>

      <div className="flex gap-2 pt-1">
        <button
          type="submit"
          disabled={saving}
          className="flex items-center gap-1.5 bg-primary hover:bg-zinc-800 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-60"
        >
          {saving ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
          {saving ? t('savingEllipsis') : t('save')}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="flex items-center gap-1.5 border border-zinc-200 text-zinc-600 px-4 py-2 rounded-lg text-sm hover:bg-zinc-50 transition-colors"
        >
          <X size={13} /> {t('cancel')}
        </button>
      </div>
    </form>
  );
}

function AddressCard({ addr, onEdit, onDelete, onSetDefault, loading }) {
  const t = useTranslations('compte');
  return (
    <div className={`relative bg-white rounded-xl border p-4 transition-colors ${addr.is_default ? 'border-zinc-300 bg-zinc-50' : 'border-zinc-100'}`}>
      {addr.is_default && (
        <span className="absolute top-3 right-3 flex items-center gap-1 text-xs text-zinc-700 font-medium">
          <Star size={11} className="fill-zinc-700 text-zinc-700" /> {t('default')}
        </span>
      )}
      <address className="not-italic text-sm text-zinc-700 leading-relaxed mb-3">
        <p className="font-medium">{addr.recipient_name}</p>
        <p className="text-zinc-500">{addr.address_line1}</p>
        {addr.address_line2 && <p className="text-zinc-500">{addr.address_line2}</p>}
        <p className="text-zinc-500">{addr.postal_code} {addr.city}{addr.province ? `, ${addr.province}` : ''}</p>
        <p className="text-zinc-500">{addr.country}</p>
        {addr.phone && <p className="text-zinc-400 text-xs mt-0.5">{addr.phone}</p>}
      </address>
      <div className="flex items-center gap-2 flex-wrap">
        {!addr.is_default && (
          <button
            onClick={() => onSetDefault(addr.id)}
            disabled={!!loading}
            className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-900 border border-zinc-200 hover:border-zinc-300 px-2.5 py-1.5 rounded-lg transition-colors disabled:opacity-50"
          >
            <Star size={11} /> {t('makeDefault')}
          </button>
        )}
        <button
          onClick={() => onEdit(addr)}
          className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-900 border border-zinc-200 px-2.5 py-1.5 rounded-lg transition-colors"
        >
          <Pencil size={11} /> {t('edit')}
        </button>
        <button
          onClick={() => onDelete(addr.id)}
          disabled={!!loading}
          className="flex items-center gap-1.5 text-xs text-zinc-400 hover:text-red-500 border border-zinc-200 hover:border-red-200 px-2.5 py-1.5 rounded-lg transition-colors disabled:opacity-50"
        >
          {loading === addr.id ? <Loader2 size={11} className="animate-spin" /> : <Trash2 size={11} />}
          {t('remove')}
        </button>
      </div>
    </div>
  );
}

export default function AdrecesPage() {
  const t = useTranslations('compte');
  const [addresses, setAddresses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null); // null | 'new' | address object
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(null);

  async function load() {
    const res = await authFetch('/me/addresses');
    if (res.ok) setAddresses(await res.json());
  }

  useEffect(() => { load().finally(() => setLoading(false)); }, []);

  async function handleSave(form) {
    setSaving(true);
    try {
      const isEdit = editing && editing !== 'new';
      const res = await authFetch(
        isEdit ? `/me/addresses/${editing.id}` : '/me/addresses',
        { method: isEdit ? 'PUT' : 'POST', body: JSON.stringify(form) }
      );
      if (res.ok) { await load(); setEditing(null); }
    } finally { setSaving(false); }
  }

  async function handleDelete(id) {
    setDeleting(id);
    try {
      await authFetch(`/me/addresses/${id}`, { method: 'DELETE' });
      await load();
    } finally { setDeleting(null); }
  }

  async function handleSetDefault(id) {
    setDeleting(id);
    try {
      await authFetch(`/me/addresses/${id}/set-default`, { method: 'POST' });
      await load();
    } finally { setDeleting(null); }
  }

  return (
    <div className="max-w-2xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="font-serif italic text-2xl md:text-3xl">{t('myAddresses')}</h1>
        {editing === null && (
          <button
            onClick={() => setEditing('new')}
            className="flex items-center gap-1.5 bg-primary hover:bg-zinc-800 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            <Plus size={14} /> {t('newAddress')}
          </button>
        )}
      </div>

      {/* New address form */}
      {editing === 'new' && (
        <div className="bg-white rounded-xl border border-zinc-200 p-5 mb-4">
          <p className="font-medium text-sm mb-4">{t('newAddress')}</p>
          <AddressForm onSave={handleSave} onCancel={() => setEditing(null)} saving={saving} />
        </div>
      )}

      {loading ? (
        <div className="space-y-3">
          {[1, 2].map(i => <div key={i} className="animate-pulse bg-zinc-100 rounded-xl h-28" />)}
        </div>
      ) : addresses.length === 0 && editing === null ? (
        <div className="bg-white rounded-xl shadow-[0_2px_20px_-6px_rgba(15,23,42,0.08)] p-10 text-center">
          <p className="text-zinc-400 text-sm mb-4">{t('noAddressesSaved')}</p>
          <button
            onClick={() => setEditing('new')}
            className="inline-flex items-center gap-1.5 bg-primary hover:bg-zinc-800 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors"
          >
            <Plus size={14} /> {t('addFirstAddress')}
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {addresses.map(addr => (
            editing && editing !== 'new' && editing.id === addr.id ? (
              <div key={addr.id} className="bg-white rounded-xl border border-zinc-300 p-5">
                <p className="font-medium text-sm mb-4">{t('editAddress')}</p>
                <AddressForm
                  initial={editing}
                  onSave={handleSave}
                  onCancel={() => setEditing(null)}
                  saving={saving}
                />
              </div>
            ) : (
              <AddressCard
                key={addr.id}
                addr={addr}
                onEdit={setEditing}
                onDelete={handleDelete}
                onSetDefault={handleSetDefault}
                loading={deleting}
              />
            )
          ))}
        </div>
      )}
    </div>
  );
}
