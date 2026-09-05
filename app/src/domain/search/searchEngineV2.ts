import type { PageData } from '../types';

export interface SearchMatchV2 {
  pageNumber: number;
  paragraphId: string;
  targetType: 'paragraph' | 'footnote' | 'heading';
  footnoteId?: number;
  language: 'ru' | 'en' | string;
  chapterTitle?: string;
  offset: number;
  snippetPrefix: string;
  snippetMatch: string;
  snippetSuffix: string;
}

export interface SearchOptions {
  maxResults?: number;
  snippetRadius?: number;
}

export interface SearchResultDetails {
  matches: SearchMatchV2[];
  totalMatches: number;
  truncated: boolean;
}

export type SearchOutput = SearchMatchV2[] & SearchResultDetails;

/**
 * Pure search algorithm returning all repeated matches across pages and footnotes.
 */
export function searchPagesV2(
  pages: PageData[],
  query: string,
  options?: SearchOptions
): SearchOutput {
  const trimmed = query.trim();
  const maxResults = options?.maxResults;
  const radius = options?.snippetRadius ?? 40;

  const matches: SearchMatchV2[] = [];
  let totalMatches = 0;

  if (!trimmed || trimmed.length < 2) {
    const emptyResult = [] as any;
    emptyResult.matches = [];
    emptyResult.totalMatches = 0;
    emptyResult.truncated = false;
    return emptyResult;
  }

  const lowerQuery = trimmed.toLowerCase();
  const queryLen = trimmed.length;

  for (const page of pages) {
    // 1. Paragraphs
    for (const para of page.paragraphs) {
      // Russian
      if (para.ru) {
        const ruLower = para.ru.toLowerCase();
        let ruPos = 0;
        while ((ruPos = ruLower.indexOf(lowerQuery, ruPos)) !== -1) {
          totalMatches++;
          if (!maxResults || matches.length < maxResults) {
            const start = Math.max(0, ruPos - radius);
            const matchEnd = ruPos + queryLen;
            const end = Math.min(para.ru.length, matchEnd + radius);

            matches.push({
              pageNumber: page.pageNumber,
              paragraphId: para.id,
              targetType: 'paragraph',
              language: 'ru',
              chapterTitle: page.chapterTitle,
              offset: ruPos,
              snippetPrefix: (start > 0 ? '…' : '') + para.ru.slice(start, ruPos),
              snippetMatch: para.ru.slice(ruPos, matchEnd),
              snippetSuffix: para.ru.slice(matchEnd, end) + (end < para.ru.length ? '…' : ''),
            });
          }
          ruPos += queryLen;
        }
      }

      // English
      if (para.en) {
        const enLower = para.en.toLowerCase();
        let enPos = 0;
        while ((enPos = enLower.indexOf(lowerQuery, enPos)) !== -1) {
          totalMatches++;
          if (!maxResults || matches.length < maxResults) {
            const start = Math.max(0, enPos - radius);
            const matchEnd = enPos + queryLen;
            const end = Math.min(para.en.length, matchEnd + radius);

            matches.push({
              pageNumber: page.pageNumber,
              paragraphId: para.id,
              targetType: 'paragraph',
              language: 'en',
              chapterTitle: page.chapterTitle,
              offset: enPos,
              snippetPrefix: (start > 0 ? '…' : '') + para.en.slice(start, enPos),
              snippetMatch: para.en.slice(enPos, matchEnd),
              snippetSuffix: para.en.slice(matchEnd, end) + (end < para.en.length ? '…' : ''),
            });
          }
          enPos += queryLen;
        }
      }
    }

    // 2. Footnotes
    for (const fn of page.footnotes || []) {
      // Russian
      if (fn.textRu) {
        const ruLower = fn.textRu.toLowerCase();
        let ruPos = 0;
        while ((ruPos = ruLower.indexOf(lowerQuery, ruPos)) !== -1) {
          totalMatches++;
          if (!maxResults || matches.length < maxResults) {
            const start = Math.max(0, ruPos - radius);
            const matchEnd = ruPos + queryLen;
            const end = Math.min(fn.textRu.length, matchEnd + radius);

            matches.push({
              pageNumber: page.pageNumber,
              paragraphId: `fn-${fn.id}`,
              targetType: 'footnote',
              footnoteId: fn.id,
              language: 'ru',
              chapterTitle: `Сноска ${fn.id}`,
              offset: ruPos,
              snippetPrefix: (start > 0 ? '…' : '') + fn.textRu.slice(start, ruPos),
              snippetMatch: fn.textRu.slice(ruPos, matchEnd),
              snippetSuffix: fn.textRu.slice(matchEnd, end) + (end < fn.textRu.length ? '…' : ''),
            });
          }
          ruPos += queryLen;
        }
      }

      // English
      if (fn.textEn) {
        const enLower = fn.textEn.toLowerCase();
        let enPos = 0;
        while ((enPos = enLower.indexOf(lowerQuery, enPos)) !== -1) {
          totalMatches++;
          if (!maxResults || matches.length < maxResults) {
            const start = Math.max(0, enPos - radius);
            const matchEnd = enPos + queryLen;
            const end = Math.min(fn.textEn.length, matchEnd + radius);

            matches.push({
              pageNumber: page.pageNumber,
              paragraphId: `fn-${fn.id}`,
              targetType: 'footnote',
              footnoteId: fn.id,
              language: 'en',
              chapterTitle: `Footnote ${fn.id}`,
              offset: enPos,
              snippetPrefix: (start > 0 ? '…' : '') + fn.textEn.slice(start, enPos),
              snippetMatch: fn.textEn.slice(enPos, matchEnd),
              snippetSuffix: fn.textEn.slice(matchEnd, end) + (end < fn.textEn.length ? '…' : ''),
            });
          }
          enPos += queryLen;
        }
      }
    }
  }

  const result = [...matches] as SearchOutput;
  result.matches = matches;
  result.totalMatches = totalMatches;
  result.truncated = maxResults !== undefined && totalMatches > maxResults;

  return result;
}

/** Current compatibility mode: synchronous main-thread scan over a loaded
 * whole-book manifest. This is cancellable/debounced, but not a Web Worker.
 */
export const SEARCH_EXECUTION_MODE = 'main-thread-whole-manifest-compatibility' as const;

export interface DebouncedSearchExecutor {
  search: (query: string, options?: SearchOptions) => Promise<{ query: string; matches: SearchMatchV2[]; totalMatches: number; truncated: boolean }>;
  cancel: () => void;
}

export function createDebouncedSearchExecutor(
  pages: PageData[],
  debounceMs = 250
): DebouncedSearchExecutor {
  let timer: any = null;
  let activeReject: ((reason: any) => void) | null = null;

  return {
    search: (query: string, options?: SearchOptions) => {
      // Cancel previous in-flight promise
      if (activeReject) {
        activeReject(new Error('Search cancelled by newer query'));
        activeReject = null;
      }
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }

      return new Promise((resolve, reject) => {
        activeReject = reject;
        timer = setTimeout(() => {
          activeReject = null;
          timer = null;
          const res = searchPagesV2(pages, query, options);
          resolve({
            query,
            matches: res.matches,
            totalMatches: res.totalMatches,
            truncated: res.truncated,
          });
        }, debounceMs);
      });
    },
    cancel: () => {
      if (activeReject) {
        activeReject(new Error('Search cancelled'));
        activeReject = null;
      }
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
    },
  };
}

/** @deprecated Kept as a compatibility alias; this does not create a Web Worker. */
export const createDebouncedSearchWorker = createDebouncedSearchExecutor;
