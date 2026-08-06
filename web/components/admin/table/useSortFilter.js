'use client';

import { useMemo, useState } from 'react';

const EMPTY = '—';

/**
 * Client-side sort + Excel-style column filter over an already-loaded array.
 *
 * columns: { [key]: { sortValue?: (row) => string|number, filterValue?: (row) => string } }
 * A column with no entry in `filters` is unfiltered (all values shown).
 */
export function useSortFilter(rows, columns) {
  const [sort, setSort] = useState({ key: null, dir: 'asc' });
  const [filters, setFilters] = useState({});

  function toggleSort(key) {
    setSort(prev => {
      if (prev.key !== key) return { key, dir: 'asc' };
      if (prev.dir === 'asc') return { key, dir: 'desc' };
      return { key: null, dir: 'asc' };
    });
  }

  function setFilter(key, selected) {
    setFilters(prev => {
      if (!selected) {
        const next = { ...prev };
        delete next[key];
        return next;
      }
      return { ...prev, [key]: selected };
    });
  }

  const distinctValues = useMemo(() => {
    const out = {};
    for (const [key, col] of Object.entries(columns)) {
      if (!col.filterValue) continue;
      const set = new Set();
      rows.forEach(r => set.add(col.filterValue(r) ?? EMPTY));
      out[key] = [...set].sort((a, b) => a.localeCompare(b, 'ca', { numeric: true }));
    }
    return out;
  }, [rows, columns]);

  const filteredSorted = useMemo(() => {
    let out = rows;
    for (const [key, selected] of Object.entries(filters)) {
      const col = columns[key];
      if (!col?.filterValue) continue;
      out = out.filter(r => selected.has(col.filterValue(r) ?? EMPTY));
    }
    if (sort.key && columns[sort.key]?.sortValue) {
      const sv = columns[sort.key].sortValue;
      out = [...out].sort((a, b) => {
        const av = sv(a);
        const bv = sv(b);
        if (av == null) return bv == null ? 0 : 1;
        if (bv == null) return -1;
        let cmp;
        if (typeof av === 'number' && typeof bv === 'number') {
          cmp = av - bv;
        } else {
          cmp = String(av).localeCompare(String(bv), 'ca', { numeric: true });
        }
        return sort.dir === 'asc' ? cmp : -cmp;
      });
    }
    return out;
  }, [rows, filters, sort, columns]);

  return { rows: filteredSorted, sort, toggleSort, filters, setFilter, distinctValues };
}
