/**
 * Storage adapter with namespaced V2 persistence, legacy V1 fallback, and automatic migration
 */
import type { ReaderSettings, ResearchCard } from '../domain/types';
import {
  StorageServiceV2,
  migrateLegacyStorage,
  MemoryStorageBackend,
} from '../domain/storage/storageV2';
import type { ResearchCardV2 } from '../domain/v2/types';

export interface IStorageService {
  getSettings(): ReaderSettings;
  saveSettings(settings: ReaderSettings): void;
  getLastPage(defaultPage: number, bookSlug?: string): number;
  saveLastPage(page: number, bookSlug?: string): void;
  getBookmarks(bookSlug?: string): number[];
  toggleBookmark(page: number, bookSlug?: string): number[];
  getCards(bookSlug?: string): ResearchCard[];
  saveCards(cards: ResearchCard[], bookSlug?: string): void;
  addCard(card: ResearchCard, bookSlug?: string): ResearchCard[];
  updateCard(id: string, updates: Partial<ResearchCard>, bookSlug?: string): ResearchCard[];
  deleteCard(id: string, bookSlug?: string): ResearchCard[];
}

export class LocalStorageService implements IStorageService {
  private backend: Storage;
  public v2: StorageServiceV2;

  constructor(backend?: Storage) {
    if (backend) {
      this.backend = backend;
    } else if (typeof window !== 'undefined' && window.localStorage) {
      this.backend = window.localStorage;
    } else {
      this.backend = new MemoryStorageBackend();
    }
    this.v2 = new StorageServiceV2(this.backend);

    // Automatically trigger idempotent migration
    migrateLegacyStorage(this.backend);
  }

  getSettings(): ReaderSettings {
    return this.v2.getSettings();
  }

  saveSettings(settings: ReaderSettings): void {
    this.v2.saveSettings(settings);
  }

  getLastPage(defaultPage: number, bookSlug = 'schreiner-ntt'): number {
    const loc = this.v2.getLastLocation(bookSlug, {
      bookSlug,
      pageNumber: defaultPage,
    });
    return loc.pageNumber;
  }

  saveLastPage(page: number, bookSlug = 'schreiner-ntt'): void {
    this.v2.saveLastLocation(bookSlug, {
      bookSlug,
      pageNumber: page,
    });
  }

  getBookmarks(bookSlug = 'schreiner-ntt'): number[] {
    return this.v2.getBookmarks(bookSlug);
  }

  toggleBookmark(page: number, bookSlug = 'schreiner-ntt'): number[] {
    return this.v2.toggleBookmark(bookSlug, page);
  }

  getCards(bookSlug = 'schreiner-ntt'): ResearchCard[] {
    const cardsV2 = this.v2.getCards(bookSlug);
    return cardsV2 as ResearchCard[];
  }

  saveCards(cards: ResearchCard[], bookSlug = 'schreiner-ntt'): void {
    this.v2.saveCards(bookSlug, cards as ResearchCardV2[]);
  }

  addCard(card: ResearchCard, bookSlug = 'schreiner-ntt'): ResearchCard[] {
    const cardV2: ResearchCardV2 = {
      ...card,
      bookSlug,
    };
    const updated = this.v2.addCard(bookSlug, cardV2);
    return updated as ResearchCard[];
  }

  updateCard(id: string, updates: Partial<ResearchCard>, bookSlug = 'schreiner-ntt'): ResearchCard[] {
    const updated = this.v2.updateCard(bookSlug, id, updates as Partial<ResearchCardV2>);
    return updated as ResearchCard[];
  }

  deleteCard(id: string, bookSlug = 'schreiner-ntt'): ResearchCard[] {
    const updated = this.v2.deleteCard(bookSlug, id);
    return updated as ResearchCard[];
  }
}

export const defaultStorage = new LocalStorageService();
