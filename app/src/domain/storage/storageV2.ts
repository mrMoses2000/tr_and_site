import type { ReaderSettings } from '../types';
import { DEFAULT_SETTINGS, validateSettings } from '../settings';
import type { ResearchCardV2 } from '../v2/types';

export interface ReaderLocationV2 {
  bookSlug: string;
  pageNumber: number;
  blockId?: string;
  footnoteId?: number | string;
  view?: 'adapted' | 'scan' | 'compare' | 'catalog';
  mode?: 'ru' | 'bilingual' | 'en';
}

export const V2_KEYS = {
  settings: 'logos.reader.settings.v2',
  lastLocation: (bookSlug: string) => `logos.reader.book.${bookSlug}.last-location.v2`,
  bookmarks: (bookSlug: string) => `logos.reader.book.${bookSlug}.bookmarks.v2`,
  cards: (bookSlug: string) => `logos.reader.book.${bookSlug}.cards.v2`,
  legacyUnassigned: 'logos.reader.legacy.unassigned',
  migrationMeta: 'logos.reader.migration.v2',
} as const;

export class MemoryStorageBackend implements Storage {
  private store: Record<string, string> = {};
  get length(): number {
    return Object.keys(this.store).length;
  }
  clear(): void {
    this.store = {};
  }
  getItem(key: string): string | null {
    return this.store[key] ?? null;
  }
  key(index: number): string | null {
    return Object.keys(this.store)[index] ?? null;
  }
  removeItem(key: string): void {
    delete this.store[key];
  }
  setItem(key: string, value: string): void {
    this.store[key] = value;
  }
}

export class StorageServiceV2 {
  private backend: Storage;

  constructor(backend?: Storage) {
    if (backend) {
      this.backend = backend;
    } else if (typeof window !== 'undefined' && window.localStorage) {
      this.backend = window.localStorage;
    } else {
      this.backend = new MemoryStorageBackend();
    }
  }

  // Global Settings
  getSettings(): ReaderSettings {
    try {
      const raw = this.backend.getItem(V2_KEYS.settings);
      if (!raw) {
        // Fallback to legacy settings key if not migrated yet
        const legacyRaw = this.backend.getItem('theology_reader_settings_v1');
        if (legacyRaw) {
          return validateSettings(JSON.parse(legacyRaw));
        }
        return DEFAULT_SETTINGS;
      }
      return validateSettings(JSON.parse(raw));
    } catch {
      return DEFAULT_SETTINGS;
    }
  }

  saveSettings(settings: ReaderSettings): void {
    try {
      this.backend.setItem(V2_KEYS.settings, JSON.stringify(settings));
    } catch {
      // Ignore quota errors
    }
  }

  // Per-book Last Location
  getLastLocation(bookSlug: string, defaultLoc: ReaderLocationV2): ReaderLocationV2 {
    try {
      const key = V2_KEYS.lastLocation(bookSlug);
      const raw = this.backend.getItem(key);
      if (!raw) return defaultLoc;
      const parsed = JSON.parse(raw);
      if (typeof parsed.pageNumber === 'number' && !Number.isNaN(parsed.pageNumber)) {
        return {
          ...defaultLoc,
          ...parsed,
          bookSlug,
        };
      }
      return defaultLoc;
    } catch {
      return defaultLoc;
    }
  }

  saveLastLocation(bookSlug: string, location: ReaderLocationV2): void {
    try {
      const key = V2_KEYS.lastLocation(bookSlug);
      this.backend.setItem(key, JSON.stringify(location));
    } catch {
      // Ignore errors
    }
  }

  // Per-book Bookmarks
  getBookmarks(bookSlug: string): number[] {
    try {
      const key = V2_KEYS.bookmarks(bookSlug);
      const raw = this.backend.getItem(key);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  saveBookmarks(bookSlug: string, bookmarks: number[]): void {
    try {
      const key = V2_KEYS.bookmarks(bookSlug);
      this.backend.setItem(key, JSON.stringify(bookmarks));
    } catch {
      // Ignore
    }
  }

  toggleBookmark(bookSlug: string, page: number): number[] {
    const current = this.getBookmarks(bookSlug);
    const next = current.includes(page)
      ? current.filter(p => p !== page)
      : [...current, page].sort((a, b) => a - b);
    this.saveBookmarks(bookSlug, next);
    return next;
  }

  // Per-book Research Cards
  getCards(bookSlug: string): ResearchCardV2[] {
    try {
      const key = V2_KEYS.cards(bookSlug);
      const raw = this.backend.getItem(key);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  saveCards(bookSlug: string, cards: ResearchCardV2[]): void {
    try {
      const key = V2_KEYS.cards(bookSlug);
      this.backend.setItem(key, JSON.stringify(cards));
    } catch {
      // Ignore
    }
  }

  addCard(bookSlug: string, card: ResearchCardV2): ResearchCardV2[] {
    const current = this.getCards(bookSlug);
    const cardWithBook: ResearchCardV2 = {
      ...card,
      bookSlug,
    };
    const next = [cardWithBook, ...current.filter(c => c.id !== card.id)];
    this.saveCards(bookSlug, next);
    return next;
  }

  updateCard(bookSlug: string, id: string, updates: Partial<ResearchCardV2>): ResearchCardV2[] {
    const current = this.getCards(bookSlug);
    const next = current.map(c =>
      c.id === id ? { ...c, ...updates, updatedAt: new Date().toISOString() } : c
    );
    this.saveCards(bookSlug, next);
    return next;
  }

  deleteCard(bookSlug: string, id: string): ResearchCardV2[] {
    const current = this.getCards(bookSlug);
    const next = current.filter(c => c.id !== id);
    this.saveCards(bookSlug, next);
    return next;
  }
}

export interface MigrationResult {
  migrated: boolean;
  alreadyMigrated: boolean;
  migratedCardsCount?: number;
  unassignedCardsCount?: number;
}

/**
 * Idempotent migration from v1 unnamespaced storage to v2 namespaced storage.
 * Per playbook rule:
 * - Executes once.
 * - Old cards bound to 'schreiner-ntt' only if stored metadata unequivocally proves the book.
 * - Ambiguous cards saved to logos.reader.legacy.unassigned.
 * - Old keys are not deleted until v2 is written and verified.
 */
export function migrateLegacyStorage(backend: Storage): MigrationResult {
  try {
    const existingMeta = backend.getItem(V2_KEYS.migrationMeta);
    if (existingMeta) {
      return { migrated: false, alreadyMigrated: true };
    }

    // 1. Settings migration
    const legacySettings = backend.getItem('theology_reader_settings_v1');
    if (legacySettings) {
      try {
        const parsed = JSON.parse(legacySettings);
        const valid = validateSettings(parsed);
        backend.setItem(V2_KEYS.settings, JSON.stringify(valid));
      } catch {
        // Fallback default
        backend.setItem(V2_KEYS.settings, JSON.stringify(DEFAULT_SETTINGS));
      }
    }

    // 2. Last page migration (bound to schreiner-ntt if within range)
    const legacyLastPage = backend.getItem('theology_reader_last_page_v1');
    if (legacyLastPage) {
      const pageNum = parseInt(legacyLastPage, 10);
      if (!Number.isNaN(pageNum)) {
        const loc: ReaderLocationV2 = {
          bookSlug: 'schreiner-ntt',
          pageNumber: pageNum,
        };
        backend.setItem(V2_KEYS.lastLocation('schreiner-ntt'), JSON.stringify(loc));
      }
    }

    // 3. Bookmarks migration
    const legacyBookmarks = backend.getItem('theology_reader_bookmarks_v1');
    if (legacyBookmarks) {
      try {
        const bookmarks = JSON.parse(legacyBookmarks);
        if (Array.isArray(bookmarks)) {
          backend.setItem(V2_KEYS.bookmarks('schreiner-ntt'), JSON.stringify(bookmarks));
        }
      } catch {
        // Ignore
      }
    }

    // 4. Cards migration
    let migratedCardsCount = 0;
    let unassignedCardsCount = 0;
    const legacyCardsRaw = backend.getItem('theology_reader_cards_v1');
    if (legacyCardsRaw) {
      try {
        const legacyCards = JSON.parse(legacyCardsRaw);
        if (Array.isArray(legacyCards)) {
          const schreinerCards: ResearchCardV2[] = [];
          const unassignedCards: any[] = [];

          const schreinerKeywords = [
            'шрайнер', 'schreiner',
            'богословие нового завета', 'new testament theology',
            'габлер', 'gabler',
            'размышления о богословии'
          ];

          for (const card of legacyCards) {
            const textToInspect = `${card.quote || ''} ${card.note || ''} ${card.citationSnapshot?.title || ''} ${card.citationSnapshot?.author || ''}`.toLowerCase();
            const hasSchreinerProof = schreinerKeywords.some(kw => textToInspect.includes(kw)) ||
              (card.bookSlug === 'schreiner-ntt');

            if (hasSchreinerProof) {
              schreinerCards.push({
                ...card,
                bookSlug: 'schreiner-ntt',
              });
            } else {
              // Ambiguous data preserved in legacy bucket
              unassignedCards.push(card);
            }
          }

          if (schreinerCards.length > 0) {
            backend.setItem(V2_KEYS.cards('schreiner-ntt'), JSON.stringify(schreinerCards));
            migratedCardsCount = schreinerCards.length;
          }

          if (unassignedCards.length > 0) {
            backend.setItem(V2_KEYS.legacyUnassigned, JSON.stringify(unassignedCards));
            unassignedCardsCount = unassignedCards.length;
          }
        }
      } catch {
        // Ignore
      }
    }

    // 5. Write migration metadata flag
    backend.setItem(V2_KEYS.migrationMeta, JSON.stringify({
      version: 2,
      migratedAt: new Date().toISOString(),
      migratedCardsCount,
      unassignedCardsCount,
    }));

    return {
      migrated: true,
      alreadyMigrated: false,
      migratedCardsCount,
      unassignedCardsCount,
    };
  } catch {
    return { migrated: false, alreadyMigrated: false };
  }
}
