import type { FC } from 'react';
import { ChevronLeft, ChevronRight, Clock } from 'lucide-react';
import type { ReadingProgress } from '../domain/types';

interface BottomBarProps {
  currentPage: number;
  minPage: number;
  maxPage: number;
  canGoPrev: boolean;
  canGoNext: boolean;
  progress: ReadingProgress;
  onPrevPage: () => void;
  onNextPage: () => void;
  onSelectPage: (page: number) => void;
}

export const BottomBar: FC<BottomBarProps> = ({
  currentPage,
  minPage,
  maxPage,
  canGoPrev,
  canGoNext,
  progress,
  onPrevPage,
  onNextPage,
  onSelectPage,
}) => {
  return (
    <footer
      className="sticky bottom-0 z-30 w-full border-t backdrop-blur-md transition-colors duration-200"
      style={{
        backgroundColor: 'var(--bg-primary)',
        borderColor: 'var(--border-subtle)',
      }}
    >
      <div className="mx-auto flex h-14 max-w-4xl items-center justify-between px-4 sm:px-6">
        {/* Previous Page Button */}
        <button
          type="button"
          onClick={onPrevPage}
          disabled={!canGoPrev}
          title="Предыдущая страница [← или K]"
          className={`flex items-center space-x-1.5 rounded-xl px-3 py-2 text-xs font-semibold transition-all ${
            canGoPrev ? 'hover:opacity-80 active:scale-95 cursor-pointer' : 'opacity-30 cursor-not-allowed'
          }`}
          style={{
            backgroundColor: 'var(--bg-secondary)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <ChevronLeft className="h-4 w-4" />
          <span className="hidden sm:inline">Назад</span>
          <kbd className="hidden rounded px-1 text-[10px] font-mono opacity-50 md:inline">K</kbd>
        </button>

        {/* Center: Interactive Scrubber Slider */}
        <div className="flex flex-1 max-w-md items-center space-x-3 px-3 sm:px-6">
          <input
            type="range"
            min={minPage}
            max={maxPage}
            step={1}
            value={currentPage}
            onChange={(e) => onSelectPage(parseInt(e.target.value, 10))}
            className="w-full accent-amber-600 cursor-pointer h-1.5 rounded-lg bg-black/10 dark:bg-white/10"
            title={`Перейти на страницу ${currentPage}`}
          />
          <div className="flex items-center space-x-1 shrink-0 text-xs font-mono opacity-75" style={{ color: 'var(--text-secondary)' }}>
            <span className="font-bold text-sm" style={{ color: 'var(--accent)' }}>{currentPage}</span>
            <span className="opacity-40">/</span>
            <span>{maxPage}</span>
          </div>
        </div>

        {/* Next Page Button */}
        <div className="flex items-center space-x-2">
          {progress.estimatedMinutesLeft > 0 && (
            <div className="hidden items-center space-x-1 text-[11px] opacity-60 md:flex" style={{ color: 'var(--text-secondary)' }}>
              <Clock className="h-3 w-3" />
              <span>~{progress.estimatedMinutesLeft} мин до конца</span>
            </div>
          )}

          <button
            type="button"
            onClick={onNextPage}
            disabled={!canGoNext}
            title="Следующая страница [→ или J]"
            className={`flex items-center space-x-1.5 rounded-xl px-3 py-2 text-xs font-semibold transition-all ${
              canGoNext ? 'hover:opacity-80 active:scale-95 cursor-pointer' : 'opacity-30 cursor-not-allowed'
            }`}
            style={{
              backgroundColor: 'var(--accent)',
              color: '#ffffff',
              boxShadow: canGoNext ? '0 2px 8px rgba(156, 66, 33, 0.25)' : 'none',
            }}
          >
            <span className="hidden sm:inline">Вперед</span>
            <kbd className="hidden rounded bg-white/20 px-1 text-[10px] font-mono md:inline">J</kbd>
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </footer>
  );
};
