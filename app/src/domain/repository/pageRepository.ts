import type { BookManifest, PageData } from '../types';

export class UnavailableChunkError extends Error {
  public bookSlug: string;
  public pageNumber: number;

  constructor(bookSlug: string, pageNumber: number, message?: string) {
    super(`Unavailable page chunk [${bookSlug}:${pageNumber}]: ${message || 'Failed to load chunk'}`);
    this.name = 'UnavailableChunkError';
    this.bookSlug = bookSlug;
    this.pageNumber = pageNumber;
    Object.setPrototypeOf(this, UnavailableChunkError.prototype);
  }
}

export type PageChunkLoader = (bookSlug: string, pageNumber: number) => Promise<PageData>;

export interface PagesIndexEntry {
  pageNumber: number;
  chunkUrl: string;
  checksum?: string;
  byteSize?: number;
  blockCount?: number;
  footnoteCount?: number;
}

export interface PagesIndexFile {
  schemaVersion: '1.0';
  bookSlug: string;
  releaseId: string;
  pageRange: { start: number; end: number };
  pages: PagesIndexEntry[];
  searchIndexUrl: string;
}

export interface PageRepository {
  getPage(bookSlug: string, pageNumber: number): Promise<PageData>;
  prefetchAdjacent(bookSlug: string, pageNumber: number, minPage?: number, maxPage?: number): void;
  clearCache(): void;
}

function isPageData(value: unknown): value is PageData {
  if (!value || typeof value !== 'object') return false;
  const page = value as Partial<PageData>;
  return typeof page.pageNumber === 'number'
    && Array.isArray(page.paragraphs)
    && Array.isArray(page.footnotes)
    && typeof page.imageSrc === 'string';
}

function isPagesIndexFile(value: unknown): value is PagesIndexFile {
  if (!value || typeof value !== 'object') return false;
  const index = value as Partial<PagesIndexFile>;
  return index.schemaVersion === '1.0'
    && typeof index.bookSlug === 'string'
    && typeof index.releaseId === 'string'
    && typeof index.pageRange?.start === 'number'
    && typeof index.pageRange?.end === 'number'
    && Array.isArray(index.pages)
    && typeof index.searchIndexUrl === 'string';
}

function resolveUrl(baseUrl: string, url: string): string {
  try {
    return new URL(url, baseUrl).toString();
  } catch {
    const dummyOrigin = 'https://logos.invalid';
    const base = new URL(baseUrl, dummyOrigin);
    const resolved = new URL(url, base);
    return resolved.pathname + resolved.search + resolved.hash;
  }
}

async function fetchJson<T>(
  url: string,
  fetchImpl: typeof fetch,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetchImpl(url, { signal });
  if (!response.ok) {
    throw new Error(`Failed to fetch ${url}: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function loadPagesIndex(
  pagesIndexUrl: string,
  fetchImpl: typeof fetch,
  signal?: AbortSignal,
): Promise<PagesIndexFile> {
  const index = await fetchJson<unknown>(pagesIndexUrl, fetchImpl, signal);
  if (!isPagesIndexFile(index)) {
    throw new Error(`Invalid pages index: ${pagesIndexUrl}`);
  }
  return index;
}

export function createIndexedPageLoader(
  pagesIndexUrl: string,
  fetchImpl: typeof fetch = fetch,
): PageChunkLoader {
  let indexPromise: Promise<PagesIndexFile> | null = null;
  const pageUrlCache = new Map<number, string>();
  const pageDataCache = new Map<number, PageData>();

  const ensureIndex = (signal?: AbortSignal) => {
    if (!indexPromise) {
      indexPromise = loadPagesIndex(pagesIndexUrl, fetchImpl, signal).catch((error) => {
        indexPromise = null;
        throw error;
      });
    }
    return indexPromise;
  };

  return async (bookSlug: string, pageNumber: number) => {
    const cached = pageDataCache.get(pageNumber);
    if (cached) {
      return cached;
    }

    const index = await ensureIndex();
    if (index.bookSlug !== bookSlug) {
      throw new UnavailableChunkError(bookSlug, pageNumber, 'page index belongs to a different book');
    }

    let chunkUrl = pageUrlCache.get(pageNumber);
    if (!chunkUrl) {
      const entry = index.pages.find((item) => item.pageNumber === pageNumber);
      if (!entry) {
        throw new UnavailableChunkError(bookSlug, pageNumber, 'page index entry not found');
      }
      chunkUrl = resolveUrl(pagesIndexUrl, entry.chunkUrl);
      pageUrlCache.set(pageNumber, chunkUrl);
    }

    const page = await fetchJson<unknown>(chunkUrl, fetchImpl);
    if (!isPageData(page) || page.pageNumber !== pageNumber) {
      throw new UnavailableChunkError(bookSlug, pageNumber, 'invalid page chunk payload');
    }
    pageDataCache.set(pageNumber, page);
    return page;
  };
}

/** Compatibility repository for current V1 manifests and the new page-indexed
 * release format. If the manifest already carries pages in memory, those win.
 * Otherwise a pages-index + per-page chunk loader is used.
 */
export function createManifestPageRepository(
  manifest: Pick<BookManifest, 'slug' | 'pages' | 'pagesIndexUrl'>,
  fetchImpl: typeof fetch = fetch,
): PageRepository {
  const inMemoryPages = new Map(manifest.pages.map((page) => [page.pageNumber, page] as const));
  const remoteLoader = manifest.pagesIndexUrl
    ? createIndexedPageLoader(manifest.pagesIndexUrl, fetchImpl)
    : null;

  const loader: PageChunkLoader = async (bookSlug: string, pageNumber: number) => {
    const cached = inMemoryPages.get(pageNumber);
    if (cached) {
      return cached;
    }
    if (!remoteLoader) {
      throw new UnavailableChunkError(bookSlug, pageNumber, 'page index unavailable');
    }
    return remoteLoader(bookSlug, pageNumber);
  };

  return new LazyPageRepository(loader);
}

export class LazyPageRepository implements PageRepository {
  private loader: PageChunkLoader;
  private cache: Map<string, PageData> = new Map();
  private inFlight: Map<string, Promise<PageData>> = new Map();

  constructor(loader: PageChunkLoader) {
    this.loader = loader;
  }

  private key(bookSlug: string, pageNumber: number): string {
    return `${bookSlug}:${pageNumber}`;
  }

  async getPage(bookSlug: string, pageNumber: number): Promise<PageData> {
    const k = this.key(bookSlug, pageNumber);

    const cached = this.cache.get(k);
    if (cached) {
      return cached;
    }

    const active = this.inFlight.get(k);
    if (active) {
      return active;
    }

    const loadPromise = (async () => {
      try {
        const page = await this.loader(bookSlug, pageNumber);
        this.cache.set(k, page);
        return page;
      } catch (err: any) {
        if (err instanceof UnavailableChunkError) {
          throw err;
        }
        throw new UnavailableChunkError(bookSlug, pageNumber, err?.message || String(err));
      } finally {
        this.inFlight.delete(k);
      }
    })();

    this.inFlight.set(k, loadPromise);
    return loadPromise;
  }

  prefetchAdjacent(bookSlug: string, pageNumber: number, minPage = 1, maxPage = 9999): void {
    const pagesToPrefetch: number[] = [];
    if (pageNumber > minPage) {
      pagesToPrefetch.push(pageNumber - 1);
    }
    if (pageNumber < maxPage) {
      pagesToPrefetch.push(pageNumber + 1);
    }

    for (const p of pagesToPrefetch) {
      const k = this.key(bookSlug, p);
      if (!this.cache.has(k) && !this.inFlight.has(k)) {
        this.getPage(bookSlug, p).catch(() => {});
      }
    }
  }

  clearCache(): void {
    this.cache.clear();
    this.inFlight.clear();
  }
}
