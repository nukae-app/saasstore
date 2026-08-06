'use client';

import { useEffect, useRef, useState } from 'react';
import { Bold, Italic, Underline, Link2, Image as ImageIcon, List, ListOrdered, Heading2, Undo2, Redo2, Loader2 } from 'lucide-react';
import { authFetch } from '../../lib/auth';

const BUTTONS = [
  { cmd: 'bold', icon: Bold, title: 'Negreta' },
  { cmd: 'italic', icon: Italic, title: 'Cursiva' },
  { cmd: 'underline', icon: Underline, title: 'Subratllat' },
  { cmd: 'formatBlock', arg: 'h2', icon: Heading2, title: 'Títol' },
  { cmd: 'insertUnorderedList', icon: List, title: 'Llista' },
  { cmd: 'insertOrderedList', icon: ListOrdered, title: 'Llista numerada' },
];

// Editor WYSIWYG senzill (contentEditable + execCommand): sense dependències noves,
// pensat per a que l'admin escrigui la newsletter sense tocar HTML directament.
export default function RichTextEditor({ value, onChange }) {
  const ref = useRef(null);
  const lastValue = useRef(value);
  const fileRef = useRef(null);
  const savedRange = useRef(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    if (ref.current && value !== lastValue.current && document.activeElement !== ref.current) {
      ref.current.innerHTML = value || '';
    }
  }, [value]);

  function exec(cmd, arg) {
    ref.current?.focus();
    document.execCommand(cmd, false, arg);
    handleInput();
  }

  function handleInput() {
    const html = ref.current?.innerHTML || '';
    lastValue.current = html;
    onChange(html);
  }

  function handleLink() {
    const url = window.prompt('URL de l\'enllaç:', 'https://');
    if (url) exec('createLink', url);
  }

  function saveSelection() {
    const sel = window.getSelection();
    if (sel && sel.rangeCount > 0 && ref.current?.contains(sel.anchorNode)) {
      savedRange.current = sel.getRangeAt(0);
    }
  }

  function openImagePicker() {
    saveSelection();
    fileRef.current?.click();
  }

  async function handleImageFile(e) {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await authFetch('/admin/newsletter/images', { method: 'POST', body: fd });
      if (!res.ok) {
        alert('No s\'ha pogut pujar la imatge.');
        return;
      }
      const { url } = await res.json();

      ref.current?.focus();
      const sel = window.getSelection();
      if (savedRange.current) {
        sel.removeAllRanges();
        sel.addRange(savedRange.current);
      }
      document.execCommand(
        'insertHTML',
        false,
        `<img src="${url}" style="max-width:100%;height:auto;display:block;">`
      );
      handleInput();
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="border border-zinc-200 rounded-xl overflow-hidden">
      <div className="flex items-center gap-0.5 px-2 py-1.5 border-b border-zinc-200 bg-zinc-50 flex-wrap">
        {BUTTONS.map(({ cmd, arg, icon: Icon, title }) => (
          <button
            key={cmd + (arg || '')}
            type="button"
            title={title}
            onMouseDown={e => e.preventDefault()}
            onClick={() => exec(cmd, arg)}
            className="p-1.5 rounded text-zinc-600 hover:bg-zinc-200 transition-colors"
          >
            <Icon size={14} />
          </button>
        ))}
        <button
          type="button"
          title="Enllaç"
          onMouseDown={e => e.preventDefault()}
          onClick={handleLink}
          className="p-1.5 rounded text-zinc-600 hover:bg-zinc-200 transition-colors"
        >
          <Link2 size={14} />
        </button>
        <button
          type="button"
          title="Insereix imatge"
          disabled={uploading}
          onMouseDown={e => e.preventDefault()}
          onClick={openImagePicker}
          className="p-1.5 rounded text-zinc-600 hover:bg-zinc-200 transition-colors disabled:opacity-50"
        >
          {uploading ? <Loader2 size={14} className="animate-spin" /> : <ImageIcon size={14} />}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          onChange={handleImageFile}
          className="hidden"
        />
        <span className="w-px h-4 bg-zinc-300 mx-1" />
        <button
          type="button"
          title="Desfer"
          onMouseDown={e => e.preventDefault()}
          onClick={() => exec('undo')}
          className="p-1.5 rounded text-zinc-600 hover:bg-zinc-200 transition-colors"
        >
          <Undo2 size={14} />
        </button>
        <button
          type="button"
          title="Refer"
          onMouseDown={e => e.preventDefault()}
          onClick={() => exec('redo')}
          className="p-1.5 rounded text-zinc-600 hover:bg-zinc-200 transition-colors"
        >
          <Redo2 size={14} />
        </button>
      </div>
      <div
        ref={ref}
        contentEditable
        suppressContentEditableWarning
        onInput={handleInput}
        className="blog-content min-h-[350px] max-h-[600px] overflow-auto bg-white px-5 py-4 text-sm focus:outline-none"
      />
    </div>
  );
}
