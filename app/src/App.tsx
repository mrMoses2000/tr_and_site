import { useState, useEffect, useCallback } from 'react';
import { useReader } from './domain/useReader';
import { Header } from './components/Header';
import { ReaderContent } from './components/ReaderContent';
import { ScanViewer } from './components/ScanViewer';
import { TableOfContents } from './components/TableOfContents';
import { SearchDialog } from './components/SearchDialog';
import { SettingsDialog } from './components/SettingsDialog';
import { FootnotePopup } from './components/FootnotePopup';
import { BottomBar } from './components/BottomBar';
import { CardModal } from './components/CardModal';
import { CardsDrawer } from './components/CardsDrawer';
import { FloatingSelectionToolbar } from './components/FloatingSelectionToolbar';
import { HomePage } from './components/HomePage';
import { HelpCircle, X, Keyboard, Minimize2, ChevronLeft, ChevronRight } from 'lucide-react';

export function App() {
  const {
    manifest,
    currentBookSlug,
    selectBook,
    availableBooks,
    currentPage,
    currentPageData,
    progress,
    settings,
    bookmarks,
    cards,
    activeFootnote,
    isTocOpen,
    isSearchOpen,
    isSettingsOpen,
    isScanOpen,
    isScanSplit,
    isCardsOpen,
    activeCardModal,
    hoveredParagraphId,
    canGoNext,
    canGoPrev,
    goToPage,
    nextPage,
    prevPage,
    toggleBookmark,
    addCard,
    updateCard,
    deleteCard,
    openCreateCard,
    openEditCard,
    closeCardModal,
    updateSettings,
    setActiveFootnote,
    setIsTocOpen,
    setIsSearchOpen,
    setIsSettingsOpen,
    setIsScanOpen,
    setIsScanSplit,
    setIsCardsOpen,
    setHoveredParagraphId,
  } = useReader();

  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Determine initial view from URL hash
  const getInitialView = (): 'home' | 'reader' => {
    if (typeof window !== 'undefined' && window.location.hash) {
      if (window.location.hash.startsWith('#book=') || window.location.hash.startsWith('#page=')) {
        return 'reader';
      }
    }
    return 'home';
  };

  const [currentView, setCurrentView] = useState<'home' | 'reader'>(getInitialView);

  // Sync hash changes with view state
  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash;
      if (hash.startsWith('#book=') || hash.startsWith('#page=')) {
        setCurrentView('reader');
      } else if (hash === '#catalog' || hash === '#home' || hash === '' || hash === '#') {
        setCurrentView('home');
      }
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const handleOpenBook = useCallback((slug: string, page?: number) => {
    selectBook(slug);
    if (page) {
      goToPage(page);
    }
    setCurrentView('reader');
    if (typeof window !== 'undefined') {
      window.location.hash = `book=${slug}&page=${page || 1}`;
    }
  }, [selectBook, goToPage]);

  const handleBackToCatalog = useCallback(() => {
    setCurrentView('home');
    if (typeof window !== 'undefined') {
      window.location.hash = 'catalog';
    }
  }, []);

  // Sync with native fullscreen state
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(Boolean(document.fullscreenElement));
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  const toggleFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {
        setIsFullscreen(prev => !prev);
      });
    } else {
      document.exitFullscreen().catch(() => {
        setIsFullscreen(false);
      });
    }
  }, []);

  // Keyboard shortcut Z for Zen / Fullscreen mode
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)) return;
      if (e.key === 'z' || e.key === 'Z') {
        e.preventDefault();
        toggleFullscreen();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [toggleFullscreen]);

  // Touch swipe handling for mobile page turning
  const [touchStart, setTouchStart] = useState<{ x: number; y: number } | null>(null);

  const handleTouchStart = (e: React.TouchEvent) => {
    if (e.touches.length === 1) {
      setTouchStart({ x: e.touches[0].clientX, y: e.touches[0].clientY });
    }
  };

  const handleTouchEnd = (e: React.TouchEvent) => {
    if (!touchStart || e.changedTouches.length === 0) return;
    const deltaX = e.changedTouches[0].clientX - touchStart.x;
    const deltaY = e.changedTouches[0].clientY - touchStart.y;
    setTouchStart(null);

    // Minimum swipe threshold: 60px horizontal, with horizontal movement dominating vertical by 1.4x
    if (Math.abs(deltaX) > 60 && Math.abs(deltaX) > Math.abs(deltaY) * 1.4) {
      if (deltaX < 0 && canGoNext) {
        nextPage();
      } else if (deltaX > 0 && canGoPrev) {
        prevPage();
      }
    }
  };

  if (currentView === 'home') {
    return (
      <HomePage
        books={availableBooks}
        activeTheme={settings.theme}
        onSelectTheme={(theme) => updateSettings({ theme })}
        onOpenBook={handleOpenBook}
      />
    );
  }

  return (
    <div
      className="min-h-screen flex flex-col selection:bg-amber-200 selection:text-amber-950 transition-colors duration-200"
      style={{
        backgroundColor: 'var(--bg-primary)',
        color: 'var(--text-primary)',
      }}
    >
      {/* Sticky Header - hidden in Fullscreen / Zen mode to eliminate clutter */}
      {!isFullscreen && (
        <Header
          bookTitle={manifest.title}
          author={manifest.authorRu || manifest.author}
          chapterTitle={currentPageData.chapterTitle}
          pageNumber={currentPage}
          totalPages={manifest.totalPages}
          progress={progress}
          settings={settings}
          isBookmarked={bookmarks.includes(currentPage)}
          cardsCount={cards.length}
          isCardsOpen={isCardsOpen}
          isFullscreen={isFullscreen}
          onBackToCatalog={handleBackToCatalog}
          onToggleBookmark={() => toggleBookmark(currentPage)}
          onOpenToc={() => setIsTocOpen(true)}
          onOpenSearch={() => setIsSearchOpen(true)}
          onOpenSettings={() => setIsSettingsOpen(true)}
          onToggleScan={() => setIsScanOpen(prev => !prev)}
          onToggleCards={() => setIsCardsOpen(prev => !prev)}
          onToggleFullscreen={toggleFullscreen}
          isScanOpen={isScanOpen}
          onChangeMode={(mode) => updateSettings({ mode })}
        />
      )}

      {/* Discreet Zen Controls in Fullscreen Mode */}
      {isFullscreen && (
        <>
          <div
            className="fixed top-4 right-4 z-40 flex items-center space-x-2 rounded-full px-3 py-1.5 text-xs shadow-xl backdrop-blur-md transition-opacity opacity-40 hover:opacity-100"
            style={{
              backgroundColor: 'var(--bg-card)',
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-primary)',
            }}
          >
            <span className="hidden sm:inline opacity-70">Полноэкранное чтение</span>
            <button
              type="button"
              onClick={toggleFullscreen}
              className="flex items-center space-x-1 font-semibold rounded-full px-2 py-0.5 transition-colors hover:opacity-80 cursor-pointer"
              style={{ backgroundColor: 'var(--accent-soft)', color: 'var(--accent)' }}
              title="Выйти из полноэкранного режима (Z / Esc)"
            >
              <Minimize2 className="h-3 w-3" />
              <span>Выйти [Z]</span>
            </button>
          </div>

          {/* Minimalist Floating Page Nav in Zen Mode */}
          <div
            className="fixed bottom-5 left-1/2 -translate-x-1/2 z-40 flex items-center space-x-3 rounded-full px-4 py-2 text-xs shadow-2xl backdrop-blur-md transition-opacity opacity-40 hover:opacity-100"
            style={{
              backgroundColor: 'var(--bg-card)',
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-primary)',
            }}
          >
            <button
              type="button"
              disabled={!canGoPrev}
              onClick={prevPage}
              className="flex items-center space-x-1 font-medium transition-opacity disabled:opacity-20 cursor-pointer"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              <span>Назад</span>
            </button>
            <span className="font-mono opacity-60">
              {currentPage} / {manifest.endPage}
            </span>
            <button
              type="button"
              disabled={!canGoNext}
              onClick={nextPage}
              className="flex items-center space-x-1 font-medium transition-opacity disabled:opacity-20 cursor-pointer"
            >
              <span>Вперед</span>
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </>
      )}

      {/* Main Reader Scroll Area */}
      <main
        id="reader-scroll-container"
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
        className={`flex-1 overflow-y-auto px-4 py-8 sm:px-6 lg:px-8 transition-all duration-200 touch-pan-y ${
          isScanSplit ? 'lg:pr-[45%]' : ''
        } ${isFullscreen ? 'py-12 sm:py-16' : ''}`}
      >
        <ReaderContent
          page={currentPageData}
          settings={settings}
          cards={cards}
          hoveredParagraphId={hoveredParagraphId}
          onHoverParagraph={setHoveredParagraphId}
          onSelectFootnote={setActiveFootnote}
          onOpenScan={() => setIsScanOpen(true)}
          onOpenCreateCard={openCreateCard}
          onOpenCards={() => setIsCardsOpen(true)}
        />
      </main>

      {/* Floating Selection Toolbar for Creating Cards */}
      <FloatingSelectionToolbar
        currentPage={currentPage}
        onOpenCreateCard={openCreateCard}
      />

      {/* Floating Keyboard Shortcuts Help Button (hidden in fullscreen) */}
      {!isFullscreen && (
        <button
          type="button"
          onClick={() => setIsHelpOpen(true)}
          title="Горячие клавиши [?]"
          className="fixed bottom-18 right-4 z-20 hidden md:flex items-center justify-center rounded-full p-2.5 shadow-lg transition-all hover:scale-110 active:scale-95 border cursor-pointer"
          style={{
            backgroundColor: 'var(--bg-card)',
            color: 'var(--text-secondary)',
            borderColor: 'var(--border-subtle)',
          }}
        >
          <HelpCircle className="h-4 w-4" />
        </button>
      )}

      {/* Sticky Bottom Navigation Bar (hidden in fullscreen) */}
      {!isFullscreen && (
        <BottomBar
          currentPage={currentPage}
          minPage={manifest.startPage}
          maxPage={manifest.endPage}
          canGoPrev={canGoPrev}
          canGoNext={canGoNext}
          progress={progress}
          onPrevPage={prevPage}
          onNextPage={nextPage}
          onSelectPage={goToPage}
        />
      )}

      {/* Side-by-side or Modal Scan Viewer */}
      <ScanViewer
        page={currentPageData}
        isOpen={isScanOpen}
        isSplit={isScanSplit}
        onClose={() => setIsScanOpen(false)}
        onToggleSplit={() => setIsScanSplit(prev => !prev)}
      />

      {/* Research Thought Cards Drawer */}
      <CardsDrawer
        isOpen={isCardsOpen}
        onClose={() => setIsCardsOpen(false)}
        cards={cards}
        currentPage={currentPage}
        onGoToPage={goToPage}
        onEditCard={openEditCard}
        onDeleteCard={deleteCard}
      />

      {/* Card Creation / Edit Modal */}
      <CardModal
        isOpen={activeCardModal !== null}
        onClose={closeCardModal}
        onSave={addCard}
        onUpdate={updateCard}
        initialData={activeCardModal?.initialData}
        cardToEdit={activeCardModal?.card}
      />

      {/* Table of Contents Drawer */}
      <TableOfContents
        isOpen={isTocOpen}
        onClose={() => setIsTocOpen(false)}
        toc={manifest.tableOfContents}
        currentPage={currentPage}
        bookmarks={bookmarks}
        onSelectPage={goToPage}
        bookTitleRu={manifest.titleRu}
        authorRu={manifest.authorRu || manifest.author}
        availableBooks={availableBooks}
        currentBookSlug={currentBookSlug}
        onSelectBook={selectBook}
      />

      {/* Search Modal */}
      <SearchDialog
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
        pages={manifest.pages}
        onSelectPage={goToPage}
      />

      {/* Settings Dialog */}
      <SettingsDialog
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        settings={settings}
        onUpdateSettings={updateSettings}
      />

      {/* Footnote Popover / Bottom Sheet */}
      <FootnotePopup
        footnote={activeFootnote}
        onClose={() => setActiveFootnote(null)}
      />

      {/* Keyboard Shortcuts Modal */}
      {isHelpOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-in fade-in duration-200"
          onClick={() => setIsHelpOpen(false)}
        >
          <div
            className="w-full max-w-sm rounded-2xl border p-5 shadow-2xl"
            style={{
              backgroundColor: 'var(--bg-card)',
              borderColor: 'var(--border-strong)',
              color: 'var(--text-primary)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b pb-3" style={{ borderColor: 'var(--border-subtle)' }}>
              <div className="flex items-center space-x-2">
                <Keyboard className="h-4 w-4" style={{ color: 'var(--accent)' }} />
                <h3 className="text-xs font-bold uppercase tracking-wider">Горячие клавиши</h3>
              </div>
              <button
                type="button"
                onClick={() => setIsHelpOpen(false)}
                className="rounded p-1 hover:opacity-70 cursor-pointer"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-4 space-y-2.5 text-xs">
              <div className="flex items-center justify-between">
                <span>Следующая страница</span>
                <kbd className="rounded border px-1.5 py-0.5 font-mono text-[10px]" style={{ borderColor: 'var(--border-strong)' }}>→ или J</kbd>
              </div>
              <div className="flex items-center justify-between">
                <span>Предыдущая страница</span>
                <kbd className="rounded border px-1.5 py-0.5 font-mono text-[10px]" style={{ borderColor: 'var(--border-strong)' }}>← или K</kbd>
              </div>
              <div className="flex items-center justify-between">
                <span>Полноэкранный дзен-режим (без мишуры)</span>
                <kbd className="rounded border px-1.5 py-0.5 font-mono text-[10px]" style={{ borderColor: 'var(--border-strong)' }}>Z</kbd>
              </div>
              <div className="flex items-center justify-between">
                <span>Режим чтения (RU / Параллельно / EN)</span>
                <kbd className="rounded border px-1.5 py-0.5 font-mono text-[10px]" style={{ borderColor: 'var(--border-strong)' }}>B</kbd>
              </div>
              <div className="flex items-center justify-between">
                <span>Карточки мыслей и цитат</span>
                <kbd className="rounded border px-1.5 py-0.5 font-mono text-[10px]" style={{ borderColor: 'var(--border-strong)' }}>N</kbd>
              </div>
              <div className="flex items-center justify-between">
                <span>Скан оригинала книги</span>
                <kbd className="rounded border px-1.5 py-0.5 font-mono text-[10px]" style={{ borderColor: 'var(--border-strong)' }}>S</kbd>
              </div>
              <div className="flex items-center justify-between">
                <span>Оглавление</span>
                <kbd className="rounded border px-1.5 py-0.5 font-mono text-[10px]" style={{ borderColor: 'var(--border-strong)' }}>T</kbd>
              </div>
              <div className="flex items-center justify-between">
                <span>Шрифт и темы оформления</span>
                <kbd className="rounded border px-1.5 py-0.5 font-mono text-[10px]" style={{ borderColor: 'var(--border-strong)' }}>F</kbd>
              </div>
              <div className="flex items-center justify-between">
                <span>Поиск по книге</span>
                <kbd className="rounded border px-1.5 py-0.5 font-mono text-[10px]" style={{ borderColor: 'var(--border-strong)' }}>/ или Ctrl+K</kbd>
              </div>
              <div className="flex items-center justify-between">
                <span>Закрыть окно</span>
                <kbd className="rounded border px-1.5 py-0.5 font-mono text-[10px]" style={{ borderColor: 'var(--border-strong)' }}>Esc</kbd>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
