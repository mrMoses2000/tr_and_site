import { describe, it, expect, beforeEach } from 'vitest';
import {
  StorageServiceV2,
  migrateLegacyStorage,
  V2_KEYS,
  type ReaderLocationV2,
} from '../domain/storage/storageV2';
import {
  formatAcademicCitationV2,
  exportCardsToMarkdownV2,
  extractBookCitationMetadata,
  type BookCitationMetadata,
} from '../domain/citation';
import {
  parseReaderLocation,
  serializeReaderLocation,
  resolveAndValidateLocation,
} from '../domain/router';
import type { ResearchCardV2 } from '../domain/v2/types';
import type { BookManifest } from '../domain/types';

describe('Phase P7: Reader Storage V2 & Cross-Book Isolation', () => {
  let backend: Storage;
  let storage: StorageServiceV2;

  beforeEach(() => {
    backend = new (class implements Storage {
      private store: Record<string, string> = {};
      get length() { return Object.keys(this.store).length; }
      clear() { this.store = {}; }
      getItem(key: string) { return this.store[key] ?? null; }
      key(i: number) { return Object.keys(this.store)[i] ?? null; }
      removeItem(key: string) { delete this.store[key]; }
      setItem(key: string, val: string) { this.store[key] = val; }
    })();
    storage = new StorageServiceV2(backend);
  });

  it('isolates reading progress, bookmarks, and cards between different books on identical page numbers', () => {
    const bookA = 'schreiner-ntt';
    const bookB = 'ozborn-germenevticheskaya-spiral';
    const sharedPageNumber = 870;

    // Set Book A location and bookmarks
    storage.saveLastLocation(bookA, { bookSlug: bookA, pageNumber: sharedPageNumber });
    storage.toggleBookmark(bookA, sharedPageNumber);

    // Set Book B location and bookmarks on the same page number
    storage.saveLastLocation(bookB, { bookSlug: bookB, pageNumber: 50 });
    storage.toggleBookmark(bookB, 50);

    // Assert Book A state is preserved and not polluted by Book B
    const locA = storage.getLastLocation(bookA, { bookSlug: bookA, pageNumber: 867 });
    expect(locA.pageNumber).toBe(sharedPageNumber);
    expect(storage.getBookmarks(bookA)).toEqual([sharedPageNumber]);

    // Assert Book B state is preserved and not polluted by Book A
    const locB = storage.getLastLocation(bookB, { bookSlug: bookB, pageNumber: 1 });
    expect(locB.pageNumber).toBe(50);
    expect(storage.getBookmarks(bookB)).toEqual([50]);

    // Add cards with same page number in Book A vs Book B
    const cardA: ResearchCardV2 = {
      id: 'card-a-1',
      bookSlug: bookA,
      pageNumber: sharedPageNumber,
      quote: 'Quote from Schreiner',
      quoteLanguage: 'en',
      note: 'Note for Schreiner',
      tag: 'theology',
      color: 'amber',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    const cardB: ResearchCardV2 = {
      id: 'card-b-1',
      bookSlug: bookB,
      pageNumber: sharedPageNumber,
      quote: 'Quote from Osborne',
      quoteLanguage: 'ru',
      note: 'Note for Osborne',
      tag: 'thesis',
      color: 'blue',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    storage.addCard(bookA, cardA);
    storage.addCard(bookB, cardB);

    const cardsA = storage.getCards(bookA);
    const cardsB = storage.getCards(bookB);

    expect(cardsA.length).toBe(1);
    expect(cardsA[0].quote).toBe('Quote from Schreiner');
    expect(cardsA[0].bookSlug).toBe(bookA);

    expect(cardsB.length).toBe(1);
    expect(cardsB[0].quote).toBe('Quote from Osborne');
    expect(cardsB[0].bookSlug).toBe(bookB);
  });

  it('performs idempotent legacy migration from v1 keys into v2 namespaced storage', () => {
    // Setup legacy V1 keys
    backend.setItem('theology_reader_settings_v1', JSON.stringify({
      fontSize: 22,
      lineHeight: 1.8,
      maxWidth: 800,
      theme: 'dark',
      fontFamily: 'serif',
      mode: 'bilingual',
      showDropCap: false,
      showScanModal: false,
    }));
    backend.setItem('theology_reader_last_page_v1', '875');
    backend.setItem('theology_reader_bookmarks_v1', JSON.stringify([867, 875]));
    backend.setItem('theology_reader_cards_v1', JSON.stringify([
      {
        id: 'legacy-schreiner-card',
        pageNumber: 875,
        quote: 'Шрайнер подчеркивает нарративную рамку спасения.',
        note: 'Заметка об экзегезе Шрайнера',
        tag: 'theology',
        color: 'emerald',
        createdAt: '2026-09-01T10:00:00.000Z',
        updatedAt: '2026-09-01T10:00:00.000Z',
      },
      {
        id: 'legacy-ambiguous-card',
        pageNumber: 12,
        quote: 'Некая цитата без указания книги или автора',
        note: 'Неизвестный источник',
        tag: 'thought',
        color: 'amber',
        createdAt: '2026-09-01T11:00:00.000Z',
        updatedAt: '2026-09-01T11:00:00.000Z',
      }
    ]));

    // Run migration
    const result = migrateLegacyStorage(backend);
    expect(result.migrated).toBe(true);

    // Verify settings migrated to global v2
    const settings = storage.getSettings();
    expect(settings.fontSize).toBe(22);
    expect(settings.theme).toBe('dark');

    // Verify schreiner-ntt received bookmarks and last page
    expect(storage.getLastLocation('schreiner-ntt', { bookSlug: 'schreiner-ntt', pageNumber: 867 }).pageNumber).toBe(875);
    expect(storage.getBookmarks('schreiner-ntt')).toEqual([867, 875]);

    // Verify proven card attached to schreiner-ntt
    const schreinerCards = storage.getCards('schreiner-ntt');
    expect(schreinerCards.length).toBe(1);
    expect(schreinerCards[0].id).toBe('legacy-schreiner-card');
    expect(schreinerCards[0].bookSlug).toBe('schreiner-ntt');

    // Verify ambiguous card routed to legacy unassigned bucket without loss
    const rawUnassigned = backend.getItem(V2_KEYS.legacyUnassigned);
    expect(rawUnassigned).not.toBeNull();
    const unassigned = JSON.parse(rawUnassigned!);
    expect(unassigned.length).toBe(1);
    expect(unassigned[0].id).toBe('legacy-ambiguous-card');

    // Verify migration record flag is saved
    expect(backend.getItem(V2_KEYS.migrationMeta)).toContain('"version":2');

    // Verify idempotency: running migration second time doesn't duplicate or throw
    const secondResult = migrateLegacyStorage(backend);
    expect(secondResult.migrated).toBe(false);
    expect(secondResult.alreadyMigrated).toBe(true);
    expect(storage.getCards('schreiner-ntt').length).toBe(1);
  });
});

describe('Phase P7: Dynamic Citations per Book & Release', () => {
  const schreinerMetadata: BookCitationMetadata = {
    shortTitle: 'Богословие Нового Завета',
    author: 'Томас Р. Шрайнер',
    title: 'Богословие Нового Завета: возвеличивание Бога во Христе',
    subtitle: 'Приложение: Размышления о богословии Нового Завета',
    publisher: 'Одесса: Тюльпан',
    year: '2011',
    edition: '1-е изд.',
  };

  const osborneMetadata: BookCitationMetadata = {
    shortTitle: 'Герменевтическая спираль',
    author: 'Грант Р. Осборн',
    title: 'Герменевтическая спираль',
    subtitle: 'Общее введение в библейское толкование',
    publisher: 'Одесса: Евро-Азиатская Аккредитационная Ассоциация',
    year: '2015',
  };

  it('formats citations dynamically without hardcoded authors or titles', () => {
    const cardSchreiner: ResearchCardV2 = {
      id: 'c1',
      bookSlug: 'schreiner-ntt',
      pageNumber: 870,
      quote: 'The kingdom is already and not yet.',
      quoteLanguage: 'en',
      note: 'Thesis',
      tag: 'thesis',
      color: 'amber',
      createdAt: '2026-09-05T00:00:00Z',
      updatedAt: '2026-09-05T00:00:00Z',
      citationSnapshot: schreinerMetadata,
    };

    const citationRu = formatAcademicCitationV2(cardSchreiner, 'ru');
    expect(citationRu).toContain('«The kingdom is already and not yet.»');
    expect(citationRu).toContain('Томас Р. Шрайнер');
    expect(citationRu).toContain('Богословие Нового Завета');
    expect(citationRu).toContain('С. 870');

    const cardOsborne: ResearchCardV2 = {
      id: 'c2',
      bookSlug: 'ozborn-germenevticheskaya-spiral',
      pageNumber: 54,
      quote: 'Контекст определяет значение слова.',
      quoteLanguage: 'ru',
      note: 'Семантическое правило',
      tag: 'quote',
      color: 'emerald',
      createdAt: '2026-09-05T00:00:00Z',
      updatedAt: '2026-09-05T00:00:00Z',
      citationSnapshot: osborneMetadata,
    };

    const citationOsborne = formatAcademicCitationV2(cardOsborne, 'ru');
    expect(citationOsborne).toContain('«Контекст определяет значение слова.»');
    expect(citationOsborne).toContain('Грант Р. Осборн');
    expect(citationOsborne).toContain('Герменевтическая спираль');
    expect(citationOsborne).toContain('С. 54');
    expect(citationOsborne).not.toContain('Шрайнер');
  });

  it('exports cards to Markdown grouped and attributed per book citation metadata', () => {
    const cards: ResearchCardV2[] = [
      {
        id: 'c-osborne',
        bookSlug: 'ozborn-germenevticheskaya-spiral',
        pageNumber: 15,
        quote: 'Библия обладает богодухновенным авторитетом.',
        quoteLanguage: 'ru',
        note: 'Ключевой постулат',
        tag: 'theology',
        color: 'purple',
        createdAt: '2026-09-05T00:00:00Z',
        updatedAt: '2026-09-05T00:00:00Z',
        citationSnapshot: osborneMetadata,
      },
    ];

    const md = exportCardsToMarkdownV2(cards, osborneMetadata);
    expect(md).toContain('# Академические выписки и карточки мыслей');
    expect(md).toContain('Грант Р. Осборн');
    expect(md).toContain('Герменевтическая спираль');
    expect(md).toContain('Стр. 15');
    expect(md).not.toContain('Шрайнер');
  });

  it('extracts citation metadata cleanly from BookManifest or BookManifestV2', () => {
    const manifest: Partial<BookManifest> = {
      titleRu: 'Герменевтическая спираль',
      subtitleRu: 'Общее введение в библейское толкование',
      authorRu: 'Грант Р. Осборн',
      publisher: 'ЕААА, 2015',
    };
    const meta = extractBookCitationMetadata(manifest as BookManifest);
    expect(meta.author).toBe('Грант Р. Осборн');
    expect(meta.title).toBe('Герменевтическая спираль');
  });
});

describe('Phase P7: Atomic Location Router & URL Hash Parser/Serializer', () => {
  const dummyManifests: Record<string, { startPage: number; endPage: number }> = {
    'schreiner-ntt': { startPage: 867, endPage: 888 },
    'ozborn-germenevticheskaya-spiral': { startPage: 1, endPage: 736 },
  };

  const resolver = (slug: string) => dummyManifests[slug] || null;

  it('parses reader locations from full and legacy hash strings', () => {
    // Full v2 hash
    const loc1 = parseReaderLocation('#book=ozborn-germenevticheskaya-spiral&page=54&view=compare&mode=bilingual&block=blk-12&fn=3');
    expect(loc1).toEqual({
      bookSlug: 'ozborn-germenevticheskaya-spiral',
      pageNumber: 54,
      view: 'compare',
      mode: 'bilingual',
      blockId: 'blk-12',
      footnoteId: '3',
    });

    // Short / legacy hash
    const loc2 = parseReaderLocation('#page=870', 'schreiner-ntt');
    expect(loc2.bookSlug).toBe('schreiner-ntt');
    expect(loc2.pageNumber).toBe(870);

    // Empty or catalog hash
    const loc3 = parseReaderLocation('#catalog');
    expect(loc3.bookSlug).toBe('');
    expect(loc3.view).toBe('catalog');
  });

  it('serializes reader locations into standard hash strings', () => {
    const hash = serializeReaderLocation({
      bookSlug: 'ozborn-germenevticheskaya-spiral',
      pageNumber: 54,
      view: 'adapted',
      mode: 'ru',
      blockId: 'blk-54-1',
    });
    expect(hash).toBe('#book=ozborn-germenevticheskaya-spiral&page=54&view=adapted&mode=ru&block=blk-54-1');
  });

  it('validates and clamps target page against target book bounds without using previous book bounds', () => {
    // Current book is Schreiner (867..888), target book is Osborne (1..736), target page is 50
    // In buggy version, 50 was clamped to 867 because it checked current book's bounds!
    const targetLoc: ReaderLocationV2 = {
      bookSlug: 'ozborn-germenevticheskaya-spiral',
      pageNumber: 50,
    };

    const resolved = resolveAndValidateLocation(targetLoc, resolver, 'schreiner-ntt', 870);
    expect(resolved.bookSlug).toBe('ozborn-germenevticheskaya-spiral');
    expect(resolved.pageNumber).toBe(50); // Valid in Osborne (1..736)

    // Now navigate to page 50 in Schreiner (invalid, must clamp to 867)
    const invalidSchreiner: ReaderLocationV2 = {
      bookSlug: 'schreiner-ntt',
      pageNumber: 50,
    };
    const resolvedSchreiner = resolveAndValidateLocation(invalidSchreiner, resolver, 'ozborn-germenevticheskaya-spiral', 50);
    expect(resolvedSchreiner.bookSlug).toBe('schreiner-ntt');
    expect(resolvedSchreiner.pageNumber).toBe(867); // Clamped to Schreiner min!

    // Navigate to page 9999 in Osborne (must clamp to 736)
    const outOfBoundsOsborne: ReaderLocationV2 = {
      bookSlug: 'ozborn-germenevticheskaya-spiral',
      pageNumber: 9999,
    };
    const resolvedOob = resolveAndValidateLocation(outOfBoundsOsborne, resolver);
    expect(resolvedOob.pageNumber).toBe(736);
  });
});
