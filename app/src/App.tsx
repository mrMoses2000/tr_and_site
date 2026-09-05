import { useState } from 'react';
import { useReader } from './domain/useReader';
import { Header } from './components/Header';
import { ReaderContent } from './components/ReaderContent';
import { ScanViewer } from './components/ScanViewer';
import { TableOfContents } from './components/TableOfContents';
import { SearchDialog } from './components/SearchDialog';
import { SettingsDialog } from './components/SettingsDialog';
import { FootnotePopup } from './components/FootnotePopup';
import { BottomBar } from './components/BottomBar';
import { HelpCircle, X, Keyboard } from 'lucide-react';

export function App() {
  const {
    manifest,
    currentPage,
    currentPageData,
    progress,
    settings,
    bookmarks,
    activeFootnote,
    isTocOpen,
    isSearchOpen,
    isSettingsOpen,
    isScanOpen,
    isScanSplit,
    hoveredParagraphId,
    canGoNext,
    canGoPrev,
    goToPage,
    nextPage,
    prevPage,
    toggleBookmark,
    updateSettings,
    setActiveFootnote,
    setIsTocOpen,
    setIsSearchOpen,
    setIsSettingsOpen,
    setIsScanOpen,
    setIsScanSplit,
    setHoveredParagraphId,
  } = useReader();

  const [isHelpOpen, setIsHelpOpen] = useState(false);

  return (
    <div
      className="min-h-screen flex flex-col selection:bg-amber-200 selection:text-amber-950 transition-colors duration-200"
      style={{
        backgroundColor: 'var(--bg-primary)',
        color: 'var(--text-primary)',
      }}
    >
      {/* Sticky Header */}
      <Header
        bookTitle={manifest.title}
        author={manifest.authorRu || manifest.author}
        chapterTitle={currentPageData.chapterTitle}
        pageNumber={currentPage}
        totalPages={manifest.totalPages}
        progress={progress}
        settings={settings}
        isBookmarked={bookmarks.includes(currentPage)}
        onToggleBookmark={() => toggleBookmark(currentPage)}
        onOpenToc={() => setIsTocOpen(true)}
        onOpenSearch={() => setIsSearchOpen(true)}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onToggleScan={() => setIsScanOpen(prev => !prev)}
        isScanOpen={isScanOpen}
        onChangeMode={(mode) => updateSettings({ mode })}
      />

      {/* Main Reader Scroll Area */}
      <main
        id="reader-scroll-container"
        className={`flex-1 overflow-y-auto px-4 py-8 sm:px-6 lg:px-8 transition-all duration-200 ${
          isScanSplit ? 'lg:pr-[45%]' : ''
        }`}
      >
        <ReaderContent
          page={currentPageData}
          settings={settings}
          hoveredParagraphId={hoveredParagraphId}
          onHoverParagraph={setHoveredParagraphId}
          onSelectFootnote={setActiveFootnote}
          onOpenScan={() => setIsScanOpen(true)}
        />
      </main>

      {/* Floating Keyboard Shortcuts Help Button */}
      <button
        type="button"
        onClick={() => setIsHelpOpen(true)}
        title="Горячие клавиши [?]"
        className="fixed bottom-18 right-4 z-20 hidden md:flex items-center justify-center rounded-full p-2.5 shadow-lg transition-all hover:scale-110 active:scale-95 border"
        style={{
          backgroundColor: 'var(--bg-card)',
          color: 'var(--text-secondary)',
          borderColor: 'var(--border-subtle)',
        }}
      >
        <HelpCircle className="h-4 w-4" />
      </button>

      {/* Sticky Bottom Navigation Bar */}
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

      {/* Side-by-side or Modal Scan Viewer */}
      <ScanViewer
        page={currentPageData}
        isOpen={isScanOpen}
        isSplit={isScanSplit}
        onClose={() => setIsScanOpen(false)}
        onToggleSplit={() => setIsScanSplit(prev => !prev)}
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
                className="rounded p-1 hover:opacity-70"
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
                <span>Режим чтения (RU / Параллельно / EN)</span>
                <kbd className="rounded border px-1.5 py-0.5 font-mono text-[10px]" style={{ borderColor: 'var(--border-strong)' }}>B</kbd>
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
