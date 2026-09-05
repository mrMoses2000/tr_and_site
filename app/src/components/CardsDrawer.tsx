import { useState, useMemo, type FC } from 'react';
import {
  X,
  Search,
  Download,
  Copy,
  Trash2,
  Edit3,
  ExternalLink,
  BookMarked,
  Check,
  Bookmark,
  Quote,
  Lightbulb,
  PenTool,
  Sparkles,
  HelpCircle,
  FileText,
} from 'lucide-react';
import type { ResearchCard, CardTag } from '../domain/types';
import {
  CARD_TAG_LABELS,
  COLOR_CLASSES,
  filterResearchCards,
  formatAcademicCitation,
  exportCardsToMarkdown,
} from '../domain/cards';

interface CardsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  cards: ResearchCard[];
  currentPage: number;
  onGoToPage: (page: number) => void;
  onEditCard: (card: ResearchCard) => void;
  onDeleteCard: (id: string) => void;
}

const TAG_ICONS: Record<CardTag, typeof Bookmark> = {
  thesis: Bookmark,
  quote: Quote,
  thought: Lightbulb,
  'for-paper': PenTool,
  theology: Sparkles,
  question: HelpCircle,
};

export const CardsDrawer: FC<CardsDrawerProps> = ({
  isOpen,
  onClose,
  cards,
  currentPage,
  onGoToPage,
  onEditCard,
  onDeleteCard,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTag, setSelectedTag] = useState<CardTag | 'all'>('all');
  const [pageFilter, setPageFilter] = useState<'all' | 'current'>('all');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [copiedAll, setCopiedAll] = useState(false);

  const filteredCards = useMemo(() => {
    return filterResearchCards(cards, {
      query: searchQuery,
      tag: selectedTag,
      pageNumber: pageFilter === 'current' ? currentPage : 'all',
    });
  }, [cards, searchQuery, selectedTag, pageFilter, currentPage]);

  const handleCopyCitation = (card: ResearchCard) => {
    const citation = formatAcademicCitation(card);
    navigator.clipboard.writeText(citation);
    setCopiedId(card.id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleExportMarkdown = () => {
    const md = exportCardsToMarkdown(filteredCards.length > 0 ? filteredCards : cards);
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `schreiner-research-cards-${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleCopyAllMarkdown = () => {
    const md = exportCardsToMarkdown(filteredCards.length > 0 ? filteredCards : cards);
    navigator.clipboard.writeText(md);
    setCopiedAll(true);
    setTimeout(() => setCopiedAll(false), 2000);
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-stretch sm:justify-end bg-black/50 backdrop-blur-xs transition-opacity duration-200"
      onClick={onClose}
    >
      <div
        className="relative flex w-full sm:max-w-xl max-h-[88dvh] sm:h-full sm:max-h-full flex-col rounded-t-3xl sm:rounded-none border-t sm:border-t-0 sm:border-l shadow-2xl transition-all"
        style={{
          backgroundColor: 'var(--bg-primary)',
          borderColor: 'var(--border-subtle)',
          color: 'var(--text-primary)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Drag handle on mobile */}
        <div className="sheet-handle sm:hidden" />

        {/* Drawer Header */}
        <div className="flex items-center justify-between border-b p-5" style={{ borderColor: 'var(--border-subtle)' }}>
          <div className="flex items-center space-x-2.5">
            <div className="rounded-xl p-2" style={{ backgroundColor: 'var(--accent-soft)', color: 'var(--accent)' }}>
              <BookMarked className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-lg font-bold">Карточки мыслей и цитат</h2>
                <span
                  className="rounded-full px-2 py-0.5 text-xs font-semibold"
                  style={{ backgroundColor: 'var(--accent-soft)', color: 'var(--accent)' }}
                >
                  {cards.length}
                </span>
              </div>
              <p className="text-xs opacity-60">
                Картотека выписок и идей для научных статей и рефератов
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

        {/* Toolbar & Filters */}
        <div className="border-b p-4 space-y-3" style={{ borderColor: 'var(--border-subtle)', backgroundColor: 'var(--bg-secondary)' }}>
          {/* Search bar */}
          <div className="relative">
            <Search className="absolute left-3 top-2.5 h-4 w-4 opacity-40" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Поиск по цитатам, мыслям и заметкам..."
              className="w-full rounded-xl border py-2 pl-9 pr-3 text-xs outline-none transition-colors"
              style={{
                backgroundColor: 'var(--bg-primary)',
                borderColor: 'var(--border-subtle)',
                color: 'var(--text-primary)',
              }}
            />
          </div>

          {/* Tag filters */}
          <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 text-xs">
            <button
              type="button"
              onClick={() => setSelectedTag('all')}
              className={`px-2.5 py-1 rounded-lg font-medium transition-all shrink-0 cursor-pointer border ${
                selectedTag === 'all' ? 'ring-1' : 'opacity-60 hover:opacity-100'
              }`}
              style={{
                borderColor: selectedTag === 'all' ? 'var(--accent)' : 'var(--border-subtle)',
                backgroundColor: selectedTag === 'all' ? 'var(--accent-soft)' : 'transparent',
                color: selectedTag === 'all' ? 'var(--accent)' : 'var(--text-primary)',
              }}
            >
              Все ({cards.length})
            </button>
            {(Object.keys(CARD_TAG_LABELS) as CardTag[]).map((t) => {
              const count = cards.filter(c => c.tag === t).length;
              if (count === 0 && selectedTag !== t) return null;
              const isSelected = selectedTag === t;
              return (
                <button
                  key={t}
                  type="button"
                  onClick={() => setSelectedTag(t)}
                  className={`px-2.5 py-1 rounded-lg font-medium transition-all shrink-0 cursor-pointer border ${
                    isSelected ? 'ring-1' : 'opacity-60 hover:opacity-100'
                  }`}
                  style={{
                    borderColor: isSelected ? 'var(--accent)' : 'var(--border-subtle)',
                    backgroundColor: isSelected ? 'var(--accent-soft)' : 'transparent',
                    color: isSelected ? 'var(--accent)' : 'var(--text-primary)',
                  }}
                >
                  {CARD_TAG_LABELS[t].label} ({count})
                </button>
              );
            })}
          </div>

          {/* Page scope & Export action bar */}
          <div className="flex items-center justify-between text-xs pt-1">
            <div className="flex items-center space-x-1">
              <button
                type="button"
                onClick={() => setPageFilter('all')}
                className={`px-2 py-0.5 rounded cursor-pointer ${pageFilter === 'all' ? 'font-semibold' : 'opacity-50'}`}
                style={{ backgroundColor: pageFilter === 'all' ? 'var(--bg-card)' : 'transparent' }}
              >
                Все страницы
              </button>
              <span>•</span>
              <button
                type="button"
                onClick={() => setPageFilter('current')}
                className={`px-2 py-0.5 rounded cursor-pointer ${pageFilter === 'current' ? 'font-semibold' : 'opacity-50'}`}
                style={{ backgroundColor: pageFilter === 'current' ? 'var(--bg-card)' : 'transparent' }}
              >
                Только стр. {currentPage}
              </button>
            </div>

            {/* Export buttons */}
            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={handleCopyAllMarkdown}
                title="Скопировать все карточки в формате Markdown"
                className="flex items-center space-x-1 rounded-lg px-2 py-1 text-[11px] font-medium transition-all hover:opacity-80 active:scale-95 cursor-pointer border"
                style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}
              >
                {copiedAll ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
                <span>{copiedAll ? 'Скопировано!' : 'Копировать'}</span>
              </button>
              <button
                type="button"
                onClick={handleExportMarkdown}
                title="Скачать карточки файлом Markdown (.md)"
                className="flex items-center space-x-1 rounded-lg px-2 py-1 text-[11px] font-semibold transition-all hover:opacity-90 active:scale-95 cursor-pointer shadow-xs"
                style={{ backgroundColor: 'var(--accent)', color: 'white' }}
              >
                <Download className="h-3 w-3" />
                <span>Экспорт .md</span>
              </button>
            </div>
          </div>
        </div>

        {/* Cards List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {filteredCards.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center px-4">
              <div
                className="rounded-2xl p-4 mb-3"
                style={{ backgroundColor: 'var(--accent-soft)', color: 'var(--accent)' }}
              >
                <FileText className="h-8 w-8" />
              </div>
              <h3 className="text-sm font-bold">
                {cards.length === 0 ? 'Картотека пока пуста' : 'Ничего не найдено'}
              </h3>
              <p className="mt-1 text-xs max-w-sm opacity-60 leading-relaxed">
                {cards.length === 0
                  ? 'Выделите фрагмент текста в ридере мышкой или нажмите «+ Карточка» у любого абзаца, чтобы зафиксировать цитату и свои размышления для будущих статей.'
                  : 'Попробуйте изменить поисковый запрос или выбрать другую категорию карточек.'}
              </p>
            </div>
          ) : (
            filteredCards.map((card) => {
              const TagIcon = TAG_ICONS[card.tag] || Bookmark;
              const colorInfo = COLOR_CLASSES[card.color] || COLOR_CLASSES.amber;

              return (
                <div
                  key={card.id}
                  className="group relative rounded-xl border p-4 shadow-xs transition-all hover:shadow-md"
                  style={{
                    backgroundColor: 'var(--bg-secondary)',
                    borderColor: 'var(--border-subtle)',
                  }}
                >
                  {/* Top bar of Card */}
                  <div className="flex items-center justify-between pb-2.5 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                    <div className="flex items-center space-x-2">
                      <span
                        className={`inline-flex items-center space-x-1 rounded-md px-2 py-0.5 text-[11px] font-semibold ${colorInfo.bg} ${colorInfo.text}`}
                      >
                        <TagIcon className="h-3 w-3" />
                        <span>{CARD_TAG_LABELS[card.tag]?.label || card.tag}</span>
                      </span>

                      <button
                        type="button"
                        onClick={() => {
                          onGoToPage(card.pageNumber);
                          onClose();
                        }}
                        className="inline-flex items-center space-x-1 rounded px-1.5 py-0.5 text-[11px] opacity-60 hover:opacity-100 transition-colors cursor-pointer"
                        title="Перейти на страницу"
                      >
                        <span className="font-mono">Стр. {card.pageNumber}</span>
                        <ExternalLink className="h-2.5 w-2.5" />
                      </button>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center space-x-1 opacity-80 group-hover:opacity-100 transition-opacity">
                      <button
                        type="button"
                        onClick={() => handleCopyCitation(card)}
                        title="Скопировать библиографическую ссылку"
                        className="rounded p-1 hover:bg-black/10 dark:hover:bg-white/10 transition-colors cursor-pointer"
                      >
                        {copiedId === card.id ? (
                          <Check className="h-3.5 w-3.5 text-emerald-500" />
                        ) : (
                          <Copy className="h-3.5 w-3.5" />
                        )}
                      </button>
                      <button
                        type="button"
                        onClick={() => onEditCard(card)}
                        title="Редактировать карточку"
                        className="rounded p-1 hover:bg-black/10 dark:hover:bg-white/10 transition-colors cursor-pointer"
                      >
                        <Edit3 className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => onDeleteCard(card.id)}
                        title="Удалить карточку"
                        className="rounded p-1 text-rose-500 hover:bg-rose-500/10 transition-colors cursor-pointer"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Quote fragment */}
                  {card.quote && (
                    <div className="mt-3 relative pl-3 border-l-2 font-serif text-xs italic leading-relaxed opacity-90"
                      style={{ borderColor: 'var(--accent)' }}
                    >
                      «{card.quote}»
                    </div>
                  )}

                  {/* User's commentary / note */}
                  {card.note && (
                    <div className="mt-3 rounded-lg p-2.5 text-xs leading-relaxed"
                      style={{ backgroundColor: 'var(--bg-primary)', color: 'var(--text-primary)' }}
                    >
                      <span className="font-bold text-[10px] uppercase tracking-wider block mb-1 opacity-50">
                        Мысль исследователя:
                      </span>
                      {card.note}
                    </div>
                  )}

                  {/* Date footer */}
                  <div className="mt-2.5 flex items-center justify-between text-[10px] opacity-40">
                    <span>
                      {new Date(card.createdAt).toLocaleDateString('ru-RU', {
                        day: 'numeric',
                        month: 'short',
                        year: 'numeric',
                      })}
                    </span>
                    <span className="font-mono">{card.quoteLanguage === 'ru' ? 'RU перевод' : 'EN оригинал'}</span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
