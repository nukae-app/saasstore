'use client';

import { useMemo, useState } from 'react';
import { ArrowUp, ArrowDown, ChevronsUpDown, Filter, Search } from 'lucide-react';
import { Popover, PopoverTrigger, PopoverContent } from '../../ui/popover';
import { Checkbox } from '../../ui/checkbox';
import { cn } from '../../lib/utils';

/**
 * <th> drop-in with click-to-sort and an optional Excel-style checkbox filter popover.
 * Matches the existing hand-rolled table header styling (bg-zinc-50 / text-zinc-500).
 */
export function SortableTh({
  label,
  sortKey,
  sort,
  onSort,
  filterOptions,
  selected,
  onFilterChange,
  align = 'left',
  className,
}) {
  const hasFilter = Array.isArray(filterOptions);
  const isSorted = sort?.key === sortKey;
  const isFiltered = hasFilter && selected != null && selected.size < filterOptions.length;

  const alignClass = align === 'right' ? 'justify-end text-right' : align === 'center' ? 'justify-center text-center' : 'justify-start text-left';

  return (
    <th className={cn('px-4 py-3 font-medium', alignClass, className)}>
      <div className={cn('flex items-center gap-1', alignClass)}>
        <button
          type="button"
          onClick={() => onSort?.(sortKey)}
          className="flex items-center gap-1 hover:text-zinc-800 transition-colors"
        >
          <span>{label}</span>
          {isSorted ? (
            sort.dir === 'asc' ? <ArrowUp size={12} /> : <ArrowDown size={12} />
          ) : (
            <ChevronsUpDown size={12} className="text-zinc-300" />
          )}
        </button>
        {hasFilter && (
          <FilterPopover
            options={filterOptions}
            selected={selected}
            onChange={sel => onFilterChange?.(sortKey, sel)}
            active={isFiltered}
          />
        )}
      </div>
    </th>
  );
}

function FilterPopover({ options, selected, onChange, active }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');

  const effective = selected ?? new Set(options);
  const visibleOptions = useMemo(() => {
    if (!q.trim()) return options;
    const ql = q.trim().toLowerCase();
    return options.filter(o => o.toLowerCase().includes(ql));
  }, [options, q]);

  function toggle(value) {
    const next = new Set(effective);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    onChange(next.size === options.length ? null : next);
  }

  function selectAll() {
    onChange(null);
  }

  function clearAll() {
    onChange(new Set());
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          title="Filtrar"
          className={cn(
            'p-0.5 rounded transition-colors',
            active ? 'text-zinc-900' : 'text-zinc-300 hover:text-zinc-500',
          )}
        >
          <Filter size={12} fill={active ? 'currentColor' : 'none'} />
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-56 normal-case font-normal">
        <div className="relative mb-2">
          <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-zinc-400" />
          <input
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="Cercar..."
            className="w-full pl-6 pr-2 py-1.5 text-xs border border-zinc-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-zinc-900"
          />
        </div>
        <div className="flex items-center justify-between mb-1.5 text-xs">
          <button type="button" onClick={selectAll} className="text-zinc-500 hover:text-zinc-800">
            Seleccionar-ho tot
          </button>
          <button type="button" onClick={clearAll} className="text-zinc-500 hover:text-zinc-800">
            Netejar
          </button>
        </div>
        <div className="max-h-56 overflow-y-auto space-y-0.5">
          {visibleOptions.length === 0 && (
            <p className="text-xs text-zinc-400 px-1 py-1">Cap resultat.</p>
          )}
          {visibleOptions.map(value => (
            <label key={value} className="flex items-center gap-2 px-1 py-1 rounded hover:bg-zinc-50 cursor-pointer text-xs text-zinc-700">
              <Checkbox checked={effective.has(value)} onCheckedChange={() => toggle(value)} />
              <span className="truncate">{value}</span>
            </label>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}
