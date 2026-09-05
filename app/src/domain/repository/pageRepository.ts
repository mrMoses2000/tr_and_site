import type { PageData } from '../types';

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

export class LazyPageRepository {
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

    // 1. Return cached if available
    const cached = this.cache.get(k);
    if (cached) {
      return cached;
    }

    // 2. Return in-flight promise if already loading
    const active = this.inFlight.get(k);
    if (active) {
      return active;
    }

    // 3. Initiate chunk fetch
    const loadPromise = (async () => {
      try {
        const page = await this.loader(bookSlug, pageNumber);
        this.cache.set(k, page);
        return page;
      } catch (err: any) {
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
        // Fire and catch errors silently in background prefetch
        this.getPage(bookSlug, p).catch(() => {});
      }
    }
  }

  clearCache(): void {
    this.cache.clear();
    this.inFlight.clear();
  }
}
