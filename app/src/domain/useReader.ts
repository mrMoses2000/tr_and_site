import { useState, useEffect, useCallback, useMemo } from 'react';
import { getBookManifest, registeredBooks, getAllBooksSummary } from '../data/library/libraryRegistry';
import { clampPage, getNextPage, getPrevPage, canGoNext, canGoPrev } from './pagination';
import { calculateProgress } from './progress';
import { defaultStorage } from '../infrastructure/storage';
import type { ReaderSettings, ReaderMode, PageData, FootnotePair, ResearchCard } from './types';
import { createResearchCard, type CreateCardInput } from './cards';

export function useReader() {
  const getInitialBookSlug = () => {
    if (typeof window !== 'undefined' && window.location.hash) {
      const match = window.location.hash.match(/book=([a-zA-Z0-9_-]+)/);
      if (match && registeredBooks[match[1]]) {
        return match[1];
      }
    }
    return 'schreiner-ntt';
  };

  const [currentBookSlug, setCurrentBookSlug] = useState<string>(getInitialBookSlug);
  const manifest = useMemo(() => getBookManifest(currentBookSlug), [currentBookSlug]);
  const minPage = manifest.startPage;
  const maxPage = manifest.endPage;

  // Initialize page from URL hash (e.g. #page=870) or localStorage
  const initialPage = useMemo(() => {
    if (typeof window !== 'undefined' && window.location.hash) {
      const match = window.location.hash.match(/page=(\d+)/);
      if (match) {
        const p = parseInt(match[1], 10);
        if (!Number.isNaN(p)) {
          return clampPage(p, minPage, maxPage);
        }
      }
    }
    return defaultStorage.getLastPage(minPage);
  }, [minPage, maxPage]);

  const [currentPage, setCurrentPage] = useState<number>(initialPage);
  const [settings, setSettings] = useState<ReaderSettings>(() => defaultStorage.getSettings());
  const [bookmarks, setBookmarks] = useState<number[]>(() => defaultStorage.getBookmarks());
  const [cards, setCards] = useState<ResearchCard[]>(() => defaultStorage.getCards());
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

  // Persist settings
  const updateSettings = useCallback((updater: Partial<ReaderSettings>) => {
    setSettings(prev => {
      const next = { ...prev, ...updater };
      defaultStorage.saveSettings(next);
      return next;
    });
  }, []);

  // Select a book from library
  const selectBook = useCallback((slug: string) => {
    if (registeredBooks[slug]) {
      setCurrentBookSlug(slug);
      const targetManifest = registeredBooks[slug];
      setCurrentPage(targetManifest.startPage);
      if (typeof window !== 'undefined') {
        window.location.hash = `book=${slug}&page=${targetManifest.startPage}`;
      }
      const readerArea = document.getElementById('reader-scroll-container');
      if (readerArea && typeof readerArea.scrollTo === 'function') {
        readerArea.scrollTo({ top: 0, behavior: 'smooth' });
      }
      setActiveFootnote(null);
    }
  }, []);

  // Update URL hash and save last page
  const goToPage = useCallback((page: number) => {
    const clamped = clampPage(page, minPage, maxPage);
    setCurrentPage(clamped);
    defaultStorage.saveLastPage(clamped);
    if (typeof window !== 'undefined') {
      window.location.hash = `book=${currentBookSlug}&page=${clamped}`;
    }
    // Scroll content container to top
    const readerArea = document.getElementById('reader-scroll-container');
    if (readerArea && typeof readerArea.scrollTo === 'function') {
      readerArea.scrollTo({ top: 0, behavior: 'smooth' });
    }
    setActiveFootnote(null);
  }, [minPage, maxPage, currentBookSlug]);

  const nextPage = useCallback(() => {
    goToPage(getNextPage(currentPage, maxPage));
  }, [currentPage, maxPage, goToPage]);

  const prevPage = useCallback(() => {
    goToPage(getPrevPage(currentPage, minPage));
  }, [currentPage, minPage, goToPage]);

  const toggleBookmark = useCallback((page: number) => {
    const updated = defaultStorage.toggleBookmark(page);
    setBookmarks(updated);
  }, []);

  const addCard = useCallback((input: CreateCardInput) => {
    const newCard = createResearchCard(input);
    const updated = defaultStorage.addCard(newCard);
    setCards(updated);
    return newCard;
  }, []);

  const updateCard = useCallback((id: string, updates: Partial<ResearchCard>) => {
    const updated = defaultStorage.updateCard(id, updates);
    setCards(updated);
  }, []);

  const deleteCard = useCallback((id: string) => {
    const updated = defaultStorage.deleteCard(id);
    setCards(updated);
  }, []);

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
          setIsTocOpen(false);
          setIsSearchOpen(false);
          setIsSettingsOpen(false);
          setIsScanOpen(false);
          setIsCardsOpen(false);
          setActiveCardModal(null);
          setActiveFootnote(null);
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [nextPage, prevPage, cycleMode]);

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
