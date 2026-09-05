import { useState, type FC } from 'react';
import { X, Copy, Check } from 'lucide-react';
import type { FootnotePair } from '../domain/types';

interface FootnotePopupProps {
  footnote: FootnotePair | null;
  onClose: () => void;
}

export const FootnotePopup: FC<FootnotePopupProps> = ({ footnote, onClose }) => {
  const [copied, setCopied] = useState(false);

  if (!footnote) return null;

  const handleCopy = () => {
    const textToCopy = `${footnote.textRu}\n\nOriginal: ${footnote.textEn}`;
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center p-3 sm:items-center sm:p-4 bg-black/40 backdrop-blur-xs animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Сноска ${footnote.id}`}
        className="w-full max-w-lg rounded-2xl border p-5 shadow-2xl transition-all sm:p-6"
        style={{
          backgroundColor: 'var(--bg-card)',
          borderColor: 'var(--border-strong)',
          color: 'var(--text-primary)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b pb-3" style={{ borderColor: 'var(--border-subtle)' }}>
          <div className="flex items-center space-x-2.5">
            <span
              className="flex h-6 w-6 items-center justify-center rounded-md text-xs font-bold"
              style={{ backgroundColor: 'var(--accent-soft)', color: 'var(--accent)' }}
            >
              {footnote.id}
            </span>
            <span className="text-xs font-semibold uppercase tracking-wider opacity-70" style={{ color: 'var(--text-secondary)' }}>
              Сноска и комментарий
            </span>
          </div>

          <div className="flex items-center space-x-1">
            <button
              type="button"
              onClick={handleCopy}
              title="Скопировать текст сноски"
              className="rounded-lg p-1.5 transition-all hover:opacity-75 active:scale-95"
              style={{ backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)' }}
            >
              {copied ? <Check className="h-4 w-4 text-emerald-500" /> : <Copy className="h-4 w-4" />}
            </button>
            <button
              type="button"
              onClick={onClose}
              title="Закрыть [Esc]"
              className="rounded-lg p-1.5 transition-all hover:opacity-75 active:scale-95"
              style={{ backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)' }}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="mt-4 space-y-3.5 text-sm" style={{ lineHeight: 1.6 }}>
          {/* Russian Translation of Footnote */}
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wider opacity-50" style={{ color: 'var(--accent)' }}>
              Перевод
            </div>
            <p className="mt-1 font-medium" style={{ color: 'var(--text-primary)' }}>
              {footnote.textRu}
            </p>
          </div>

          {/* Original English Citation */}
          <div className="rounded-xl border p-3" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-subtle)' }}>
            <div className="text-[11px] font-semibold uppercase tracking-wider opacity-50" style={{ color: 'var(--text-secondary)' }}>
              Оригинал (English citation)
            </div>
            <p className="mt-1 font-serif text-xs italic" style={{ color: 'var(--text-secondary)' }}>
              {footnote.textEn}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
