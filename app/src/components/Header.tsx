import type { FC } from 'react';
import {
  BookOpen,
  Columns,
  FileText,
  Image as ImageIcon,
  Search,
  Sliders,
  Bookmark,
  BookMarked,
  List,
  Maximize2,
  Minimize2,
  Library,
} from 'lucide-react';
import type { ReaderSettings, ReaderMode, ReadingProgress } from '../domain/types';

interface HeaderProps {
  bookTitle: string;
  author: string;
  chapterTitle?: string;
  pageNumber: number;
  totalPages: number;
  progress: ReadingProgress;
  settings: ReaderSettings;
  isBookmarked: boolean;
  cardsCount?: number;
  isCardsOpen?: boolean;
  isFullscreen?: boolean;
  onBackToCatalog?: () => void;
  onToggleBookmark: () => void;
  onOpenToc: () => void;
  onOpenSearch: () => void;
  onOpenSettings: () => void;
  onToggleScan: () => void;
  onToggleCards?: () => void;
  onToggleFullscreen?: () => void;
  isScanOpen: boolean;
  onChangeMode: (mode: ReaderMode) => void;
}

export const Header: FC<HeaderProps> = ({
  author,
  chapterTitle,
  pageNumber,
  totalPages,
  progress,
  settings,
  isBookmarked,
  cardsCount = 0,
  isCardsOpen = false,
  onToggleBookmark,
  onOpenToc,
  onOpenSearch,
  onOpenSettings,
  onToggleScan,
  onToggleCards,
  isScanOpen,
  isFullscreen = false,
  onToggleFullscreen,
  onChangeMode,
  onBackToCatalog,
}) => {
  return (
    <header className="sticky top-0 z-30 w-full border-b backdrop-blur-md transition-colors duration-200"
      style={{
        backgroundColor: 'var(--bg-primary)',
        borderColor: 'var(--border-subtle)',
      }}
    >
      {/* Top Reading Progress Bar */}
      <div className="h-1 w-full overflow-hidden bg-opacity-30" style={{ backgroundColor: 'var(--progress-bg)' }}>
        <div
          className="h-full transition-all duration-300 ease-out"
          style={{
            width: `${progress.percent}%`,
            backgroundColor: 'var(--accent)',
          }}
        />
      </div>

      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-3 sm:px-6">
        {/* Left: Table of Contents & Title */}
        <div className="flex items-center space-x-2 sm:space-x-3">
          {onBackToCatalog && (
            <button
              type="button"
              onClick={onBackToCatalog}
              title="На главную в библиотеку"
              aria-label="В библиотеку"
              className="flex items-center space-x-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold transition-all hover:opacity-85 active:scale-95"
              style={{
                backgroundColor: 'var(--bg-secondary)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <Library className="h-4 w-4 opacity-75" />
              <span className="hidden sm:inline">Каталог</span>
            </button>
          )}

          <button
            type="button"
            onClick={onOpenToc}
            title="Содержание [T]"
            aria-label="Открыть оглавление"
            className="flex items-center space-x-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-all hover:opacity-80 active:scale-95"
            style={{
              backgroundColor: 'var(--bg-secondary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <List className="h-4 w-4" />
            <span className="hidden sm:inline">Оглавление</span>
            <kbd className="hidden rounded px-1 text-[10px] font-mono text-xs opacity-60 md:inline">T</kbd>
          </button>

          <div className="hidden flex-col md:flex">
            <span className="text-xs font-semibold uppercase tracking-wider opacity-70" style={{ color: 'var(--text-secondary)' }}>
              {author}
            </span>
            <span className="truncate text-xs font-medium" style={{ color: 'var(--text-primary)', maxWidth: '240px' }}>
              {chapterTitle || bookTitle || 'Чтение'}
            </span>
          </div>
        </div>

        {/* Center: Current Page Badge */}
        <div className="flex items-center space-x-2">
          <div
            className="flex items-center rounded-full px-3 py-0.5 text-xs font-medium tracking-tight shadow-xs"
            style={{
              backgroundColor: 'var(--bg-card)',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>Стр. {pageNumber}</span>
            <span className="mx-1.5 opacity-40">/</span>
            <span>{totalPages} стр.</span>
            <span className="ml-2 hidden rounded-sm px-1.5 py-0.2 text-[10px] font-semibold sm:inline"
              style={{ backgroundColor: 'var(--accent-soft)', color: 'var(--accent)' }}
            >
              {progress.percent}%
            </span>
          </div>

          <button
            type="button"
            onClick={onToggleBookmark}
            title={isBookmarked ? 'Удалить закладку' : 'Добавить закладку'}
            aria-label="Закладка"
            className="rounded-full p-1.5 transition-all hover:opacity-80 active:scale-90"
            style={{
              color: isBookmarked ? 'var(--accent)' : 'var(--text-muted)',
              backgroundColor: isBookmarked ? 'var(--accent-soft)' : 'transparent',
            }}
          >
            <Bookmark className={`h-4 w-4 ${isBookmarked ? 'fill-current' : ''}`} />
          </button>
        </div>

        {/* Right: Mode Switcher & Tools */}
        <div className="flex items-center space-x-1.5 sm:space-x-2">
          {/* Mode Segmented Controls */}
          <div
            className="flex items-center rounded-lg p-0.5"
            style={{
              backgroundColor: 'var(--bg-secondary)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <button
              type="button"
              onClick={() => onChangeMode('ru')}
              title="Только русский перевод"
              className={`flex items-center space-x-1 rounded-md px-2 py-1 text-xs font-medium transition-all ${
                settings.mode === 'ru' ? 'shadow-xs' : 'opacity-70 hover:opacity-100'
              }`}
              style={{
                backgroundColor: settings.mode === 'ru' ? 'var(--bg-card)' : 'transparent',
                color: settings.mode === 'ru' ? 'var(--accent)' : 'var(--text-secondary)',
              }}
            >
              <FileText className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Русский</span>
            </button>

            <button
              type="button"
              onClick={() => onChangeMode('bilingual')}
              title="Параллельный текст (RU + EN) [B]"
              className={`flex items-center space-x-1 rounded-md px-2 py-1 text-xs font-medium transition-all ${
                settings.mode === 'bilingual' ? 'shadow-xs' : 'opacity-70 hover:opacity-100'
              }`}
              style={{
                backgroundColor: settings.mode === 'bilingual' ? 'var(--bg-card)' : 'transparent',
                color: settings.mode === 'bilingual' ? 'var(--accent)' : 'var(--text-secondary)',
              }}
            >
              <Columns className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Параллельно</span>
            </button>

            <button
              type="button"
              onClick={() => onChangeMode('en')}
              title="English Original"
              className={`flex items-center space-x-1 rounded-md px-2 py-1 text-xs font-medium transition-all ${
                settings.mode === 'en' ? 'shadow-xs' : 'opacity-70 hover:opacity-100'
              }`}
              style={{
                backgroundColor: settings.mode === 'en' ? 'var(--bg-card)' : 'transparent',
                color: settings.mode === 'en' ? 'var(--accent)' : 'var(--text-secondary)',
              }}
            >
              <BookOpen className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Original</span>
            </button>
          </div>

          {/* Original Book Photo / Scan Trigger */}
          <button
            type="button"
            onClick={onToggleScan}
            title="Фото оригинала страницы [S]"
            aria-label="Показать скан оригинала"
            className={`flex items-center space-x-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-all active:scale-95 ${
              isScanOpen ? 'ring-2' : 'hover:opacity-80'
            }`}
            style={{
              backgroundColor: isScanOpen ? 'var(--accent-soft)' : 'var(--bg-secondary)',
              color: isScanOpen ? 'var(--accent)' : 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <ImageIcon className="h-4 w-4" />
            <span className="hidden lg:inline">Скан</span>
            <kbd className="hidden rounded px-1 text-[10px] font-mono opacity-60 md:inline">S</kbd>
          </button>

          {/* Research Thought Cards Trigger */}
          <button
            type="button"
            onClick={onToggleCards}
            title="Карточки мыслей и цитат [N]"
            aria-label="Карточки мыслей"
            className={`relative flex items-center space-x-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-all active:scale-95 cursor-pointer ${
              isCardsOpen ? 'ring-2' : 'hover:opacity-80'
            }`}
            style={{
              backgroundColor: isCardsOpen ? 'var(--accent-soft)' : 'var(--bg-secondary)',
              color: isCardsOpen ? 'var(--accent)' : 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <BookMarked className="h-4 w-4" />
            <span className="hidden lg:inline">Карточки</span>
            {cardsCount > 0 && (
              <span
                className="rounded-full px-1.5 py-0.2 text-[10px] font-bold text-white leading-none"
                style={{ backgroundColor: 'var(--accent)' }}
              >
                {cardsCount}
              </span>
            )}
            <kbd className="hidden rounded px-1 text-[10px] font-mono opacity-60 md:inline">N</kbd>
          </button>

          {/* Search Trigger */}
          <button
            type="button"
            onClick={onOpenSearch}
            title="Поиск [/]"
            aria-label="Поиск по книге"
            className="rounded-lg p-2 transition-all hover:opacity-80 active:scale-95"
            style={{
              backgroundColor: 'var(--bg-secondary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <Search className="h-4 w-4" />
          </button>

          {/* Settings Trigger */}
          <button
            type="button"
            onClick={onOpenSettings}
            title="Шрифт и оформление [F]"
            aria-label="Настройки шрифта и темы"
            className="rounded-lg p-2 transition-all hover:opacity-80 active:scale-95 cursor-pointer"
            style={{
              backgroundColor: 'var(--bg-secondary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <Sliders className="h-4 w-4" />
          </button>

          {/* Fullscreen / Zen Mode Trigger */}
          <button
            type="button"
            onClick={onToggleFullscreen}
            title={isFullscreen ? "Выйти из полноэкранного режима [Z]" : "Полноэкранный режим чтения без мишуры [Z]"}
            aria-label="Полноэкранный режим"
            className={`rounded-lg p-2 transition-all active:scale-95 cursor-pointer ${
              isFullscreen ? 'ring-2' : 'hover:opacity-80'
            }`}
            style={{
              backgroundColor: isFullscreen ? 'var(--accent-soft)' : 'var(--bg-secondary)',
              color: isFullscreen ? 'var(--accent)' : 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </header>
  );
};
