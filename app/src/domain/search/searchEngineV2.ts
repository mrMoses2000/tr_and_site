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

export interface SearchCorpusEntry {
  pageNumber: number;
  paragraphId: string;
  targetType: 'paragraph' | 'footnote' | 'heading';
  footnoteId?: number;
  language: 'ru' | 'en' | string;
  chapterTitle?: string;
  text: string;
}

export interface SearchOptions {
  maxResults?: number;
  snippetRadius?: number;
  isCancelled?: () => boolean;
}

export interface SearchResultDetails {
  matches: SearchMatchV2[];
  totalMatches: number;
  truncated: boolean;
}

export type SearchOutput = SearchMatchV2[] & SearchResultDetails;

function emptySearchOutput(): SearchOutput {
  const emptyResult = [] as unknown as SearchOutput;
  emptyResult.matches = [];
  emptyResult.totalMatches = 0;
  emptyResult.truncated = false;
  return emptyResult;
}

function pushMatch(
  matches: SearchMatchV2[],
  record: SearchCorpusEntry,
  offset: number,
  radius: number,
  queryLen: number,
): void {
  const start = Math.max(0, offset - radius);
  const matchEnd = offset + queryLen;
  const end = Math.min(record.text.length, matchEnd + radius);
  matches.push({
    pageNumber: record.pageNumber,
    paragraphId: record.paragraphId,
    targetType: record.targetType,
    footnoteId: record.footnoteId,
    language: record.language,
    chapterTitle: record.chapterTitle,
    offset,
    snippetPrefix: (start > 0 ? '…' : '') + record.text.slice(start, offset),
    snippetMatch: record.text.slice(offset, matchEnd),
    snippetSuffix: record.text.slice(matchEnd, end) + (end < record.text.length ? '…' : ''),
  });
}

export function searchCorpusV2(
  corpus: SearchCorpusEntry[],
  query: string,
  options?: SearchOptions,
): SearchOutput {
  const trimmed = query.trim();
  const maxResults = options?.maxResults;
  const radius = options?.snippetRadius ?? 40;

  if (!trimmed || trimmed.length < 2) {
    return emptySearchOutput();
  }

  const matches: SearchMatchV2[] = [];
  let totalMatches = 0;
  const lowerQuery = trimmed.toLowerCase();
  const queryLen = trimmed.length;

  for (let recordIndex = 0; recordIndex < corpus.length; recordIndex += 1) {
    if (options?.isCancelled?.()) {
      break;
    }
    const record = corpus[recordIndex];
    const haystack = record.text.toLowerCase();
    let offset = 0;
    while ((offset = haystack.indexOf(lowerQuery, offset)) !== -1) {
      totalMatches += 1;
      if (!maxResults || matches.length < maxResults) {
        pushMatch(matches, record, offset, radius, queryLen);
      }
      offset += queryLen;
      if (options?.isCancelled?.()) {
        break;
      }
    }
  }

  const result = [...matches] as SearchOutput;
  result.matches = matches;
  result.totalMatches = totalMatches;
  result.truncated = maxResults !== undefined && totalMatches > maxResults;
  return result;
}

export function searchPagesV2(
  pages: PageData[],
  query: string,
  options?: SearchOptions,
): SearchOutput {
  const corpus: SearchCorpusEntry[] = [];

  for (const page of pages) {
    for (const para of page.paragraphs) {
      if (para.ru) {
        corpus.push({
          pageNumber: page.pageNumber,
          paragraphId: para.id,
          targetType: 'paragraph',
          language: 'ru',
          chapterTitle: page.chapterTitle,
          text: para.ru,
        });
      }
      if (para.en) {
        corpus.push({
          pageNumber: page.pageNumber,
          paragraphId: para.id,
          targetType: 'paragraph',
          language: 'en',
          chapterTitle: page.chapterTitle,
          text: para.en,
        });
      }
    }

    for (const fn of page.footnotes || []) {
      if (fn.textRu) {
        corpus.push({
          pageNumber: page.pageNumber,
          paragraphId: `fn-${fn.id}`,
          targetType: 'footnote',
          footnoteId: fn.id,
          language: 'ru',
          chapterTitle: `Сноска ${fn.id}`,
          text: fn.textRu,
        });
      }
      if (fn.textEn) {
        corpus.push({
          pageNumber: page.pageNumber,
          paragraphId: `fn-${fn.id}`,
          targetType: 'footnote',
          footnoteId: fn.id,
          language: 'en',
          chapterTitle: `Footnote ${fn.id}`,
          text: fn.textEn,
        });
      }
    }
  }

  return searchCorpusV2(corpus, query, options);
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
  debounceMs = 250,
): DebouncedSearchExecutor {
  let timer: ReturnType<typeof setTimeout> | null = null;
  let activeReject: ((reason: any) => void) | null = null;

  return {
    search: (query: string, options?: SearchOptions) => {
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
