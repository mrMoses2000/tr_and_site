import { useState, useEffect, useMemo, useRef, type FC } from 'react';
import { Search, X, ArrowRight, CornerDownLeft } from 'lucide-react';
import { createDebouncedSearchExecutor, type SearchMatchV2 } from '../domain/search/searchEngineV2';
import type { PageData } from '../domain/types';
import type { ReaderLocationV2 } from '../domain/storage/storageV2';

interface SearchDialogProps {
  isOpen: boolean;
  onClose: () => void;
  pages: PageData[];
  onSelectLocation?: (location: Partial<ReaderLocationV2>) => void;
  onSelectPage?: (page: number, blockId?: string) => void;
}

export const SearchDialog: FC<SearchDialogProps> = ({
  isOpen,
  onClose,
  pages,
  onSelectLocation,
  onSelectPage,
}) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchMatchV2[]>([]);
  const [totalMatches, setTotalMatches] = useState(0);
  const [isTruncated, setIsTruncated] = useState(false);
  const [searchState, setSearchState] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [searchError, setSearchError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const searchExecutor = useMemo(() => createDebouncedSearchExecutor(pages, 200), [pages]);

  useEffect(() => {
    if (isOpen) {
      inputRef.current?.focus();
    } else {
      setQuery('');
      setResults([]);
      setTotalMatches(0);
      setIsTruncated(false);
      setSearchState('idle');
      setSearchError(null);
    }
  }, [isOpen]);

  useEffect(() => () => searchExecutor.cancel(), [searchExecutor]);

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed || trimmed.length < 2) {
      setResults([]);
      setTotalMatches(0);
      setIsTruncated(false);
      setSearchState('idle');
      setSearchError(null);
      return;
    }

    let active = true;
    setSearchState('loading');
    setSearchError(null);
    void searchExecutor.search(trimmed, { maxResults: 50, snippetRadius: 50 })
      .then((searchOutput) => {
        if (!active) return;
        setResults(searchOutput.matches);
        setTotalMatches(searchOutput.totalMatches);
        setIsTruncated(searchOutput.truncated);
        setSearchState('success');
      })
      .catch((error: unknown) => {
        if (!active || error instanceof Error && /cancelled/i.test(error.message)) return;
        setResults([]);
        setTotalMatches(0);
        setIsTruncated(false);
        setSearchError(error instanceof Error ? error.message : String(error));
        setSearchState('error');
      });

    return () => {
      active = false;
      searchExecutor.cancel();
    };
  }, [query, searchExecutor]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Поиск по книге"
      className="fixed inset-0 z-50 flex items-start justify-center p-3 pt-12 sm:p-6 sm:pt-20 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        className="flex max-h-[80vh] w-full max-w-2xl flex-col rounded-2xl border shadow-2xl transition-all"
        style={{
          backgroundColor: 'var(--bg-card)',
          borderColor: 'var(--border-strong)',
          color: 'var(--text-primary)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input Bar */}
        <div className="flex h-14 items-center border-b px-4" style={{ borderColor: 'var(--border-subtle)' }}>
          <Search className="h-5 w-5 shrink-0 opacity-40" />
          <input
            ref={inputRef}
            aria-label="Поиск по тексту книги и сноскам"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Поиск по тексту книги и сноскам..."
            className="flex-1 bg-transparent px-3 text-sm outline-hidden"
            style={{ color: 'var(--text-primary)' }}
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery('')}
              className="mr-2 rounded p-1 opacity-50 hover:opacity-100"
            >
              <X className="h-4 w-4" />
            </button>
          )}
          <kbd className="hidden rounded px-1.5 py-0.5 text-[10px] font-mono opacity-50 border sm:inline"
            style={{ borderColor: 'var(--border-subtle)' }}
          >
            Esc
          </kbd>
        </div>

        {/* Results List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {searchState === 'loading' && (
            <div className="py-10 text-center text-xs opacity-60" role="status">Поиск…</div>
          )}

          {searchState === 'error' && (
            <div className="py-10 text-center text-xs text-red-600" role="alert">
              Не удалось выполнить поиск: {searchError}
            </div>
          )}

          {searchState === 'success' && query.trim().length >= 2 && results.length === 0 && (
            <div className="py-12 text-center text-xs opacity-60" data-search-empty="true">
              Ничего не найдено по запросу «{query}»
            </div>
          )}

          {query.trim().length < 2 && (
            <div className="py-10 text-center text-xs opacity-50">
              Введите не менее 2 символов для поиска по всем {pages.length} страницам книги и сноскам.
            </div>
          )}

          {results.map((match, idx) => (
            <button
              key={`${match.pageNumber}-${match.paragraphId}-${idx}`}
              type="button"
              onClick={() => {
                const target: Partial<ReaderLocationV2> = {
                  pageNumber: match.pageNumber,
                  blockId: match.paragraphId,
                  footnoteId: match.footnoteId,
                };
                if (onSelectLocation) onSelectLocation(target);
                else onSelectPage?.(match.pageNumber, match.paragraphId);
                onClose();
              }}
              className="group flex w-full flex-col rounded-xl border p-3 text-left transition-all hover:ring-1 cursor-pointer"
              style={{
                backgroundColor: 'var(--bg-secondary)',
                borderColor: 'var(--border-subtle)',
              }}
            >
              <div className="flex items-center justify-between text-xs pb-1.5 border-b border-opacity-30" style={{ borderColor: 'var(--border-subtle)' }}>
                <div className="flex items-center space-x-2">
                  <span
                    className="rounded-md px-1.5 py-0.5 font-mono text-[10px] font-bold"
                    style={{ backgroundColor: 'var(--accent-soft)', color: 'var(--accent)' }}
                  >
                    Стр. {match.pageNumber}
                  </span>
                  <span
                    className="rounded px-1 text-[10px] uppercase font-bold"
                    style={{
                      backgroundColor: match.language === 'ru' ? 'rgba(59, 130, 246, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                      color: match.language === 'ru' ? '#2563eb' : '#059669',
                    }}
                  >
                    {match.language === 'ru' ? 'Русский' : 'Original EN'}
                  </span>
                  {match.targetType === 'footnote' && (
                    <span
                      className="rounded px-1 text-[10px] font-semibold"
                      style={{ backgroundColor: 'var(--accent-soft)', color: 'var(--accent)' }}
                    >
                      Сноска {match.footnoteId}
                    </span>
                  )}
                </div>

                <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity text-[11px]" style={{ color: 'var(--accent)' }}>
                  <span>Перейти</span>
                  <ArrowRight className="h-3 w-3" />
                </div>
              </div>

              <div className="pt-2 text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                <span>{match.snippetPrefix}</span>
                <mark
                  className="rounded px-1 font-semibold"
                  style={{ backgroundColor: 'var(--accent-soft)', color: 'var(--accent)' }}
                >
                  {match.snippetMatch}
                </mark>
                <span>{match.snippetSuffix}</span>
              </div>
            </button>
          ))}
        </div>

        {/* Footer info */}
        {results.length > 0 && (
          <div className="flex items-center justify-between border-t px-4 py-2.5 text-[11px] opacity-60" style={{ borderColor: 'var(--border-subtle)' }}>
            <span>
              Найдено совпадений: {totalMatches}
              {isTruncated && ` (показаны первые ${results.length})`}
            </span>
            <div className="flex items-center space-x-1">
              <CornerDownLeft className="h-3 w-3" />
              <span>нажмите на результат для перехода</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
