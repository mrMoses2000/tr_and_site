/**
 * Multilingual full-text search and snippet extraction
 * Backwards compatible adapter over searchEngineV2
 */
import type { PageData } from './types';
import { searchPagesV2 } from './search/searchEngineV2';

export interface SearchMatch {
  pageNumber: number;
  paragraphId: string;
  language: 'ru' | 'en';
  chapterTitle?: string;
  snippetPrefix: string;
  snippetMatch: string;
  snippetSuffix: string;
}

export function searchPages(pages: PageData[], query: string, snippetRadius = 40): SearchMatch[] {
  const matches = searchPagesV2(pages, query, { snippetRadius });
  return matches.map(m => ({
    pageNumber: m.pageNumber,
    paragraphId: m.paragraphId,
    language: (m.language === 'en' ? 'en' : 'ru') as 'ru' | 'en',
    chapterTitle: m.chapterTitle,
    snippetPrefix: m.snippetPrefix,
    snippetMatch: m.snippetMatch,
    snippetSuffix: m.snippetSuffix,
  }));
}
