import { useState, useEffect, useCallback, useMemo } from 'react';
import { getBookManifest, registeredBooks, getAllBooksSummary } from '../data/library/libraryRegistry';
import { clampPage, getNextPage, getPrevPage, canGoNext, canGoPrev } from './pagination';
import { calculateProgress } from './progress';
import { defaultStorage } from '../infrastructure/storage';
import type { ReaderSettings, ReaderMode, PageData, FootnotePair, ResearchCard } from './types';
import { createResearchCard, type CreateCardInput } from './cards';
import {
  parseReaderLocation,
  serializeReaderLocation,
  resolveAndValidateLocation,
  type ManifestBoundsResolver,
} from './router';
import type { ReaderLocationV2 } from './storage/storageV2';
import { extractBookCitationMetadata } from './citation';

const boundsResolver: ManifestBoundsResolver = (slug: string) => {
  const b = registeredBooks[slug];
  if (!b) return null;
  return {
    startPage: b.startPage,
    endPage: b.endPage,
  };
};

export function useReader() {
  const getInitialLocation = (): ReaderLocationV2 => {
    if (typeof window !== 'undefined' && window.location.hash) {
      const parsed = parseReaderLocation(window.location.hash, 'schreiner-ntt');
      if (parsed.bookSlug && registeredBooks[parsed.bookSlug]) {
        return resolveAndValidateLocation(parsed, boundsResolver);
      }
    }
    const defaultSlug = 'schreiner-ntt';
    const initialManifest = getBookManifest(defaultSlug);
    const lastPage = defaultStorage.getLastPage(initialManifest.startPage, defaultSlug);
    return {
      bookSlug: defaultSlug,
      pageNumber: clampPage(lastPage, initialManifest.startPage, initialManifest.endPage),
    };
  };

  const initialLoc = useMemo(getInitialLocation, []);
  const [currentBookSlug, setCurrentBookSlug] = useState<string>(initialLoc.bookSlug || 'schreiner-ntt');
  const [currentPage, setCurrentPage] = useState<number>(initialLoc.pageNumber || 867);

  const manifest = useMemo(() => getBookManifest(currentBookSlug), [currentBookSlug]);
  const minPage = manifest.startPage;
  const maxPage = manifest.endPage;

  const [settings, setSettings] = useState<ReaderSettings>(() => defaultStorage.getSettings());
  const [bookmarks, setBookmarks] = useState<number[]>(() => defaultStorage.getBookmarks(currentBookSlug));
  const [cards, setCards] = useState<ResearchCard[]>(() => defaultStorage.getCards(currentBookSlug));

  const [activeFootnote, setActiveFootnote] = useState<FootnotePair | null>(null);
  const [isTocOpen, setIsTocOpen] = useState<boolean>(false);
  const [isSearchOpen, setIsSearchOpen] = useState<boolean>(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);
  const [isScanOpen, setIsScanOpen] = useState<boolean>(false);
  const [isScanSplit, setIsScanSplit] = useState<boolean>(false);
  const [isCardsOpen, setIsCardsOpen] = useState<boolean>(false);
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

  // Sync theme to root html element data-theme attribute
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', settings.theme);
  }, [settings.theme]);

  // When currentBookSlug changes, re-fetch bookmarks and cards for that specific book
  useEffect(() => {
    setBookmarks(defaultStorage.getBookmarks(currentBookSlug));
    setCards(defaultStorage.getCards(currentBookSlug));
  }, [currentBookSlug]);

  // Persist settings
  const updateSettings = useCallback((updater: Partial<ReaderSettings>) => {
    setSettings(prev => {
      const next = { ...prev, ...updater };
      defaultStorage.saveSettings(next);
      return next;
    });
  }, []);

  // Close all open overlays
  const closeAllOverlays = useCallback(() => {
    setIsTocOpen(false);
    setIsSearchOpen(false);
    setIsSettingsOpen(false);
    setIsScanOpen(false);
    setActiveCardModal(null);
    setActiveFootnote(null);
  }, []);

  // Central atomic navigation command (playbook 11.3)
  const navigateLocation = useCallback((target: Partial<ReaderLocationV2>, updateHash = true) => {
    const resolved = resolveAndValidateLocation(
      target,
      boundsResolver,
      currentBookSlug,
      currentPage
    );

    setCurrentBookSlug(resolved.bookSlug);
    setCurrentPage(resolved.pageNumber);
    defaultStorage.saveLastPage(resolved.pageNumber, resolved.bookSlug);

    closeAllOverlays();

    if (updateHash && typeof window !== 'undefined') {
      const hash = serializeReaderLocation(resolved);
      if (window.location.hash !== hash) {
        window.location.hash = hash;
      }
    }

    // Scroll reader area to top
    const readerArea = document.getElementById('reader-scroll-container');
    if (readerArea && typeof readerArea.scrollTo === 'function') {
      readerArea.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }, [currentBookSlug, currentPage, closeAllOverlays]);

  // Listen for browser Back/Forward (hashchange)
  useEffect(() => {
    const handleHashChange = () => {
      if (typeof window === 'undefined') return;
      const hash = window.location.hash;
      if (hash === '#catalog' || hash === '#home' || hash === '' || hash === '#') {
        return;
      }
      const parsed = parseReaderLocation(hash, currentBookSlug, currentPage);
      if (parsed.bookSlug && registeredBooks[parsed.bookSlug]) {
        navigateLocation(parsed, false);
      }
    };

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, [currentBookSlug, currentPage, navigateLocation]);

  // Select a book from library
  const selectBook = useCallback((slug: string) => {
    if (registeredBooks[slug]) {
      const targetManifest = registeredBooks[slug];
      const savedPage = defaultStorage.getLastPage(targetManifest.startPage, slug);
      navigateLocation({
        bookSlug: slug,
        pageNumber: clampPage(savedPage, targetManifest.startPage, targetManifest.endPage),
      });
    }
  }, [navigateLocation]);

  // Update page inside current book
  const goToPage = useCallback((page: number) => {
    navigateLocation({
      bookSlug: currentBookSlug,
      pageNumber: page,
    });
  }, [currentBookSlug, navigateLocation]);

  const nextPage = useCallback(() => {
    goToPage(getNextPage(currentPage, maxPage));
  }, [currentPage, maxPage, goToPage]);

  const prevPage = useCallback(() => {
    goToPage(getPrevPage(currentPage, minPage));
  }, [currentPage, minPage, goToPage]);

  const toggleBookmark = useCallback((page: number) => {
    const updated = defaultStorage.toggleBookmark(page, currentBookSlug);
    setBookmarks(updated);
  }, [currentBookSlug]);

  const addCard = useCallback((input: CreateCardInput) => {
    const citationSnapshot = extractBookCitationMetadata(manifest);
    const newCard = createResearchCard({
      ...input,
      bookSlug: currentBookSlug,
      citationSnapshot,
    });
    const updated = defaultStorage.addCard(newCard, currentBookSlug);
    setCards(updated);
    return newCard;
  }, [currentBookSlug, manifest]);

  const updateCard = useCallback((id: string, updates: Partial<ResearchCard>) => {
    const updated = defaultStorage.updateCard(id, updates, currentBookSlug);
    setCards(updated);
  }, [currentBookSlug]);

  const deleteCard = useCallback((id: string) => {
    const updated = defaultStorage.deleteCard(id, currentBookSlug);
    setCards(updated);
  }, [currentBookSlug]);

  const openCreateCard = useCallback((data: {
    pageNumber: number;
    paragraphId?: string;
    quote: string;
    quoteLanguage: 'ru' | 'en';
  }) => {
    setActiveCardModal({ initialData: data });
  }, []);

  const openEditCard = useCallback((card: ResearchCard) => {
    setActiveCardModal({ card });
  }, []);

  const closeCardModal = useCallback(() => {
    setActiveCardModal(null);
  }, []);

  const cycleMode = useCallback(() => {
    const modes: ReaderMode[] = ['ru', 'bilingual', 'en'];
    const nextIdx = (modes.indexOf(settings.mode) + 1) % modes.length;
    updateSettings({ mode: modes[nextIdx] });
  }, [settings.mode, updateSettings]);

  // Current page data
  const currentPageData: PageData = useMemo(() => {
    const found = manifest.pages.find(p => p.pageNumber === currentPage);
    return found || manifest.pages[0];
  }, [currentPage, manifest]);

  // Progress computation
  const progress = useMemo(() => {
    return calculateProgress(currentPage, manifest.pages);
  }, [currentPage, manifest]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Do not trigger if typing in an input
      if (['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)) {
        return;
      }

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setIsSearchOpen(prev => !prev);
        return;
      }

      switch (e.key) {
        case 'ArrowRight':
        case 'j':
        case 'J':
          nextPage();
          break;
        case 'ArrowLeft':
        case 'k':
        case 'K':
          prevPage();
          break;
        case 'b':
        case 'B':
          cycleMode();
          break;
        case 's':
        case 'S':
          setIsScanOpen(prev => !prev);
          break;
        case 't':
        case 'T':
          setIsTocOpen(prev => !prev);
          break;
        case 'n':
        case 'N':
          setIsCardsOpen(prev => !prev);
          break;
        case 'f':
        case 'F':
          setIsSettingsOpen(prev => !prev);
          break;
        case '/':
          e.preventDefault();
          setIsSearchOpen(true);
          break;
        case 'Escape':
          closeAllOverlays();
          setIsCardsOpen(false);
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [nextPage, prevPage, cycleMode, closeAllOverlays]);

  return {
    manifest,
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
    setIsTocOpen,
    setIsSearchOpen,
    setIsSettingsOpen,
    setIsScanOpen,
    setIsScanSplit,
    setIsCardsOpen,
    setHoveredParagraphId,
    cycleMode,
  };
}
