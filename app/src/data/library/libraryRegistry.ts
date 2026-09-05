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
export const dynamicBookLoaders: Record<string, () => Promise<any>> = import.meta.glob<Record<string, any>>(
  '../books/*/manifest.json'
);

// In test environments, eagerly populate registeredBooks so synchronous tests run seamlessly
if (typeof import.meta !== 'undefined' && (import.meta as any).env?.MODE === 'test') {
  const eagerModules = import.meta.glob<Record<string, any>>(
    '../books/*/manifest.json',
    { eager: true }
  );
  for (const module of Object.values(eagerModules)) {
    const manifest = (module as any).default || module;
    if (manifest && manifest.slug) {
      registeredBooks[manifest.slug] = manifest;
    }
  }
}

export async function loadBookManifest(slug: string): Promise<BookManifest> {
  if (registeredBooks[slug]) {
    return registeredBooks[slug];
  }

  for (const [path, loader] of Object.entries(dynamicBookLoaders)) {
    if (path.includes(`/${slug}/`)) {
      const module = await loader();
      const manifest = module.default || module;
      registeredBooks[slug] = manifest;
      return manifest;
    }
  }

  return registeredBooks['schreiner-ntt'];
}

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

  return registeredBooks['schreiner-ntt'];
}

export function getAllBooksSummary(): BookSummary[] {
  return Object.values(bookSummaries);
}
