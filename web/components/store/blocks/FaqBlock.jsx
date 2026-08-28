'use client';

import { useState } from 'react';
import { ChevronDown } from 'lucide-react';

// Bloc "faq" (ver api/app/blocks/registry.py::FaqProps) — preguntes freqüents
// en acordió, tot copy del tenant. Sense llibreria nova: un `useState` amb
// l'índex obert n'hi ha prou per a una llista curta de preguntes.
export default function FaqBlock({ id, heading, items = [] }) {
  const [openIndex, setOpenIndex] = useState(null);

  if (!items || items.length === 0) return null;

  return (
    <section
      data-block-id={id}
      style={{
        paddingTop: 'var(--spacing-density)',
        paddingBottom: 'var(--spacing-density)',
        borderTop: 'var(--section-divider, none)',
      }}
      className="px-5 md:px-16 bg-white"
    >
      <div className="max-w-2xl mx-auto">
        {heading && (
          <h2 className="font-serif italic text-3xl md:text-4xl text-center mb-12 md:mb-16">{heading}</h2>
        )}
        <div className="divide-y divide-zinc-200 border-t border-b border-zinc-200">
          {items.map((item, i) => {
            const open = openIndex === i;
            return (
              <div key={i}>
                <button
                  type="button"
                  onClick={() => setOpenIndex(open ? null : i)}
                  aria-expanded={open}
                  className="w-full flex items-center justify-between gap-4 py-5 text-left"
                >
                  <span className="font-medium text-zinc-900">{item.question}</span>
                  <ChevronDown
                    size={18}
                    className={`shrink-0 text-zinc-400 transition-transform duration-300 ${open ? 'rotate-180' : ''}`}
                  />
                </button>
                <div
                  className="grid transition-[grid-template-rows] duration-300 ease-out"
                  style={{ gridTemplateRows: open ? '1fr' : '0fr' }}
                >
                  <div className="overflow-hidden">
                    <p className="text-zinc-500 leading-relaxed pb-5 whitespace-pre-line">{item.answer}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
