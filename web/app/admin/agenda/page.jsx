'use client';

import { useEffect, useState } from 'react';
import MIcon from '../../../components/ui/m-icon';
import { authFetch } from '../../lib/auth';

const EMPTY_EVENT = {
  title: '', description: '', date: '', location: '', link: '',
};

function formatFecha(iso) {
  return new Date(iso).toLocaleDateString('ca-ES', {
    weekday: 'short', day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function isPast(iso) {
  return new Date(iso) < new Date();
}

function EventForm({ initial = EMPTY_EVENT, onSave, onCancel, saving }) {
  const [form, setForm] = useState({
    ...EMPTY_EVENT,
    ...initial,
    date: initial.date
      ? new Date(initial.date).toISOString().slice(0, 16)
      : '',
  });

  function set(k, v) { setForm(f => ({ ...f, [k]: v })); }

  function handleSubmit(e) {
    e.preventDefault();
    onSave({ ...form, link: form.link || null, description: form.description || null });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid md:grid-cols-2 gap-4">
        <div className="md:col-span-2">
          <label className="block text-xs font-medium text-on-surface-variant mb-1.5">Títol *</label>
          <input
            type="text"
            value={form.title}
            onChange={e => set('title', e.target.value)}
            required
            placeholder="Nom de l'esdeveniment…"
            className="w-full border border-outline-variant rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-on-surface-variant mb-1.5">Data i hora *</label>
          <input
            type="datetime-local"
            value={form.date}
            onChange={e => set('date', e.target.value)}
            required
            className="w-full border border-outline-variant rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-on-surface-variant mb-1.5">Lloc</label>
          <input
            type="text"
            value={form.location}
            onChange={e => set('location', e.target.value)}
            className="w-full border border-outline-variant rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div className="md:col-span-2">
          <label className="block text-xs font-medium text-on-surface-variant mb-1.5">Descripció</label>
          <textarea
            value={form.description}
            onChange={e => set('description', e.target.value)}
            placeholder="Detalls opcionals de l'acte…"
            rows={3}
            className="w-full border border-outline-variant rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none"
          />
        </div>

        <div className="md:col-span-2">
          <label className="block text-xs font-medium text-on-surface-variant mb-1.5">Link extern (opcional)</label>
          <input
            type="url"
            value={form.link}
            onChange={e => set('link', e.target.value)}
            placeholder="https://…"
            className="w-full border border-outline-variant rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
      </div>

      <div className="flex gap-2 pt-1">
        <button
          type="submit"
          disabled={saving}
          className="flex items-center gap-1.5 bg-primary hover:opacity-90 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-60"
        >
          {saving ? <MIcon name="progress_activity" size={13} className="animate-spin" /> : <MIcon name="check" size={13} />}
          {saving ? 'Guardant…' : 'Guardar'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="flex items-center gap-1.5 border border-outline-variant text-on-surface-variant px-4 py-2 rounded-lg text-sm hover:bg-surface-container-high transition-colors"
        >
          <MIcon name="close" size={13} /> Cancel·lar
        </button>
      </div>
    </form>
  );
}

export default function AdminAgendaPage() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(null);
  const [showPast, setShowPast] = useState(false);
  // Lloc per defecte d'un esdeveniment nou: l'adreça del propi tenant en
  // lloc d'una hardcodejada — abans sempre deia "Ultra-Local Records...".
  const [defaultPlace, setDefaultPlace] = useState('');

  async function load() {
    const res = await authFetch('/admin/events');
    if (res.ok) setEvents(await res.json());
    setLoading(false);
  }

  useEffect(() => {
    load();
    authFetch('/admin/configuracio')
      .then(r => (r.ok ? r.json() : null))
      .then(config => { if (config) setDefaultPlace([config.fiscal_name, config.address].filter(Boolean).join(', ')); })
      .catch(() => {});
  }, []);

  async function handleSave(form, id = null) {
    setSaving(true);
    try {
      const res = await authFetch(
        id ? `/admin/events/${id}` : '/admin/events',
        { method: id ? 'PUT' : 'POST', body: JSON.stringify(form) }
      );
      if (res.ok) {
        await load();
        setCreating(false);
        setEditing(null);
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id, title) {
    if (!confirm(`Eliminar "${title}"?`)) return;
    setDeleting(id);
    try {
      await authFetch(`/admin/events/${id}`, { method: 'DELETE' });
      setEvents(ev => ev.filter(e => e.id !== id));
    } finally {
      setDeleting(null);
    }
  }

  const upcoming = events.filter(e => !isPast(e.date));
  const past = events.filter(e => isPast(e.date));
  const visible = showPast ? events : upcoming;

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold">Agenda</h1>
          <p className="text-sm text-secondary-foreground mt-0.5">
            {upcoming.length} propers · {past.length} passats
          </p>
        </div>
        {!creating && (
          <button
            onClick={() => setCreating(true)}
            className="flex items-center gap-1.5 bg-primary hover:opacity-90 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            <MIcon name="add" size={15} /> Nou esdeveniment
          </button>
        )}
      </div>

      {/* Formulari de creació */}
      {creating && (
        <div className="bg-card border border-outline-variant rounded-xl p-5">
          <p className="font-medium text-sm mb-4">Nou esdeveniment</p>
          <EventForm
            initial={{ ...EMPTY_EVENT, location: defaultPlace }}
            onSave={form => handleSave(form)}
            onCancel={() => setCreating(false)}
            saving={saving}
          />
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16">
          <MIcon name="progress_activity" size={20} className="animate-spin text-secondary-foreground" />
        </div>
      ) : events.length === 0 && !creating ? (
        <div className="text-center py-20 text-secondary-foreground">
          <MIcon name="calendar_today" size={32} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm mb-3">Sense esdeveniments.</p>
          <button
            onClick={() => setCreating(true)}
            className="text-on-surface hover:text-on-surface-variant text-sm font-medium"
          >
            Crear primer acte →
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {visible.map(event => (
            editing === event.id ? (
              <div key={event.id} className="bg-card border border-outline-variant rounded-xl p-5">
                <p className="font-medium text-sm mb-4">Editar esdeveniment</p>
                <EventForm
                  initial={event}
                  onSave={form => handleSave(form, event.id)}
                  onCancel={() => setEditing(null)}
                  saving={saving}
                />
              </div>
            ) : (
              <EventCard
                key={event.id}
                event={event}
                defaultPlace={defaultPlace}
                onEdit={() => setEditing(event.id)}
                onDelete={handleDelete}
                deleting={deleting}
              />
            )
          ))}

          {past.length > 0 && (
            <button
              onClick={() => setShowPast(v => !v)}
              className="w-full text-sm text-secondary-foreground hover:text-on-surface-variant py-3 border border-dashed border-outline-variant rounded-xl transition-colors"
            >
              {showPast ? `Amagar ${past.length} actes passats` : `Veure ${past.length} actes passats`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function EventCard({ event, defaultPlace, onEdit, onDelete, deleting }) {
  const past = isPast(event.date);
  return (
    <div className={`bg-card rounded-xl border p-4 transition-colors ${past ? 'opacity-60 border-outline-variant' : 'border-outline-variant hover:border-outline-variant'}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-medium text-on-surface">{event.title}</p>
            {past && (
              <span className="text-xs text-secondary-foreground bg-surface-container-high border border-outline-variant px-1.5 py-0.5 rounded">Passat</span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-3 mt-1 text-xs text-secondary-foreground">
            <span className="flex items-center gap-1">
              <MIcon name="calendar_today" size={10} /> {formatFecha(event.date)}
            </span>
            {event.location !== defaultPlace && (
              <span>{event.location}</span>
            )}
          </div>
          {event.description && (
            <p className="text-xs text-secondary-foreground mt-1.5 line-clamp-2">{event.description}</p>
          )}
          {event.link && (
            <a
              href={event.link}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-on-surface hover:text-on-surface-variant mt-1.5"
            >
              <MIcon name="open_in_new" size={10} /> {event.link.replace(/^https?:\/\//, '').slice(0, 40)}
            </a>
          )}
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={onEdit}
            className="p-1.5 text-secondary-foreground hover:text-on-surface-variant rounded-lg hover:bg-surface-container-high transition-colors"
          >
            <MIcon name="edit" size={13} />
          </button>
          <button
            onClick={() => onDelete(event.id, event.title)}
            disabled={deleting === event.id}
            className="p-1.5 text-secondary-foreground hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors disabled:opacity-50"
          >
            {deleting === event.id
              ? <MIcon name="progress_activity" size={13} className="animate-spin" />
              : <MIcon name="delete" size={13} />
            }
          </button>
        </div>
      </div>
    </div>
  );
}
