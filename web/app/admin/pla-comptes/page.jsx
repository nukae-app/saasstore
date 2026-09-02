'use client';

import { useEffect, useMemo, useState } from 'react';
import { authFetch } from '../../lib/auth';
import { useSortFilter } from '../../../components/admin/table/useSortFilter';
import { SortableTh } from '../../../components/admin/table/SortableTh';
import { useT } from '../../lib/i18n';

const TIPUS_CLS = {
  actiu: 'bg-blue-100 text-blue-700',
  passiu: 'bg-amber-100 text-amber-700',
  patrimoni_net: 'bg-purple-100 text-purple-700',
  ingres: 'bg-green-100 text-green-700',
  despesa: 'bg-red-100 text-red-700',
};

function TipusBadge({ tipus, label }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${TIPUS_CLS[tipus] || 'bg-zinc-100 text-zinc-700'}`}>
      {label}
    </span>
  );
}

export default function PlaComptesPage() {
  const t = useT();
  const [comptes, setComptes] = useState([]);
  const [loading, setLoading] = useState(true);

  const TIPUS_LABEL = useMemo(() => ({
    actiu: t('pla_comptes.type.actiu', 'Actiu'),
    passiu: t('pla_comptes.type.passiu', 'Passiu'),
    patrimoni_net: t('pla_comptes.type.patrimoni_net', 'Patrimoni net'),
    ingres: t('pla_comptes.type.ingres', 'Ingrés'),
    despesa: t('pla_comptes.type.despesa', 'Despesa'),
  }), [t]);

  useEffect(() => {
    authFetch('/admin/comptes-comptables')
      .then(r => r.json())
      .then(data => { setComptes(data); setLoading(false); });
  }, []);

  const columns = useMemo(() => ({
    codi: { sortValue: c => c.code },
    nom: { sortValue: c => c.name.toLowerCase() },
    grup: { sortValue: c => c.group, filterValue: c => `${t('pla_comptes.group', 'Grup')} ${c.group}` },
    tipus: { sortValue: c => TIPUS_LABEL[c.account_type] || c.account_type, filterValue: c => TIPUS_LABEL[c.account_type] || c.account_type },
  }), [t, TIPUS_LABEL]);

  const { rows: llista, sort, toggleSort, filters, setFilter, distinctValues } = useSortFilter(comptes, columns);

  return (
    <div className="space-y-5 max-w-4xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold text-zinc-900">{t('pla_comptes.title', 'Pla de comptes')}</h2>
        <p className="text-sm text-zinc-500 mt-1">
          {t('pla_comptes.subtitle', "Comptes del Pla General Comptable sembrats per aquest negoci. Es generen sols en donar-se d'alta la forma jurídica a Configuració — no es creen ni editen des d'aquí.")}
        </p>
      </div>

      <div className="bg-white rounded-2xl border border-zinc-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-zinc-400 text-sm">{t('common.loading', 'Carregant...')}</div>
        ) : llista.length === 0 ? (
          <div className="p-12 text-center text-zinc-400 text-sm">
            {t('pla_comptes.empty', "Encara no hi ha pla de comptes — fixa la forma jurídica a Configuració per sembrar-lo.")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-xs text-zinc-500 border-b border-zinc-200">
                <tr>
                  <SortableTh label={t('pla_comptes.col.code', 'Codi')} sortKey="codi" sort={sort} onSort={toggleSort} />
                  <SortableTh label={t('common.name', 'Nom')} sortKey="nom" sort={sort} onSort={toggleSort} />
                  <SortableTh label={t('pla_comptes.col.group', 'Grup')} sortKey="grup" sort={sort} onSort={toggleSort}
                    filterOptions={distinctValues.grup} selected={filters.grup} onFilterChange={setFilter} />
                  <SortableTh label={t('common.type', 'Tipus')} sortKey="tipus" sort={sort} onSort={toggleSort} align="center"
                    filterOptions={distinctValues.tipus} selected={filters.tipus} onFilterChange={setFilter} />
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {llista.map(c => (
                  <tr key={c.id} className={!c.active ? 'opacity-50' : ''}>
                    <td className="px-4 py-3 font-mono text-zinc-700">{c.code}</td>
                    <td className="px-4 py-3 text-zinc-900">{c.name}</td>
                    <td className="px-4 py-3 text-zinc-500 text-xs">{t('pla_comptes.group', 'Grup')} {c.group}</td>
                    <td className="px-4 py-3 text-center"><TipusBadge tipus={c.account_type} label={TIPUS_LABEL[c.account_type] || c.account_type} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
