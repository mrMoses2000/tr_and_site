import type { BookManifest } from '../../domain/types';
import { bookManifest as schreinerManifest } from '../bookManifest';

export interface BookSummary {
  slug: string;
  title: string;
  titleRu: string;
  author: string;
  authorRu: string;
  totalPages: number;
}

// Lightweight static summary registry for instant catalog load without 6MB bundle overhead
export const bookSummaries: Record<string, BookSummary> = {
  'schreiner-ntt': {
    slug: 'schreiner-ntt',
    title: schreinerManifest.title,
    titleRu: schreinerManifest.titleRu,
    author: schreinerManifest.author,
    authorRu: schreinerManifest.authorRu || schreinerManifest.author,
    totalPages: schreinerManifest.totalPages,
  },
  'ozborn-germenevticheskaya-spiral': {
    slug: 'ozborn-germenevticheskaya-spiral',
    title: 'Герменевтическая спираль',
    titleRu: 'Герменевтическая спираль',
    author: 'Grant R. Osborne',
    authorRu: 'Грант Р. Осборн',
    totalPages: 736,
  },
};

// Base in-memory manifest cache
export const registeredBooks: Record<string, BookManifest> = {
  'schreiner-ntt': {
    ...schreinerManifest,
    slug: 'schreiner-ntt',
  },
};

// Lazy dynamic chunk loaders for full book manifests
// Ask Vite for the JSON default directly. This keeps the loader contract stable
// across dev, Vitest, and production chunking (where module namespace shape can vary).
export const dynamicBookLoaders: Record<string, () => Promise<unknown>> = import.meta.glob(
  '../books/*/manifest.json',
  { import: 'default' },
);

const dynamicBookLoadersBySlug: Record<string, () => Promise<unknown>> = {};
for (const [path, loader] of Object.entries(dynamicBookLoaders)) {
  const match = path.match(/(?:^|\/)books\/([^/]+)\/manifest\.json$/);
  if (match && !dynamicBookLoadersBySlug[match[1]]) dynamicBookLoadersBySlug[match[1]] = loader;
}

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

// Compatibility loader: the current Osborne asset is one dynamic manifest,
// not true per-page chunks. Keep this explicit until a chunks index exists.

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
  return manifest.pages.every((page) => (
    Boolean(page)
    && typeof page.pageNumber === 'number'
    && page.pageNumber >= manifest.startPage
    && page.pageNumber <= manifest.endPage
  )) && new Set(manifest.pages.map((page) => page.pageNumber)).size === manifest.pages.length;
}

export const loadBookManifest: BookManifestLoader = async (slug, signal) => {
  assertNotAborted(slug, signal);
  if (registeredBooks[slug]) {
    return registeredBooks[slug];
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

  // If known in summary but not yet loaded into memory, return skeleton with accurate bounds
  if (slug && bookSummaries[slug]) {
    const sum = bookSummaries[slug];
    return {
      slug: sum.slug,
      title: sum.title,
      titleRu: sum.titleRu,
      author: sum.author,
      authorRu: sum.authorRu,
      startPage: 1,
      endPage: sum.totalPages,
      totalPages: sum.totalPages,
      tableOfContents: [],
      pages: [],
    };
  }

  if (!slug) return registeredBooks['schreiner-ntt'];
  throw new UnknownBookError(slug);
}

export function getAllBooksSummary(): BookSummary[] {
  return Object.values(bookSummaries);
}
