'use client';

import { useEffect, useState } from 'react';
import { Plus, Pencil, Trash2, Loader2, Calendar, ExternalLink, X, Check } from 'lucide-react';
import { authFetch } from '../../lib/auth';

const DEFAULT_PLACE = 'Ultra-Local Records, Pujades 113, Barcelona';

const EMPTY_EVENT = {
  titulo: '', descripcion: '', fecha: '', lugar: DEFAULT_PLACE, link: '',
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
    fecha: initial.fecha
      ? new Date(initial.fecha).toISOString().slice(0, 16)
      : '',
  });

  function set(k, v) { setForm(f => ({ ...f, [k]: v })); }

  function handleSubmit(e) {
    e.preventDefault();
    onSave({ ...form, link: form.link || null, descripcion: form.descripcion || null });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid md:grid-cols-2 gap-4">
        <div className="md:col-span-2">
          <label className="block text-xs font-medium text-zinc-600 mb-1.5">Títol *</label>
          <input
            type="text"
            value={form.titulo}
            onChange={e => set('titulo', e.target.value)}
            required
            placeholder="Nom de l'esdeveniment…"
            className="w-full border border-zinc-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-zinc-600 mb-1.5">Data i hora *</label>
          <input
            type="datetime-local"
            value={form.fecha}
            onChange={e => set('fecha', e.target.value)}
            required
            className="w-full border border-zinc-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-zinc-600 mb-1.5">Lloc</label>
          <input
            type="text"
            value={form.lugar}
            onChange={e => set('lugar', e.target.value)}
            className="w-full border border-zinc-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
          />
        </div>

        <div className="md:col-span-2">
          <label className="block text-xs font-medium text-zinc-600 mb-1.5">Descripció</label>
          <textarea
            value={form.descripcion}
            onChange={e => set('descripcion', e.target.value)}
            placeholder="Detalls opcionals de l'acte…"
            rows={3}
            className="w-full border border-zinc-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900 resize-none"
          />
        </div>

        <div className="md:col-span-2">
          <label className="block text-xs font-medium text-zinc-600 mb-1.5">Link extern (opcional)</label>
          <input
            type="url"
            value={form.link}
            onChange={e => set('link', e.target.value)}
            placeholder="https://…"
            className="w-full border border-zinc-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
          />
        </div>
      </div>

      <div className="flex gap-2 pt-1">
        <button
          type="submit"
          disabled={saving}
          className="flex items-center gap-1.5 bg-primary hover:bg-zinc-800 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-60"
        >
          {saving ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
          {saving ? 'Guardant…' : 'Guardar'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="flex items-center gap-1.5 border border-zinc-200 text-zinc-600 px-4 py-2 rounded-lg text-sm hover:bg-zinc-50 transition-colors"
        >
          <X size={13} /> Cancel·lar
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

  async function load() {
    const res = await authFetch('/admin/events');
    if (res.ok) setEvents(await res.json());
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

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

  async function handleDelete(id, titulo) {
    if (!confirm(`Eliminar "${titulo}"?`)) return;
    setDeleting(id);
    try {
      await authFetch(`/admin/events/${id}`, { method: 'DELETE' });
      setEvents(ev => ev.filter(e => e.id !== id));
    } finally {
      setDeleting(null);
    }
  }

  const upcoming = events.filter(e => !isPast(e.fecha));
  const past = events.filter(e => isPast(e.fecha));
  const visible = showPast ? events : upcoming;

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold">Agenda</h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            {upcoming.length} propers · {past.length} passats
          </p>
        </div>
        {!creating && (
          <button
            onClick={() => setCreating(true)}
            className="flex items-center gap-1.5 bg-primary hover:bg-zinc-800 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            <Plus size={15} /> Nou esdeveniment
          </button>
        )}
      </div>

      {/* Formulari de creació */}
      {creating && (
        <div className="bg-white border border-zinc-200 rounded-xl p-5">
          <p className="font-medium text-sm mb-4">Nou esdeveniment</p>
          <EventForm
            onSave={form => handleSave(form)}
            onCancel={() => setCreating(false)}
            saving={saving}
          />
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 size={20} className="animate-spin text-zinc-400" />
        </div>
      ) : events.length === 0 && !creating ? (
        <div className="text-center py-20 text-zinc-400">
          <Calendar size={32} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm mb-3">Sense esdeveniments.</p>
          <button
            onClick={() => setCreating(true)}
            className="text-zinc-900 hover:text-zinc-600 text-sm font-medium"
          >
            Crear primer acte →
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {visible.map(event => (
            editing === event.id ? (
              <div key={event.id} className="bg-white border border-zinc-300 rounded-xl p-5">
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
                onEdit={() => setEditing(event.id)}
                onDelete={handleDelete}
                deleting={deleting}
              />
            )
          ))}

          {past.length > 0 && (
            <button
              onClick={() => setShowPast(v => !v)}
              className="w-full text-sm text-zinc-400 hover:text-zinc-600 py-3 border border-dashed border-zinc-200 rounded-xl transition-colors"
            >
              {showPast ? `Amagar ${past.length} actes passats` : `Veure ${past.length} actes passats`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function EventCard({ event, onEdit, onDelete, deleting }) {
  const past = isPast(event.fecha);
  return (
    <div className={`bg-white rounded-xl border p-4 transition-colors ${past ? 'opacity-60 border-zinc-100' : 'border-zinc-100 hover:border-zinc-200'}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-medium text-zinc-900">{event.titulo}</p>
            {past && (
              <span className="text-xs text-zinc-400 bg-zinc-50 border border-zinc-200 px-1.5 py-0.5 rounded">Passat</span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-3 mt-1 text-xs text-zinc-500">
            <span className="flex items-center gap-1">
              <Calendar size={10} /> {formatFecha(event.fecha)}
            </span>
            {event.lugar !== DEFAULT_PLACE && (
              <span>{event.lugar}</span>
            )}
          </div>
          {event.descripcion && (
            <p className="text-xs text-zinc-500 mt-1.5 line-clamp-2">{event.descripcion}</p>
          )}
          {event.link && (
            <a
              href={event.link}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-zinc-900 hover:text-zinc-600 mt-1.5"
            >
              <ExternalLink size={10} /> {event.link.replace(/^https?:\/\//, '').slice(0, 40)}
            </a>
          )}
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={onEdit}
            className="p-1.5 text-zinc-400 hover:text-zinc-700 rounded-lg hover:bg-zinc-100 transition-colors"
          >
            <Pencil size={13} />
          </button>
          <button
            onClick={() => onDelete(event.id, event.titulo)}
            disabled={deleting === event.id}
            className="p-1.5 text-zinc-300 hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors disabled:opacity-50"
          >
            {deleting === event.id
              ? <Loader2 size={13} className="animate-spin" />
              : <Trash2 size={13} />
            }
          </button>
        </div>
      </div>
    </div>
  );
}
