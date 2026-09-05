/**
 * Pure domain logic for reading progress and time estimation
 */
import type { PageData, ReadingProgress } from './types';

const AVERAGE_WORDS_PER_MINUTE = 180;

export function countWords(text: string): number {
  if (!text) return 0;
  return text.trim().split(/\s+/).filter(Boolean).length;
}

export function estimatePageReadingMinutes(text: string, wordsPerMinute: number = AVERAGE_WORDS_PER_MINUTE): number {
  const words = countWords(text);
  if (words === 0) return 1;
  const minutes = Math.ceil(words / wordsPerMinute);
  return Math.max(1, minutes);
}

export function calculateProgress(
  currentPage: number,
  pages: PageData[]
): ReadingProgress {
  if (pages.length === 0) {
    return {
      currentPage,
      totalPages: 0,
      percent: 0,
      estimatedMinutesLeft: 0,
    };
  }

  const sortedPages = [...pages].sort((a, b) => a.pageNumber - b.pageNumber);
  const minPage = sortedPages[0].pageNumber;
  const total = sortedPages.length;

  const currentIndex = sortedPages.findIndex(p => p.pageNumber === currentPage);
  const pageIdx = currentIndex >= 0 ? currentIndex : Math.min(Math.max(currentPage - minPage, 0), total - 1);

  const percent = Math.round(((pageIdx + 1) / total) * 100);

  // Calculate estimated minutes remaining for subsequent pages
  const remainingPages = sortedPages.slice(pageIdx + 1);
  let totalRemainingWords = 0;
  for (const page of remainingPages) {
    const text = page.translatedRu || page.paragraphs.map(p => p.ru).join(' ') || page.originalEn || '';
    totalRemainingWords += countWords(text);
  }

  const estimatedMinutesLeft = Math.ceil(totalRemainingWords / AVERAGE_WORDS_PER_MINUTE);

  return {
    currentPage,
    totalPages: total,
    percent: Math.min(Math.max(percent, 0), 100),
    estimatedMinutesLeft: Math.max(0, estimatedMinutesLeft),
  };
}

export function calculateProgressFromBounds(
  currentPage: number,
  startPage: number,
  endPage: number,
  totalPages: number,
): ReadingProgress {
  if (totalPages <= 0 || endPage < startPage) {
    return {
      currentPage,
      totalPages: 0,
      percent: 0,
      estimatedMinutesLeft: 0,
    };
  }

  const boundedPage = Math.max(startPage, Math.min(endPage, currentPage));
  const pageIndex = boundedPage - startPage;
  const percent = Math.round(((pageIndex + 1) / totalPages) * 100);

  return {
    currentPage: boundedPage,
    totalPages,
    percent: Math.min(Math.max(percent, 0), 100),
    estimatedMinutesLeft: Math.max(0, totalPages - pageIndex - 1),
  };
}
