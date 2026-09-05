import { useState, useEffect, type FC, type FormEvent } from 'react';
import { X, Quote, Sparkles, Check, Bookmark, Lightbulb, PenTool, HelpCircle } from 'lucide-react';
import type { ResearchCard, CardTag, HighlightColor } from '../domain/types';
import { CARD_TAG_LABELS, type CreateCardInput } from '../domain/cards';

interface CardModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: CreateCardInput) => void;
  onUpdate?: (id: string, data: Partial<ResearchCard>) => void;
  initialData?: {
    pageNumber: number;
    paragraphId?: string;
    quote: string;
    quoteLanguage: 'ru' | 'en';
  };
  cardToEdit?: ResearchCard;
}

const TAG_ICONS: Record<CardTag, typeof Bookmark> = {
  thesis: Bookmark,
  quote: Quote,
  thought: Lightbulb,
  'for-paper': PenTool,
  theology: Sparkles,
  question: HelpCircle,
};

const COLOR_OPTIONS: { color: HighlightColor; name: string; hex: string }[] = [
  { color: 'amber', name: 'Золотой / Янтарный', hex: '#f59e0b' },
  { color: 'emerald', name: 'Изумрудный', hex: '#10b981' },
  { color: 'blue', name: 'Небесный', hex: '#0ea5e9' },
  { color: 'purple', name: 'Фиолетовый', hex: '#a855f7' },
];

export const CardModal: FC<CardModalProps> = ({
  isOpen,
  onClose,
  onSave,
  onUpdate,
  initialData,
  cardToEdit,
}) => {
  const [quote, setQuote] = useState('');
  const [note, setNote] = useState('');
  const [tag, setTag] = useState<CardTag>('thought');
  const [color, setColor] = useState<HighlightColor>('amber');
  const [quoteLanguage, setQuoteLanguage] = useState<'ru' | 'en'>('ru');
  const pageNumber = cardToEdit?.pageNumber ?? initialData?.pageNumber ?? 867;

  useEffect(() => {
    if (cardToEdit) {
      setQuote(cardToEdit.quote);
      setNote(cardToEdit.note);
      setTag(cardToEdit.tag);
      setColor(cardToEdit.color);
      setQuoteLanguage(cardToEdit.quoteLanguage);
    } else if (initialData) {
      setQuote(initialData.quote);
      setNote('');
      setTag('thought');
      setColor('amber');
      setQuoteLanguage(initialData.quoteLanguage);
    }
  }, [cardToEdit, initialData, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!quote.trim() && !note.trim()) return;

    if (cardToEdit && onUpdate) {
      onUpdate(cardToEdit.id, {
        quote: quote.trim(),
        note: note.trim(),
        tag,
        color,
        quoteLanguage,
      });
    } else {
      onSave({
        pageNumber,
        paragraphId: initialData?.paragraphId,
        quote: quote.trim(),
        quoteLanguage,
        note: note.trim(),
        tag,
        color,
      });
    }
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs transition-opacity duration-200"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-xl rounded-2xl border p-6 shadow-2xl transition-transform sm:p-7 max-h-[90vh] flex flex-col"
        style={{
          backgroundColor: 'var(--bg-primary)',
          borderColor: 'var(--border-strong)',
          color: 'var(--text-primary)',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
          <div className="flex items-center space-x-2">
            <div className="rounded-lg p-2" style={{ backgroundColor: 'var(--accent-soft)', color: 'var(--accent)' }}>
              <Quote className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold">
                {cardToEdit ? 'Редактировать карточку мысли' : 'Создать карточку мысли'}
              </h2>
              <p className="text-xs opacity-60">
                Томас Шрайнер • Богословие Нового Завета • Стр. {pageNumber}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 opacity-60 hover:opacity-100 transition-colors cursor-pointer"
            style={{ backgroundColor: 'var(--bg-secondary)' }}
            aria-label="Закрыть"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto pt-4 space-y-4 pr-1">
          {/* Tag Selector */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider mb-2 opacity-70">
              Тип карточки:
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {(Object.keys(CARD_TAG_LABELS) as CardTag[]).map((t) => {
                const isSelected = tag === t;
                const IconComponent = TAG_ICONS[t];
                return (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setTag(t)}
                    className={`flex items-center space-x-2 rounded-lg px-2.5 py-2 text-xs font-medium transition-all text-left cursor-pointer border ${
                      isSelected ? 'ring-2' : 'opacity-70 hover:opacity-100'
                    }`}
                    style={{
                      borderColor: isSelected ? 'var(--accent)' : 'var(--border-subtle)',
                      backgroundColor: isSelected ? 'var(--accent-soft)' : 'var(--bg-secondary)',
                      color: isSelected ? 'var(--accent)' : 'var(--text-primary)',
                      outline: 'none',
                    }}
                  >
                    <IconComponent className="h-3.5 w-3.5 shrink-0" />
                    <span className="truncate">{CARD_TAG_LABELS[t].label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Color Highlight Picker */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider mb-2 opacity-70">
              Цветовой акцент:
            </label>
            <div className="flex items-center space-x-3">
              {COLOR_OPTIONS.map((c) => {
                const isSelected = color === c.color;
                return (
                  <button
                    key={c.color}
                    type="button"
                    onClick={() => setColor(c.color)}
                    title={c.name}
                    className={`flex h-7 w-7 items-center justify-center rounded-full transition-transform cursor-pointer border-2 ${
                      isSelected ? 'scale-110 shadow-sm' : 'opacity-70 hover:opacity-100'
                    }`}
                    style={{
                      backgroundColor: c.hex,
                      borderColor: isSelected ? 'var(--text-primary)' : 'transparent',
                    }}
                  >
                    {isSelected && <Check className="h-4 w-4 text-white" />}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Quote Section */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold uppercase tracking-wider opacity-70">
                Цитата из текста (источник):
              </label>
              <div className="flex items-center space-x-1 text-[11px]">
                <button
                  type="button"
                  onClick={() => setQuoteLanguage('ru')}
                  className={`px-1.5 py-0.5 rounded cursor-pointer ${quoteLanguage === 'ru' ? 'font-bold' : 'opacity-50'}`}
                  style={{ backgroundColor: quoteLanguage === 'ru' ? 'var(--accent-soft)' : 'transparent', color: 'var(--accent)' }}
                >
                  Русский
                </button>
                <span>/</span>
                <button
                  type="button"
                  onClick={() => setQuoteLanguage('en')}
                  className={`px-1.5 py-0.5 rounded cursor-pointer ${quoteLanguage === 'en' ? 'font-bold' : 'opacity-50'}`}
                  style={{ backgroundColor: quoteLanguage === 'en' ? 'var(--accent-soft)' : 'transparent', color: 'var(--accent)' }}
                >
                  English
                </button>
              </div>
            </div>
            <textarea
              rows={3}
              value={quote}
              onChange={e => setQuote(e.target.value)}
              placeholder="Выделенная цитата из книги..."
              className="w-full rounded-xl border p-3 text-sm font-serif italic outline-none transition-colors"
              style={{
                backgroundColor: 'var(--bg-secondary)',
                borderColor: 'var(--border-subtle)',
                color: 'var(--text-primary)',
              }}
            />
          </div>

          {/* User's Note / Thought Section */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5 opacity-70">
              Ваша мысль, аргумент или тезис для научной работы:
            </label>
            <textarea
              rows={4}
              autoFocus
              value={note}
              onChange={e => setNote(e.target.value)}
              placeholder="Запишите ваши мысли: как эта мысль соотносится с вашей работой, вопросы к автору, контраргументы или богословские выводы..."
              className="w-full rounded-xl border p-3 text-sm outline-none transition-colors"
              style={{
                backgroundColor: 'var(--bg-secondary)',
                borderColor: 'var(--border-subtle)',
                color: 'var(--text-primary)',
              }}
            />
          </div>

          {/* Footer Actions */}
          <div className="pt-3 border-t flex items-center justify-end space-x-3" style={{ borderColor: 'var(--border-subtle)' }}>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-sm font-medium transition-opacity hover:opacity-75 cursor-pointer"
              style={{ backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)' }}
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={!quote.trim() && !note.trim()}
              className="px-5 py-2 rounded-xl text-sm font-semibold transition-all hover:opacity-90 active:scale-95 disabled:opacity-40 cursor-pointer shadow-sm"
              style={{ backgroundColor: 'var(--accent)', color: 'white' }}
            >
              {cardToEdit ? 'Сохранить изменения' : 'Создать карточку'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
