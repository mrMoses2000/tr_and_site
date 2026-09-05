import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  bookSummaries,
  getAllBooksSummary,
  loadBookManifest,
  registeredBooks,
  type BookManifestLoader,
} from '../data/library/libraryRegistry';
import { clampPage, getNextPage, getPrevPage, canGoNext, canGoPrev } from './pagination';
import { calculateProgress } from './progress';
import { defaultStorage } from '../infrastructure/storage';
import type { ReaderSettings, ReaderMode, PageData, FootnotePair, ResearchCard, BookManifest } from './types';
import { createResearchCard, type CreateCardInput } from './cards';
import {
  parseReaderLocation,
  serializeReaderLocation,
  resolveAndValidateLocation,
  type ManifestBoundsResolver,
} from './router';
import type { ReaderLocationV2 } from './storage/storageV2';
import { extractBookCitationMetadata } from './citation';

const DEFAULT_BOOK_SLUG = 'schreiner-ntt';

const boundsResolver: ManifestBoundsResolver = (slug) => {
  const loaded = registeredBooks[slug];
  if (loaded) return { startPage: loaded.startPage, endPage: loaded.endPage };
  const summary = bookSummaries[slug];
  if (summary) return { startPage: 1, endPage: summary.totalPages };
  return null;
};

export type ManifestLoadState = 'loading' | 'ready' | 'error';

export interface UseReaderOptions {
  loadManifest?: BookManifestLoader;
  initialLocation?: ReaderLocationV2;
}

function getInitialLocation(initialLocation?: ReaderLocationV2): ReaderLocationV2 {
  if (initialLocation) return initialLocation;
  if (typeof window !== 'undefined' && window.location.hash) {
    const parsed = parseReaderLocation(window.location.hash, DEFAULT_BOOK_SLUG);
    if (parsed.bookSlug && parsed.view !== 'catalog') {
      const bounds = boundsResolver(parsed.bookSlug);
      return {
        ...parsed,
        pageNumber: bounds
          ? clampPage(parsed.pageNumber, bounds.startPage, bounds.endPage)
          : Math.max(1, parsed.pageNumber),
      };
    }
  }
  const initialManifest = registeredBooks[DEFAULT_BOOK_SLUG];
  const lastPage = defaultStorage.getLastPage(initialManifest.startPage, DEFAULT_BOOK_SLUG);
  return {
    bookSlug: DEFAULT_BOOK_SLUG,
    pageNumber: clampPage(lastPage, initialManifest.startPage, initialManifest.endPage),
    view: 'adapted',
  };
}

export function useReader(options: UseReaderOptions = {}) {
  const manifestLoader = options.loadManifest ?? loadBookManifest;
  const initialLoc = useMemo(
    () => getInitialLocation(options.initialLocation),
    [options.initialLocation],
  );
  const [location, setLocation] = useState<ReaderLocationV2>(initialLoc);
  const [manifest, setManifest] = useState<BookManifest | null>(
    () => registeredBooks[initialLoc.bookSlug] ?? null,
  );
  const [manifestLoadState, setManifestLoadState] = useState<ManifestLoadState>(
    () => (registeredBooks[initialLoc.bookSlug] ? 'ready' : 'loading'),
  );
  const [manifestError, setManifestError] = useState<Error | null>(null);
  const pendingPageByBook = useRef<Record<string, number>>({
    [initialLoc.bookSlug]: initialLoc.pageNumber,
  });

  const currentBookSlug = location.bookSlug;
  const currentPage = location.pageNumber;
  const minPage = manifest?.startPage ?? boundsResolver(currentBookSlug)?.startPage ?? 1;
  const maxPage = manifest?.endPage ?? boundsResolver(currentBookSlug)?.endPage ?? 1;

  const [settings, setSettings] = useState<ReaderSettings>(() => {
    const stored = defaultStorage.getSettings();
    return initialLoc.mode ? { ...stored, mode: initialLoc.mode } : stored;
  });
  const [bookmarks, setBookmarks] = useState<number[]>(() => defaultStorage.getBookmarks(currentBookSlug));
  const [cards, setCards] = useState<ResearchCard[]>(() => defaultStorage.getCards(currentBookSlug));
  const [activeFootnote, setActiveFootnoteState] = useState<FootnotePair | null>(null);
  const [isTocOpen, setIsTocOpen] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isScanOpen, setIsScanOpen] = useState(false);
  const [isScanSplit, setIsScanSplit] = useState(false);
  const [isCardsOpen, setIsCardsOpen] = useState(false);
  const [activeCardModal, setActiveCardModal] = useState<{
    card?: ResearchCard;
    initialData?: {
      pageNumber: number;
      paragraphId?: string;
      quote: string;
      quoteLanguage: 'ru' | 'en';
    };
  } | null>(null);
  const [hoveredParagraphId, setHoveredParagraphId] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const currentManifest = manifest?.slug === currentBookSlug ? manifest : null;
    if (!currentManifest) {
      setManifest(null);
      setManifestLoadState('loading');
    }
    setManifestError(null);

    void manifestLoader(currentBookSlug, controller.signal)
      .then((loaded) => {
        if (!active || controller.signal.aborted) return;
        setManifest(loaded);
        setManifestLoadState('ready');
        const requestedPage = pendingPageByBook.current[currentBookSlug] ?? location.pageNumber;
        setLocation((previous) => {
          if (previous.bookSlug !== currentBookSlug) return previous;
          const loadedBoundsResolver: ManifestBoundsResolver = (slug) => {
            if (slug === currentBookSlug) {
              return { startPage: loaded.startPage, endPage: loaded.endPage };
            }
            return boundsResolver(slug);
          };
          return resolveAndValidateLocation(
            { ...previous, pageNumber: requestedPage },
            loadedBoundsResolver,
            currentBookSlug,
            requestedPage,
          );
        });
      })
      .catch((error: unknown) => {
        if (!active || controller.signal.aborted) return;
        setManifest(null);
        setManifestLoadState('error');
        setManifestError(error instanceof Error ? error : new Error(String(error)));
      });

    return () => {
      active = false;
      controller.abort();
    };
    // Page changes must not restart a manifest request.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentBookSlug, manifestLoader]);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', settings.theme);
  }, [settings.theme]);

  useEffect(() => {
    setBookmarks(defaultStorage.getBookmarks(currentBookSlug));
    setCards(defaultStorage.getCards(currentBookSlug));
  }, [currentBookSlug]);

  useEffect(() => {
    if (!manifest || location.footnoteId === undefined) {
      setActiveFootnoteState(null);
      return;
    }
    const page = manifest.pages.find((item) => item.pageNumber === location.pageNumber);
    const footnote = page?.footnotes.find((item) => String(item.id) === String(location.footnoteId));
    setActiveFootnoteState(footnote ?? null);
  }, [manifest, location.pageNumber, location.footnoteId]);

  const updateSettings = useCallback((updater: Partial<ReaderSettings>) => {
    setSettings((previous) => {
      const next = { ...previous, ...updater };
      defaultStorage.saveSettings(next);
      return next;
    });
  }, []);

  const closeAllOverlays = useCallback(() => {
    setIsTocOpen(false);
    setIsSearchOpen(false);
    setIsSettingsOpen(false);
    setIsScanOpen(false);
    setActiveCardModal(null);
    setActiveFootnoteState(null);
  }, []);

  const navigateLocation = useCallback((target: Partial<ReaderLocationV2>, updateHash = true) => {
    const resolved = resolveAndValidateLocation(
      { ...location, ...target },
      boundsResolver,
      currentBookSlug,
      currentPage,
    );
    pendingPageByBook.current[resolved.bookSlug] = resolved.pageNumber;
    setLocation(resolved);
    defaultStorage.saveLastPage(resolved.pageNumber, resolved.bookSlug);
    if (resolved.mode) updateSettings({ mode: resolved.mode });
    setHoveredParagraphId(resolved.blockId ?? null);
    closeAllOverlays();
    if (updateHash && typeof window !== 'undefined') {
      const hash = serializeReaderLocation(resolved);
      if (window.location.hash !== hash) window.location.hash = hash;
    }
    const readerArea = document.getElementById('reader-scroll-container');
    if (readerArea && typeof readerArea.scrollTo === 'function') {
      readerArea.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }, [closeAllOverlays, currentBookSlug, currentPage, location, updateSettings]);

  useEffect(() => {
    const handleHashChange = () => {
      if (typeof window === 'undefined') return;
      const parsed = parseReaderLocation(window.location.hash, currentBookSlug, currentPage);
      if (parsed.view === 'catalog' || !parsed.bookSlug) return;
      navigateLocation(parsed, false);
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, [currentBookSlug, currentPage, navigateLocation]);

  const selectBook = useCallback((slug: string, page?: number) => {
    const bounds = boundsResolver(slug);
    const requestedPage = page ?? defaultStorage.getLastPage(bounds?.startPage ?? 1, slug);
    pendingPageByBook.current[slug] = requestedPage;
    navigateLocation({
      bookSlug: slug,
      pageNumber: requestedPage,
      view: 'adapted',
      blockId: undefined,
      footnoteId: undefined,
    });
  }, [navigateLocation]);

  const goToPage = useCallback((page: number) => {
    navigateLocation({ bookSlug: currentBookSlug, pageNumber: page, blockId: undefined, footnoteId: undefined });
  }, [currentBookSlug, navigateLocation]);
  const nextPage = useCallback(() => goToPage(getNextPage(currentPage, maxPage)), [currentPage, maxPage, goToPage]);
  const prevPage = useCallback(() => goToPage(getPrevPage(currentPage, minPage)), [currentPage, minPage, goToPage]);

  const toggleBookmark = useCallback((page: number) => {
    setBookmarks(defaultStorage.toggleBookmark(page, currentBookSlug));
  }, [currentBookSlug]);

  const addCard = useCallback((input: CreateCardInput) => {
    if (!manifest) throw new Error('Book manifest is not loaded');
    const newCard = createResearchCard({
      ...input,
      bookSlug: currentBookSlug,
      citationSnapshot: extractBookCitationMetadata(manifest),
    });
    setCards(defaultStorage.addCard(newCard, currentBookSlug));
    return newCard;
  }, [currentBookSlug, manifest]);
  const updateCard = useCallback((id: string, updates: Partial<ResearchCard>) => {
    setCards(defaultStorage.updateCard(id, updates, currentBookSlug));
  }, [currentBookSlug]);
  const deleteCard = useCallback((id: string) => {
    setCards(defaultStorage.deleteCard(id, currentBookSlug));
  }, [currentBookSlug]);
  const openCreateCard = useCallback((data: {
    pageNumber: number;
    paragraphId?: string;
    quote: string;
    quoteLanguage: 'ru' | 'en';
  }) => setActiveCardModal({ initialData: data }), []);
  const openEditCard = useCallback((card: ResearchCard) => setActiveCardModal({ card }), []);
  const closeCardModal = useCallback(() => setActiveCardModal(null), []);
  const cycleMode = useCallback(() => {
    const modes: ReaderMode[] = ['ru', 'bilingual', 'en'];
    const nextIndex = (modes.indexOf(settings.mode) + 1) % modes.length;
    updateSettings({ mode: modes[nextIndex] });
  }, [settings.mode, updateSettings]);
  const openFootnote = useCallback((footnote: FootnotePair) => {
    navigateLocation({ footnoteId: footnote.id, blockId: `fn-${footnote.id}` });
  }, [navigateLocation]);
  const closeFootnote = useCallback(() => {
    setActiveFootnoteState(null);
    navigateLocation({
      footnoteId: undefined,
      blockId: location.blockId?.startsWith('fn-') ? undefined : location.blockId,
    });
  }, [location.blockId, navigateLocation]);
  const setActiveFootnote = useCallback((footnote: FootnotePair | null) => {
    if (footnote) openFootnote(footnote);
    else closeFootnote();
  }, [closeFootnote, openFootnote]);

  const toggleScan = useCallback(() => {
    const nextOpen = !isScanOpen;
    navigateLocation({
      view: nextOpen ? 'scan' : 'adapted',
      blockId: undefined,
      footnoteId: undefined,
    });
    // navigateLocation closes overlays as part of its atomic transition;
    // apply the requested final scan state after that cleanup.
    setIsScanOpen(nextOpen);
  }, [isScanOpen, navigateLocation]);

  useEffect(() => {
    setIsScanOpen(location.view === 'scan');
  }, [location.view]);

  const currentPageData = useMemo<PageData | null>(() => {
    if (!manifest) return null;
    return manifest.pages.find((page) => page.pageNumber === currentPage) ?? null;
  }, [currentPage, manifest]);
  const progress = useMemo(
    () => calculateProgress(currentPage, manifest?.pages ?? []),
    [currentPage, manifest],
  );

  const escapeCssAttribute = (value: string): string => {
    if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') return CSS.escape(value);
    return value.replace(/[^a-zA-Z0-9_-]/g, (character) => `\\${character}`);
  };

  useEffect(() => {
    if (!manifest || (!location.blockId && location.footnoteId === undefined)) return;
    const targetSelector = location.footnoteId !== undefined
      ? `[data-footnote-id="${escapeCssAttribute(String(location.footnoteId))}"]`
      : `[data-paragraph-id="${escapeCssAttribute(location.blockId ?? '')}"]`;
    const target = document.querySelector<HTMLElement>(targetSelector);
    if (!target) return;
    target.scrollIntoView?.({ block: 'center', behavior: 'smooth' });
    target.focus({ preventScroll: true });
  }, [location.blockId, location.footnoteId, manifest, currentPageData, settings.mode]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (['INPUT', 'TEXTAREA'].includes((event.target as HTMLElement)?.tagName)) return;
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setIsSearchOpen((previous) => !previous);
        return;
      }
      switch (event.key) {
        case 'ArrowRight': case 'j': case 'J': nextPage(); break;
        case 'ArrowLeft': case 'k': case 'K': prevPage(); break;
        case 'b': case 'B': cycleMode(); break;
        case 's': case 'S': toggleScan(); break;
        case 't': case 'T': setIsTocOpen((previous) => !previous); break;
        case 'n': case 'N': setIsCardsOpen((previous) => !previous); break;
        case 'f': case 'F': setIsSettingsOpen((previous) => !previous); break;
        case '/': event.preventDefault(); setIsSearchOpen(true); break;
        case 'Escape': closeAllOverlays(); setIsCardsOpen(false); break;
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [closeAllOverlays, cycleMode, nextPage, prevPage, toggleScan]);

  return {
    manifest,
    manifestLoadState,
    manifestError,
    location,
    currentBookSlug,
    selectBook,
    availableBooks: getAllBooksSummary(),
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
    canGoNext: canGoNext(currentPage, maxPage),
    canGoPrev: canGoPrev(currentPage, minPage),
    goToPage,
    navigateLocation,
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
    openFootnote,
    closeFootnote,
    setIsTocOpen,
    setIsSearchOpen,
    setIsSettingsOpen,
    setIsScanOpen,
    setIsScanSplit,
    setIsCardsOpen,
    setHoveredParagraphId,
    cycleMode,
    toggleScan,
  };
}
