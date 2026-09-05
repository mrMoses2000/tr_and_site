/**
 * Pure domain logic for multilingual full-text search and snippet extraction
 */
import type { PageData } from './types';

export interface SearchMatch {
  pageNumber: number;
  paragraphId: string;
  language: 'ru' | 'en';
  chapterTitle?: string;
  snippetPrefix: string;
  snippetMatch: string;
  snippetSuffix: string;
}

export function searchPages(pages: PageData[], query: string, snippetRadius: number = 40): SearchMatch[] {
  const trimmed = query.trim();
  if (!trimmed || trimmed.length < 2) {
    return [];
  }

  const lowerQuery = trimmed.toLowerCase();
  const results: SearchMatch[] = [];

  for (const page of pages) {
    for (const para of page.paragraphs) {
      // Check Russian
      const ruLower = para.ru.toLowerCase();
      const ruIdx = ruLower.indexOf(lowerQuery);
      if (ruIdx !== -1) {
        const start = Math.max(0, ruIdx - snippetRadius);
        const matchEnd = ruIdx + trimmed.length;
        const end = Math.min(para.ru.length, matchEnd + snippetRadius);

        results.push({
          pageNumber: page.pageNumber,
          paragraphId: para.id,
          language: 'ru',
          chapterTitle: page.chapterTitle,
          snippetPrefix: (start > 0 ? '…' : '') + para.ru.slice(start, ruIdx),
          snippetMatch: para.ru.slice(ruIdx, matchEnd),
          snippetSuffix: para.ru.slice(matchEnd, end) + (end < para.ru.length ? '…' : ''),
        });
      }

      // Check English
      const enLower = para.en.toLowerCase();
      const enIdx = enLower.indexOf(lowerQuery);
      if (enIdx !== -1) {
        const start = Math.max(0, enIdx - snippetRadius);
        const matchEnd = enIdx + trimmed.length;
        const end = Math.min(para.en.length, matchEnd + snippetRadius);

        results.push({
          pageNumber: page.pageNumber,
          paragraphId: para.id,
          language: 'en',
          chapterTitle: page.chapterTitle,
          snippetPrefix: (start > 0 ? '…' : '') + para.en.slice(start, enIdx),
          snippetMatch: para.en.slice(enIdx, matchEnd),
          snippetSuffix: para.en.slice(matchEnd, end) + (end < para.en.length ? '…' : ''),
        });
      }
    }

    // Check Footnotes
    for (const fn of page.footnotes) {
      const fnRuLower = fn.textRu.toLowerCase();
      const fnRuIdx = fnRuLower.indexOf(lowerQuery);
      if (fnRuIdx !== -1) {
        const start = Math.max(0, fnRuIdx - snippetRadius);
        const matchEnd = fnRuIdx + trimmed.length;
        const end = Math.min(fn.textRu.length, matchEnd + snippetRadius);

        results.push({
          pageNumber: page.pageNumber,
          paragraphId: `fn-${fn.id}`,
          language: 'ru',
          chapterTitle: `Сноска ${fn.id}`,
          snippetPrefix: (start > 0 ? '…' : '') + fn.textRu.slice(start, fnRuIdx),
          snippetMatch: fn.textRu.slice(fnRuIdx, matchEnd),
          snippetSuffix: fn.textRu.slice(matchEnd, end) + (end < fn.textRu.length ? '…' : ''),
        });
      }

      const fnEnLower = fn.textEn.toLowerCase();
      const fnEnIdx = fnEnLower.indexOf(lowerQuery);
      if (fnEnIdx !== -1) {
        const start = Math.max(0, fnEnIdx - snippetRadius);
        const matchEnd = fnEnIdx + trimmed.length;
        const end = Math.min(fn.textEn.length, matchEnd + snippetRadius);

        results.push({
          pageNumber: page.pageNumber,
          paragraphId: `fn-${fn.id}`,
          language: 'en',
          chapterTitle: `Footnote ${fn.id}`,
          snippetPrefix: (start > 0 ? '…' : '') + fn.textEn.slice(start, fnEnIdx),
          snippetMatch: fn.textEn.slice(fnEnIdx, matchEnd),
          snippetSuffix: fn.textEn.slice(matchEnd, end) + (end < fn.textEn.length ? '…' : ''),
        });
      }
    }
  }

  return results;
}
