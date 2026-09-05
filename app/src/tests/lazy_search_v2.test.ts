import { describe, it, expect, vi } from 'vitest';
import {
  searchPagesV2,
  createDebouncedSearchWorker as createLegacyDebouncedSearchWorker,
  type SearchOptions,
} from '../domain/search/searchEngineV2';
import {
  LazyPageRepository,
  UnavailableChunkError,
  type PageChunkLoader,
  createIndexedPageLoader,
} from '../domain/repository/pageRepository';
import type { PageData } from '../domain/types';
import {
  loadBookManifest,
  UnknownBookError,
  BookManifestLoadCancelledError,
} from '../data/library/libraryRegistry';
import { createDebouncedSearchWorker as createSearchWorkerExecutor } from '../domain/search/searchWorkerClient';

describe('Phase P8: Search Engine V2', () => {
  const samplePages: PageData[] = [
    {
      pageNumber: 10,
      chapterTitle: 'Глава 1. Герменевтический круг',
      paragraphs: [
        {
          id: 'p-10-1',
          ru: 'Герменевтика изучает текст. Правильная герменевтика требует контекста, а герменевтика без богословия слепа.',
          en: 'Hermeneutics examines text. Proper hermeneutics requires context, and hermeneutics without theology is blind.',
        },
        {
          id: 'p-10-2',
          ru: 'Экзегеза и богословие идут рука об руку.',
          en: 'Exegesis and theology walk hand in hand.',
        },
      ],
      footnotes: [
        {
          id: 1,
          textRu: 'См. классическое определение: герменевтика как искусство понимания.',
          textEn: 'See classical definition: hermeneutics as the art of understanding.',
        },
      ],
      imageSrc: '/scans/10.webp',
    },
    {
      pageNumber: 11,
      chapterTitle: 'Глава 1. Герменевтический круг',
      paragraphs: [
        {
          id: 'p-11-1',
          ru: 'Второй шаг анализа — исторический фон.',
          en: 'The second step of analysis is historical background.',
        },
      ],
      footnotes: [],
      imageSrc: '/scans/11.webp',
    },
  ];

  it('finds all repeated matches in the same paragraph instead of only the first', () => {
    // 'герменевтика' appears 3 times in paragraph p-10-1
    const results = searchPagesV2(samplePages, 'герменевтика');

    const p10Matches = results.filter(m => m.paragraphId === 'p-10-1');
    expect(p10Matches.length).toBe(3);

    // Verify distinct snippets for repeated matches
    expect(p10Matches[0].snippetMatch.toLowerCase()).toBe('герменевтика');
    expect(p10Matches[1].snippetMatch.toLowerCase()).toBe('герменевтика');
    expect(p10Matches[2].snippetMatch.toLowerCase()).toBe('герменевтика');
    expect(p10Matches[0].offset).toBeLessThan(p10Matches[1].offset);
    expect(p10Matches[1].offset).toBeLessThan(p10Matches[2].offset);
  });

  it('correctly targets footnotes with footnoteId anchor', () => {
    const results = searchPagesV2(samplePages, 'искусство понимания');
    expect(results.length).toBe(1);
    const match = results[0];
    expect(match.pageNumber).toBe(10);
    expect(match.targetType).toBe('footnote');
    expect(match.footnoteId).toBe(1);
    expect(match.paragraphId).toBe('fn-1');
  });

  it('respects result limit parameter while reporting total matches count', () => {
    const options: SearchOptions = { maxResults: 2 };
    const { matches, totalMatches, truncated } = searchPagesV2(samplePages, 'герменевтика', options);

    expect(matches.length).toBe(2);
    expect(totalMatches).toBe(4); // 3 in paragraph + 1 in footnote
    expect(truncated).toBe(true);
  });

  it('supports cancellation and debouncing for rapid successive queries', async () => {
    const searcher = createLegacyDebouncedSearchWorker(samplePages, 50);

    const promise1 = searcher.search('герм');
    promise1.catch(() => {});
    const promise2 = searcher.search('гермене');
    promise2.catch(() => {});
    const promise3 = searcher.search('герменевтика');

    const result = await promise3;
    expect(result.query).toBe('герменевтика');
    expect(result.matches.length).toBeGreaterThan(0);

    // Earlier searches should be rejected as cancelled
    await expect(promise1).rejects.toThrow(/cancelled/i);
    await expect(promise2).rejects.toThrow(/cancelled/i);
  });

  it('uses worker transport when a search index url is available', async () => {
    const postedMessages: Array<Record<string, unknown>> = [];

    class MockWorker {
      private readonly listeners = new Set<(event: MessageEvent) => void>();

      constructor(public scriptURL: URL, public options: unknown) {}

      addEventListener(type: string, listener: EventListenerOrEventListenerObject) {
        if (type !== 'message' || typeof listener !== 'function') return;
        this.listeners.add(listener as (event: MessageEvent) => void);
      }

      removeEventListener(type: string, listener: EventListenerOrEventListenerObject) {
        if (type !== 'message' || typeof listener !== 'function') return;
        this.listeners.delete(listener as (event: MessageEvent) => void);
      }

      postMessage(message: Record<string, unknown>) {
        postedMessages.push(message);
        if (message.type === 'init') {
          queueMicrotask(() => {
            this.emit({ type: 'ready', bookSlug: 'sample-book', releaseId: 'rel-sample-book' });
          });
          return;
        }
        if (message.type === 'search') {
          queueMicrotask(() => {
            this.emit({
              type: 'result',
              requestId: message.requestId,
              matches: [
                {
                  pageNumber: 10,
                  paragraphId: 'p-10-1',
                  targetType: 'paragraph',
                  language: 'ru',
                  chapterTitle: 'Глава 1',
                  offset: 0,
                  snippetPrefix: '',
                  snippetMatch: 'герменевтика',
                  snippetSuffix: ' …',
                },
              ],
              totalMatches: 1,
              truncated: false,
            });
          });
        }
      }

      terminate() {}

      private emit(data: Record<string, unknown>) {
        for (const listener of this.listeners) {
          listener({ data } as MessageEvent);
        }
      }
    }

    vi.stubGlobal('Worker', MockWorker as unknown as typeof Worker);

    try {
      const searcher = createSearchWorkerExecutor(
        { pages: samplePages, searchIndexUrl: 'https://example.test/search-index.json' },
        0,
      );
      const result = await searcher.search('герменевтика', { maxResults: 10 });

      expect(result.query).toBe('герменевтика');
      expect(result.matches).toHaveLength(1);
      expect(result.totalMatches).toBe(1);
      expect(postedMessages[0]).toMatchObject({
        type: 'init',
        searchIndexUrl: 'https://example.test/search-index.json',
      });
      expect(postedMessages.some((message) => message.type === 'search')).toBe(true);

      searcher.cancel();
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

describe('Phase P8: Lazy Manifests & Page Repository', () => {
  it('rejects unknown slugs without silently falling back to another book', async () => {
    await expect(loadBookManifest('does-not-exist')).rejects.toBeInstanceOf(UnknownBookError);
  });

  it('does not commit a manifest after the caller aborts a load', async () => {
    const controller = new AbortController();
    controller.abort();
    await expect(loadBookManifest('ozborn-germenevticheskaya-spiral', controller.signal))
      .rejects.toBeInstanceOf(BookManifestLoadCancelledError);
  });

  it('loads page chunks on demand and caches subsequent requests', async () => {
    const mockLoader: PageChunkLoader = vi.fn().mockImplementation(async (_slug: string, pageNum: number) => {
      return {
        pageNumber: pageNum,
        chapterTitle: `Page ${pageNum}`,
        paragraphs: [{ id: `p-${pageNum}-1`, ru: `Текст страницы ${pageNum}`, en: `Text of page ${pageNum}` }],
        footnotes: [],
        imageSrc: `/scans/${pageNum}.webp`,
      };
    });

    const repo = new LazyPageRepository(mockLoader);

    // First load hits loader
    const page10 = await repo.getPage('test-book', 10);
    expect(page10.pageNumber).toBe(10);
    expect(mockLoader).toHaveBeenCalledTimes(1);

    // Second load hits cache without calling loader again
    const page10Cached = await repo.getPage('test-book', 10);
    expect(page10Cached.pageNumber).toBe(10);
    expect(mockLoader).toHaveBeenCalledTimes(1);

    // Different page calls loader
    const page20 = await repo.getPage('test-book', 20);
    expect(page20.pageNumber).toBe(20);
    expect(mockLoader).toHaveBeenCalledTimes(2);
  });

  it('throws structured UnavailableChunkError on network or chunk failure', async () => {
    const failingLoader: PageChunkLoader = vi.fn().mockRejectedValue(new Error('Network 404: Chunk not found'));
    const repo = new LazyPageRepository(failingLoader);

    await expect(repo.getPage('missing-book', 404)).rejects.toThrow(UnavailableChunkError);
    try {
      await repo.getPage('missing-book', 404);
    } catch (err: any) {
      expect(err).toBeInstanceOf(UnavailableChunkError);
      expect(err.bookSlug).toBe('missing-book');
      expect(err.pageNumber).toBe(404);
      expect(err.message).toContain('Chunk not found');
    }
  });

  it('supports prefetching adjacent pages in background without blocking current page', async () => {
    const loadedPages: number[] = [];
    const mockLoader: PageChunkLoader = vi.fn().mockImplementation(async (_slug: string, pageNum: number) => {
      loadedPages.push(pageNum);
      return {
        pageNumber: pageNum,
        paragraphs: [],
        footnotes: [],
        imageSrc: '',
      };
    });

    const repo = new LazyPageRepository(mockLoader);
    await repo.getPage('book', 5);
    repo.prefetchAdjacent('book', 5, 1, 10); // Should prefetch 4 and 6

    // Wait for microtasks
    await new Promise(res => setTimeout(res, 20));

    expect(loadedPages).toContain(5);
    expect(loadedPages).toContain(4);
    expect(loadedPages).toContain(6);
  });

  it('loads indexed pages from a pages index and caches chunk fetches', async () => {
    const pagesIndexUrl = 'https://example.test/books/book/releases/rel-book/pages-index.json';
    const fetchMock = vi.fn(async (url: string) => {
      if (url === pagesIndexUrl) {
        return new Response(JSON.stringify({
          schemaVersion: '1.0',
          bookSlug: 'book',
          releaseId: 'rel-book',
          pageRange: { start: 1, end: 2 },
          searchIndexUrl: 'https://example.test/books/book/releases/rel-book/search-index.json',
          pages: [
            { pageNumber: 1, chunkUrl: 'pages/page-1.json' },
            { pageNumber: 2, chunkUrl: 'pages/page-2.json' },
          ],
        }), { status: 200 });
      }
      if (url === 'https://example.test/books/book/releases/rel-book/pages/page-1.json') {
        return new Response(JSON.stringify({
          pageNumber: 1,
          chapterTitle: 'Chapter 1',
          paragraphs: [{ id: 'p-1', ru: 'Текст страницы 1', en: 'Page one text' }],
          footnotes: [],
          imageSrc: '/scans/page_1.webp',
        }), { status: 200 });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });

    const loader = createIndexedPageLoader(pagesIndexUrl, fetchMock as unknown as typeof fetch);

    const first = await loader('book', 1);
    const second = await loader('book', 1);

    expect(first.pageNumber).toBe(1);
    expect(second.pageNumber).toBe(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
