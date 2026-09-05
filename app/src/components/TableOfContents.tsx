import { useState, type FC } from 'react';
import { X, BookOpen, Bookmark, ChevronRight, Search } from 'lucide-react';
import type { TocItem } from '../domain/types';

interface TableOfContentsProps {
  isOpen: boolean;
  onClose: () => void;
  toc: TocItem[];
  currentPage: number;
  bookmarks: number[];
  onSelectPage: (page: number) => void;
  bookTitleRu: string;
  authorRu: string;
  availableBooks?: Array<{
    slug: string;
    title: string;
    titleRu: string;
    author: string;
    authorRu: string;
    totalPages: number;
  }>;
  currentBookSlug?: string;
  onSelectBook?: (slug: string) => void;
}

export const TableOfContents: FC<TableOfContentsProps> = ({
  isOpen,
  onClose,
  toc,
  currentPage,
  bookmarks,
  onSelectPage,
  bookTitleRu,
  authorRu,
  availableBooks = [],
  currentBookSlug,
  onSelectBook,
}) => {
  const [filter, setFilter] = useState('');

  if (!isOpen) return null;

  const validToc = (toc || [])
    .filter(item => item && typeof item === 'object' && item.pageNumber > 0)
    .map(item => {
      const titleRu = item.titleRu || (item as any).title || item.titleEn || 'Раздел';
      const cleanTitleRu = titleRu.replace(/\.pdf$/i, '').replace(/^_+/, '').trim();
      const titleEn = item.titleEn && item.titleEn !== titleRu ? item.titleEn.replace(/\.pdf$/i, '').trim() : '';
      return {
        ...item,
        titleRu: cleanTitleRu,
        titleEn,
      };
    });

  const filteredItems = validToc.filter(item =>
    item.titleRu.toLowerCase().includes(filter.toLowerCase()) ||
    (item.titleEn && item.titleEn.toLowerCase().includes(filter.toLowerCase())) ||
    item.pageNumber.toString().includes(filter)
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-stretch bg-black/50 backdrop-blur-xs animate-in fade-in duration-200"
      onClick={onClose}
    >
      <aside
        className="flex w-full sm:max-w-md max-h-[88dvh] sm:h-full sm:max-h-full flex-col rounded-t-3xl sm:rounded-none border-t sm:border-t-0 sm:border-r shadow-2xl transition-all"
        style={{
          backgroundColor: 'var(--bg-primary)',
          borderColor: 'var(--border-strong)',
          color: 'var(--text-primary)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Drag handle on mobile */}
        <div className="sheet-handle sm:hidden" />

        {/* Header */}
        <div className="flex h-14 items-center justify-between border-b px-5" style={{ borderColor: 'var(--border-subtle)' }}>
          <div className="flex items-center space-x-2.5">
            <BookOpen className="h-5 w-5" style={{ color: 'var(--accent)' }} />
            <h2 className="text-sm font-bold tracking-tight">Оглавление</h2>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 transition-all hover:opacity-75 active:scale-95"
            style={{ backgroundColor: 'var(--bg-secondary)' }}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Book Info Summary */}
        <div className="border-b p-4" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-subtle)' }}>
          <div className="text-[11px] font-semibold uppercase tracking-wider opacity-60" style={{ color: 'var(--text-secondary)' }}>
            {authorRu}
          </div>
          <div className="text-sm font-bold mt-0.5 leading-snug" style={{ color: 'var(--text-primary)' }}>
            {bookTitleRu}
          </div>
        </div>

        {/* Multi-Book Library Selector */}
        {availableBooks.length > 1 && (
          <div className="border-b px-4 py-2.5" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-subtle)' }}>
            <label className="text-[10px] font-bold uppercase tracking-wider opacity-60 block mb-1.5" style={{ color: 'var(--text-secondary)' }}>
              Книга из каталога:
            </label>
            <select
              value={currentBookSlug}
              onChange={(e) => onSelectBook?.(e.target.value)}
              className="w-full rounded-lg px-2.5 py-1.5 text-xs font-medium outline-hidden transition-all"
              style={{
                backgroundColor: 'var(--bg-secondary)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              {availableBooks.map((b) => (
                <option key={b.slug} value={b.slug}>
                  {b.titleRu} ({b.authorRu})
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Search filter input */}
        <div className="p-3 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
          <div className="relative">
            <Search className="absolute left-3 top-2.5 h-4 w-4 opacity-40" />
            <input
              type="text"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Фильтр по разделам или номеру..."
              className="w-full rounded-lg py-1.5 pl-9 pr-3 text-xs outline-hidden transition-all"
              style={{
                backgroundColor: 'var(--bg-card)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-subtle)',
              }}
            />
          </div>
        </div>

        {/* Chapters list */}
        <nav className="flex-1 overflow-y-auto p-3 space-y-1">
          {filteredItems.map((item, idx) => {
            const isExact = currentPage === item.pageNumber;
            const isBookmarked = bookmarks.includes(item.pageNumber);

            return (
              <button
                key={`toc-${item.pageNumber}-${idx}`}
                type="button"
                onClick={() => {
                  onSelectPage(item.pageNumber);
                  onClose();
                }}
                className={`group flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left transition-all duration-150 ${
                  isExact ? 'shadow-xs font-semibold' : 'hover:opacity-90'
                }`}
                style={{
                  backgroundColor: isExact ? 'var(--accent-soft)' : 'transparent',
                  border: isExact ? '1px solid var(--accent)' : '1px solid transparent',
                  paddingLeft: item.level === 2 ? '1.5rem' : '0.75rem',
                }}
              >
                <div className="flex-1 pr-2">
                  <div className="flex items-center space-x-1.5">
                    <span
                      className="text-xs"
                      style={{ color: isExact ? 'var(--accent)' : 'var(--text-primary)' }}
                    >
                      {item.titleRu}
                    </span>
                    {isBookmarked && (
                      <Bookmark className="h-3 w-3 fill-current text-amber-500" />
                    )}
                  </div>
                  {item.titleEn && (
                    <div className="text-[11px] opacity-60 font-serif italic mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                      {item.titleEn}
                    </div>
                  )}
                </div>

                <div className="flex items-center space-x-1.5 shrink-0">
                  <span
                    className="rounded-md px-2 py-0.5 text-[11px] font-mono font-semibold"
                    style={{
                      backgroundColor: isExact ? 'var(--accent)' : 'var(--bg-card)',
                      color: isExact ? '#ffffff' : 'var(--text-secondary)',
                      border: '1px solid var(--border-subtle)',
                    }}
                  >
                    стр. {item.pageNumber}
                  </span>
                  <ChevronRight className="h-3.5 w-3.5 opacity-40 group-hover:opacity-100 transition-opacity" />
                </div>
              </button>
            );
          })}

          {filteredItems.length === 0 && (
            <div className="py-8 text-center text-xs opacity-50">
              Разделы не найдены
            </div>
          )}
        </nav>

        {/* Bookmarks Quick Jump Footer */}
        {bookmarks.length > 0 && (
          <div className="border-t p-3" style={{ borderColor: 'var(--border-subtle)', backgroundColor: 'var(--bg-secondary)' }}>
            <div className="flex items-center space-x-1 text-xs font-semibold" style={{ color: 'var(--accent)' }}>
              <Bookmark className="h-3.5 w-3.5 fill-current" />
              <span>Ваши закладки ({bookmarks.length}):</span>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {bookmarks.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => {
                    onSelectPage(p);
                    onClose();
                  }}
                  className="rounded-md px-2 py-1 text-xs font-mono font-medium transition-all hover:opacity-80"
                  style={{
                    backgroundColor: 'var(--bg-card)',
                    color: 'var(--text-primary)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  Стр. {p}
                </button>
              ))}
            </div>
          </div>
        )}
      </aside>
    </div>
  );
};
