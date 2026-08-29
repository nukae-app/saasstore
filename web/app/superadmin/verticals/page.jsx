'use client';

import { useCallback, useEffect, useState } from 'react';
import { Plus, Loader2, Pencil } from 'lucide-react';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Label } from '../../../components/ui/label';
import { Badge } from '../../../components/ui/badge';
import { Switch } from '../../../components/ui/switch';
import { Checkbox } from '../../../components/ui/checkbox';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../../components/ui/select';
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from '../../../components/ui/table';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../../components/ui/dialog';
import { superadminAuthFetch } from '../../lib/superadmin-auth';

// Mismo criterio que api/app/verticals_registry.py: solo se ofrecen las
// combinaciones que tienen algo real detrás en código, no texto libre — ver
// docs/ARQUITECTURA_CORE_VERTICAL.md §20.
const CATALOG_PROVIDERS = [{ value: 'discogs', label: 'Discogs' }];

const PRODUCT_ARCHETYPES = [
  { value: 'record', label: 'Discos (implementat: RecordProduct/RecordStockDetail)' },
  { value: 'floristry', label: 'Floristeria (implementat: ReleaseFloristeria)' },
  { value: 'media_catalog', label: 'Media/catàleg — llibres... (planejat, sense taula)' },
  { value: 'consumable', label: 'Consumible — cafè, vi, formatge... (planejat, sense taula)' },
  { value: 'botanical', label: 'Botànic — plantes... (planejat, sense taula)' },
  { value: 'retail_simple', label: 'Retail simple — joguines, cosmètica... (planejat, sense taula)' },
  { value: 'apparel_variant', label: 'Variant talla/color — roba (planejat, sense taula)' },
];

const FEATURE_KEYS = [
  { key: 'discogs_sync', label: 'Sincronització amb Discogs' },
  { key: 'subscriptions', label: 'Club de subscripció' },
  { key: 'catalog_browse_mode', label: 'Mode "Remena" (cubetes) al catàleg' },
  { key: 'catalog_format_filter', label: 'Filtre de format al catàleg' },
  { key: 'catalog_genre_filter', label: 'Filtre de gènere al catàleg' },
];

const NONE_VALUE = '__none__';

const EMPTY_FORM = {
  id: '', name_ca: '', name_es: '', name_en: '',
  catalog_provider: NONE_VALUE, product_archetype: NONE_VALUE, default_features: {},
};

function archetypeLabel(value) {
  return PRODUCT_ARCHETYPES.find((a) => a.value === value)?.label.split(' (')[0] ?? value;
}

export default function SuperadminVerticalsPage() {
  const [verticals, setVerticals] = useState(null);
  const [editing, setEditing] = useState(null); // null = tancat, {} = creant, vertical = editant
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    // include_inactive: a diferència del <select> d'alta de tenant, aquí cal
    // veure també els desactivats per poder-los reactivar.
    const res = await superadminAuthFetch('/superadmin/verticals?include_inactive=true');
    if (res.ok) setVerticals(await res.json());
  }, []);

  useEffect(() => { load(); }, [load]);

  function openCreate() {
    setForm(EMPTY_FORM);
    setError('');
    setEditing({});
  }

  function openEdit(vertical) {
    setForm({
      id: vertical.id, name_ca: vertical.name_ca, name_es: vertical.name_es, name_en: vertical.name_en,
      catalog_provider: vertical.catalog_provider ?? NONE_VALUE,
      product_archetype: vertical.product_archetype ?? NONE_VALUE,
      default_features: vertical.default_features ?? {},
    });
    setError('');
    setEditing(vertical);
  }

  function toggleFeature(key, checked) {
    setForm((f) => ({ ...f, default_features: { ...f.default_features, [key]: checked } }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setSaving(true);
    try {
      const isCreate = !editing?.id;
      const payload = {
        name_ca: form.name_ca, name_es: form.name_es, name_en: form.name_en,
        catalog_provider: form.catalog_provider === NONE_VALUE ? null : form.catalog_provider,
        product_archetype: form.product_archetype === NONE_VALUE ? null : form.product_archetype,
        // Solo se guardan las claves marcadas: una feature ausente del dict
        // equivale a "no activada por defecto", igual que hoy en TenantFeature.
        default_features: Object.fromEntries(
          Object.entries(form.default_features).filter(([, v]) => v),
        ),
      };
      const res = isCreate
        ? await superadminAuthFetch('/superadmin/verticals', { method: 'POST', body: JSON.stringify({ id: form.id, ...payload }) })
        : await superadminAuthFetch(`/superadmin/verticals/${editing.id}`, { method: 'PATCH', body: JSON.stringify(payload) });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.detail?.[0]?.msg || body.detail || 'No s\'ha pogut desar el vertical.');
        return;
      }
      setEditing(null);
      load();
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleActive(vertical, next) {
    const res = await superadminAuthFetch(`/superadmin/verticals/${vertical.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ active: next }),
    });
    if (res.ok) load();
  }

  return (
    <div className="space-y-5 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Verticals</h2>
          <p className="text-sm text-slate-500 mt-1">
            Tipus de negoci que pot tenir un tenant (discos, floristeria, cafè...). Desactivar-ne un
            el treu del selector d&apos;alta de tenant nou, sense afectar els tenants que ja el fan servir.
            Un vertical &quot;planejat&quot; (sense arquetip implementat) es pot registrar ja, però un tenant
            d&apos;aquest vertical vendria producte Core pur (nom/preu/estoc) fins que es construeixi la seva taula.
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus size={16} /> Nou vertical
        </Button>
      </div>

      {verticals === null ? (
        <div className="flex items-center gap-2 text-slate-500 text-sm">
          <Loader2 size={14} className="animate-spin" /> Carregant...
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Id</TableHead>
              <TableHead>Nom (CAT)</TableHead>
              <TableHead>Proveïdor catàleg</TableHead>
              <TableHead>Arquetip</TableHead>
              <TableHead>Actiu</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {verticals.map((v) => (
              <TableRow key={v.id}>
                <TableCell className="font-mono text-xs text-slate-500">{v.id}</TableCell>
                <TableCell>{v.name_ca}</TableCell>
                <TableCell className="text-slate-500">
                  {v.catalog_provider
                    ? <Badge variant="secondary">{v.catalog_provider}</Badge>
                    : <span className="text-slate-300">—</span>}
                </TableCell>
                <TableCell className="text-slate-500 text-sm">
                  {v.product_archetype ? archetypeLabel(v.product_archetype) : <span className="text-slate-300">—</span>}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Switch checked={v.active} onCheckedChange={(next) => handleToggleActive(v, next)} />
                    <Badge variant={v.active ? 'default' : 'secondary'}>{v.active ? 'Actiu' : 'Inactiu'}</Badge>
                  </div>
                </TableCell>
                <TableCell>
                  <Button variant="ghost" size="sm" onClick={() => openEdit(v)}>
                    <Pencil size={14} />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog open={!!editing} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editing?.id ? `Editar ${editing.id}` : 'Nou vertical'}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4 max-h-[70vh] overflow-y-auto pr-1">
            {!editing?.id && (
              <div className="space-y-1.5">
                <Label htmlFor="v-id">Id</Label>
                <Input id="v-id" required value={form.id}
                  onChange={(e) => setForm((f) => ({ ...f, id: e.target.value }))}
                  placeholder="coffee" />
                <p className="text-xs text-slate-400">
                  Minúscules/dígits/guió baix, sense espais — identificador tècnic estable, no editable després.
                </p>
              </div>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="v-ca">Nom (català)</Label>
              <Input id="v-ca" required value={form.name_ca}
                onChange={(e) => setForm((f) => ({ ...f, name_ca: e.target.value }))} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="v-es">Nom (castellà)</Label>
              <Input id="v-es" required value={form.name_es}
                onChange={(e) => setForm((f) => ({ ...f, name_es: e.target.value }))} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="v-en">Nom (anglès)</Label>
              <Input id="v-en" required value={form.name_en}
                onChange={(e) => setForm((f) => ({ ...f, name_en: e.target.value }))} />
            </div>

            <div className="space-y-1.5">
              <Label>Proveïdor de catàleg (buscador de referències a compres)</Label>
              <Select value={form.catalog_provider} onValueChange={(v) => setForm((f) => ({ ...f, catalog_provider: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE_VALUE}>— (cap, alta manual)</SelectItem>
                  {CATALOG_PROVIDERS.map((p) => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label>Arquetip de producte</Label>
              <Select value={form.product_archetype} onValueChange={(v) => setForm((f) => ({ ...f, product_archetype: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE_VALUE}>— (encara sense taula d&apos;extensió)</SelectItem>
                  {PRODUCT_ARCHETYPES.map((a) => <SelectItem key={a.value} value={a.value}>{a.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label>Features per defecte d&apos;un tenant nou d&apos;aquest vertical</Label>
              <div className="space-y-2 border border-slate-200 rounded-lg p-3">
                {FEATURE_KEYS.map(({ key, label }) => (
                  <label key={key} className="flex items-center gap-2 text-sm text-slate-700">
                    <Checkbox
                      checked={!!form.default_features[key]}
                      onCheckedChange={(checked) => toggleFeature(key, !!checked)}
                    />
                    {label}
                  </label>
                ))}
              </div>
              <p className="text-xs text-slate-400">
                Encara no s&apos;aplica automàticament en donar d&apos;alta un tenant — es guarda per quan
                s&apos;abordi (docs/ARQUITECTURA_CORE_VERTICAL.md §20).
              </p>
            </div>

            {error && <p className="text-sm text-red-600">{error}</p>}
            <DialogFooter>
              <Button type="submit" disabled={saving}>
                {saving ? 'Desant...' : 'Desar'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
