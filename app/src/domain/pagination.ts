/**
 * Pure domain logic for book pagination and navigation
 */

export function clampPage(page: number, min: number, max: number): number {
  if (Number.isNaN(page)) return min;
  return Math.min(Math.max(page, min), max);
}

export function canGoNext(currentPage: number, maxPage: number): boolean {
  return currentPage < maxPage;
}

export function canGoPrev(currentPage: number, minPage: number): boolean {
  return currentPage > minPage;
}

export function getNextPage(currentPage: number, maxPage: number): number {
  return canGoNext(currentPage, maxPage) ? currentPage + 1 : currentPage;
}

export function getPrevPage(currentPage: number, minPage: number): number {
  return canGoPrev(currentPage, minPage) ? currentPage - 1 : currentPage;
}
