import type { BookManifest } from '../../domain/types';
import { bookManifest as schreinerManifest } from '../bookManifest';
import bundledCatalog from './generatedCatalog.json';

export interface BookSummary {
  slug: string;
  title: string;
  titleRu: string;
  author: string;
  authorRu: string;
  totalPages: number;
  releaseId?: string;
  manifestUrl?: string;
  pagesIndexUrl?: string;
  searchIndexUrl?: string;
  pageChunkPattern?: string;
  scanPattern?: string;
}

export interface RuntimeCatalog {
  schemaVersion: '1.0';
  generatedAt?: string;
  books: BookSummary[];
}

const bundledRuntimeCatalog = bundledCatalog as RuntimeCatalog;

function normalizeBookSummary(book: BookSummary): BookSummary {
  return {
    slug: book.slug,
    title: book.title,
    titleRu: book.titleRu,
    author: book.author,
    authorRu: book.authorRu,
    totalPages: book.totalPages,
    releaseId: book.releaseId,
    manifestUrl: book.manifestUrl,
    pagesIndexUrl: book.pagesIndexUrl,
    searchIndexUrl: book.searchIndexUrl,
    pageChunkPattern: book.pageChunkPattern,
    scanPattern: book.scanPattern,
  };
}

function validateCatalog(value: unknown): RuntimeCatalog {
  if (!value || typeof value !== 'object') {
    throw new Error('Invalid catalog: expected an object');
  }
  const catalog = value as Record<string, unknown>;
  if (catalog.schemaVersion !== '1.0') {
    throw new Error(`Unsupported catalog schemaVersion: ${String(catalog.schemaVersion)}`);
  }
  if (!Array.isArray(catalog.books)) {
    throw new Error('Invalid catalog: missing books array');
  }
  for (const entry of catalog.books as Array<Record<string, unknown>>) {
    if (typeof entry.slug !== 'string'
      || typeof entry.title !== 'string'
      || typeof entry.titleRu !== 'string'
      || typeof entry.author !== 'string'
      || typeof entry.authorRu !== 'string'
      || typeof entry.totalPages !== 'number') {
      throw new Error(`Invalid catalog entry: ${String(entry?.slug ?? '<unknown>')}`);
    }
  }
  return {
    schemaVersion: '1.0',
    generatedAt: typeof catalog.generatedAt === 'string' ? catalog.generatedAt : undefined,
    books: (catalog.books as BookSummary[]).map(normalizeBookSummary),
  };
}

function indexCatalog(catalog: RuntimeCatalog): Record<string, BookSummary> {
  return Object.fromEntries(catalog.books.map((book) => [book.slug, normalizeBookSummary(book)]));
}

function manifestFromSummary(summary: BookSummary): BookManifest {
  return {
    slug: summary.slug,
    releaseId: summary.releaseId,
    title: summary.title,
    titleRu: summary.titleRu,
    author: summary.author,
    authorRu: summary.authorRu,
    startPage: 1,
    endPage: summary.totalPages,
    totalPages: summary.totalPages,
    pagesIndexUrl: summary.pagesIndexUrl,
    searchIndexUrl: summary.searchIndexUrl,
    pageChunkPattern: summary.pageChunkPattern,
    manifestUrl: summary.manifestUrl,
    tableOfContents: [],
    pages: [],
  };
}

export const bookSummaries: Record<string, BookSummary> = indexCatalog(validateCatalog(bundledRuntimeCatalog));

export const registeredBooks: Record<string, BookManifest> = {
  'schreiner-ntt': {
    ...schreinerManifest,
    slug: 'schreiner-ntt',
  },
};

export const dynamicBookLoaders: Record<string, () => Promise<unknown>> = import.meta.glob(
  '../books/*/manifest.json',
  { import: 'default' },
);

const dynamicBookLoadersBySlug: Record<string, () => Promise<unknown>> = {};
for (const [path, loader] of Object.entries(dynamicBookLoaders)) {
  const match = path.match(/(?:^|\/)books\/([^/]+)\/manifest\.json$/);
  if (match && !dynamicBookLoadersBySlug[match[1]]) dynamicBookLoadersBySlug[match[1]] = loader;
}

let runtimeCatalogCache = validateCatalog(bundledRuntimeCatalog);

export class UnknownBookError extends Error {
  readonly slug: string;

  constructor(slug: string) {
    super(`Unknown book slug: ${slug}`);
    this.name = 'UnknownBookError';
    this.slug = slug;
    Object.setPrototypeOf(this, UnknownBookError.prototype);
  }
}

export class InvalidBookManifestError extends Error {
  readonly slug: string;

  constructor(slug: string) {
    super(`Invalid book manifest: ${slug}`);
    this.name = 'InvalidBookManifestError';
    this.slug = slug;
    Object.setPrototypeOf(this, InvalidBookManifestError.prototype);
  }
}

export class BookManifestLoadCancelledError extends Error {
  readonly slug: string;

  constructor(slug: string) {
    super(`Book manifest load cancelled: ${slug}`);
    this.name = 'BookManifestLoadCancelledError';
    this.slug = slug;
    Object.setPrototypeOf(this, BookManifestLoadCancelledError.prototype);
  }
}

export type BookManifestLoader = (
  slug: string,
  signal?: AbortSignal,
) => Promise<BookManifest>;

function assertNotAborted(slug: string, signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw new BookManifestLoadCancelledError(slug);
  }
}

function isBookManifest(value: unknown): value is BookManifest {
  if (!value || typeof value !== 'object') return false;
  const manifest = value as Partial<BookManifest>;
  return typeof manifest.slug === 'string'
    && typeof manifest.title === 'string'
    && typeof manifest.startPage === 'number'
    && typeof manifest.endPage === 'number'
    && typeof manifest.totalPages === 'number'
    && Array.isArray(manifest.pages)
    && Array.isArray(manifest.tableOfContents);
}

function hasConsistentManifestBounds(manifest: BookManifest, slug: string): boolean {
  if (manifest.slug !== slug || manifest.startPage > manifest.endPage || manifest.totalPages < 1) {
    return false;
  }
  if (manifest.pages.length === 0) {
    return true;
  }
  return manifest.pages.every((page) => (
    Boolean(page)
    && typeof page.pageNumber === 'number'
    && page.pageNumber >= manifest.startPage
    && page.pageNumber <= manifest.endPage
  )) && new Set(manifest.pages.map((page) => page.pageNumber)).size === manifest.pages.length;
}

function resolveCatalogEntry(slug: string): BookSummary | undefined {
  return runtimeCatalogCache.books.find((book) => book.slug === slug)
    ?? bundledRuntimeCatalog.books.find((book) => book.slug === slug)
    ?? bookSummaries[slug];
}

function resolveManifestUrl(slug: string): string | undefined {
  const entry = resolveCatalogEntry(slug);
  if (entry?.manifestUrl) return entry.manifestUrl;
  return undefined;
}

export async function loadRuntimeCatalog(signal?: AbortSignal): Promise<RuntimeCatalog> {
  if (signal?.aborted) {
    return runtimeCatalogCache;
  }

  try {
    const response = await fetch('/catalog.json', { signal });
    if (!response.ok) {
      throw new Error(`Failed to fetch catalog: ${response.status}`);
    }
    const catalog = validateCatalog(await response.json());
    runtimeCatalogCache = catalog;
    return catalog;
  } catch {
    runtimeCatalogCache = bundledRuntimeCatalog;
    return runtimeCatalogCache;
  }
}

export function getBookSummary(slug: string): BookSummary | undefined {
  const summary = resolveCatalogEntry(slug);
  if (summary) return summary;
  const manifest = registeredBooks[slug];
  if (manifest) {
    return {
      slug,
      title: manifest.title,
      titleRu: manifest.titleRu,
      author: manifest.author,
      authorRu: manifest.authorRu || manifest.author,
      totalPages: manifest.totalPages,
      releaseId: manifest.releaseId,
      pagesIndexUrl: manifest.pagesIndexUrl,
      searchIndexUrl: manifest.searchIndexUrl,
      pageChunkPattern: manifest.pageChunkPattern,
      manifestUrl: manifest.manifestUrl,
    };
  }
  return undefined;
}

export const loadBookManifest: BookManifestLoader = async (slug, signal) => {
  assertNotAborted(slug, signal);
  if (registeredBooks[slug]) {
    return registeredBooks[slug];
  }

  const manifestUrl = resolveManifestUrl(slug);
  const catalogEntry = getBookSummary(slug);
  if (manifestUrl) {
    const response = await fetch(manifestUrl, { signal });
    if (!response.ok) {
      throw new InvalidBookManifestError(slug);
    }
    assertNotAborted(slug, signal);
    const manifest = await response.json() as BookManifest;
    if (!isBookManifest(manifest) || !hasConsistentManifestBounds(manifest, slug)) {
      throw new InvalidBookManifestError(slug);
    }
    registeredBooks[slug] = manifest;
    return manifest;
  }

  if (catalogEntry) {
    const skeleton = manifestFromSummary(catalogEntry);
    registeredBooks[slug] = skeleton;
    return skeleton;
  }

  const loader = dynamicBookLoadersBySlug[slug];
  if (loader) {
    let module: unknown;
    try {
      module = await loader();
    } catch (error) {
      if (signal?.aborted) throw new BookManifestLoadCancelledError(slug);
      throw error;
    }
    assertNotAborted(slug, signal);
    const manifest = module && typeof module === 'object' && 'default' in module
      ? (module as Record<string, unknown>).default
      : module;
    if (!isBookManifest(manifest) || !hasConsistentManifestBounds(manifest, slug)) {
      throw new InvalidBookManifestError(slug);
    }
    registeredBooks[slug] = manifest;
    return manifest;
  }

  throw new UnknownBookError(slug);
};

export function getBookManifest(slug?: string): BookManifest {
  if (slug && registeredBooks[slug]) {
    return registeredBooks[slug];
  }

  if (slug) {
    const summary = getBookSummary(slug);
    if (summary) {
      return manifestFromSummary(summary);
    }
  }

  if (!slug) return registeredBooks['schreiner-ntt'];
  throw new UnknownBookError(slug);
}

export function getAllBooksSummary(): BookSummary[] {
  return runtimeCatalogCache.books.map(normalizeBookSummary);
}
