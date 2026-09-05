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

// Base books
const baseBooks: Record<string, BookManifest> = {
  'schreiner-ntt': {
    ...schreinerManifest,
    slug: 'schreiner-ntt',
  },
};

// Dynamically discovered books from ../books/*/manifest.json
const dynamicBookModules = import.meta.glob<Record<string, any>>(
  '../books/*/manifest.json',
  { eager: true }
);

export const registeredBooks: Record<string, BookManifest> = { ...baseBooks };

for (const module of Object.values(dynamicBookModules)) {
  const manifest = (module as any).default || module;
  if (manifest && manifest.slug) {
    registeredBooks[manifest.slug] = manifest;
  }
}

export function getBookManifest(slug?: string): BookManifest {
  if (slug && registeredBooks[slug]) {
    return registeredBooks[slug];
  }
  return registeredBooks['schreiner-ntt'];
}

export function getAllBooksSummary(): BookSummary[] {
  return Object.values(registeredBooks).map(b => ({
    slug: b.slug || 'schreiner-ntt',
    title: b.title,
    titleRu: b.titleRu,
    author: b.author,
    authorRu: b.authorRu || b.author,
    totalPages: b.totalPages,
  }));
}
