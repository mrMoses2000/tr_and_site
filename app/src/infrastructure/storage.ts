/**
 * Storage adapter with fallback for test and non-browser environments
 */
import type { ReaderSettings, ResearchCard } from '../domain/types';
import { DEFAULT_SETTINGS, validateSettings } from '../domain/settings';

const SETTINGS_KEY = 'theology_reader_settings_v1';
const LAST_PAGE_KEY = 'theology_reader_last_page_v1';
const BOOKMARKS_KEY = 'theology_reader_bookmarks_v1';
const CARDS_KEY = 'theology_reader_cards_v1';

export interface IStorageService {
  getSettings(): ReaderSettings;
  saveSettings(settings: ReaderSettings): void;
  getLastPage(defaultPage: number): number;
  saveLastPage(page: number): void;
  getBookmarks(): number[];
  toggleBookmark(page: number): number[];
  getCards(): ResearchCard[];
  saveCards(cards: ResearchCard[]): void;
  addCard(card: ResearchCard): ResearchCard[];
  updateCard(id: string, updates: Partial<ResearchCard>): ResearchCard[];
  deleteCard(id: string): ResearchCard[];
}

class MemoryStorageBackend implements Storage {
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

export class LocalStorageService implements IStorageService {
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

  getSettings(): ReaderSettings {
    try {
      const raw = this.backend.getItem(SETTINGS_KEY);
      if (!raw) return DEFAULT_SETTINGS;
      const parsed = JSON.parse(raw);
      return validateSettings(parsed);
    } catch {
      return DEFAULT_SETTINGS;
    }
  }

  saveSettings(settings: ReaderSettings): void {
    try {
      this.backend.setItem(SETTINGS_KEY, JSON.stringify(settings));
    } catch {
      // Ignore quota errors gracefully
    }
  }

  getLastPage(defaultPage: number): number {
    try {
      const raw = this.backend.getItem(LAST_PAGE_KEY);
      if (!raw) return defaultPage;
      const parsed = parseInt(raw, 10);
      return Number.isNaN(parsed) ? defaultPage : parsed;
    } catch {
      return defaultPage;
    }
  }

  saveLastPage(page: number): void {
    try {
      this.backend.setItem(LAST_PAGE_KEY, page.toString());
    } catch {
      // Ignore errors
    }
  }

  getBookmarks(): number[] {
    try {
      const raw = this.backend.getItem(BOOKMARKS_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  toggleBookmark(page: number): number[] {
    const current = this.getBookmarks();
    const next = current.includes(page)
      ? current.filter(p => p !== page)
      : [...current, page].sort((a, b) => a - b);
    try {
      this.backend.setItem(BOOKMARKS_KEY, JSON.stringify(next));
    } catch {
      // Ignore
    }
    return next;
  }

  getCards(): ResearchCard[] {
    try {
      const raw = this.backend.getItem(CARDS_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  saveCards(cards: ResearchCard[]): void {
    try {
      this.backend.setItem(CARDS_KEY, JSON.stringify(cards));
    } catch {
      // Ignore quota errors
    }
  }

  addCard(card: ResearchCard): ResearchCard[] {
    const current = this.getCards();
    const next = [card, ...current];
    this.saveCards(next);
    return next;
  }

  updateCard(id: string, updates: Partial<ResearchCard>): ResearchCard[] {
    const current = this.getCards();
    const next = current.map(c => (c.id === id ? { ...c, ...updates, updatedAt: new Date().toISOString() } : c));
    this.saveCards(next);
    return next;
  }

  deleteCard(id: string): ResearchCard[] {
    const current = this.getCards();
    const next = current.filter(c => c.id !== id);
    this.saveCards(next);
    return next;
  }
}

export const defaultStorage = new LocalStorageService();
