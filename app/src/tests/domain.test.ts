import { describe, it, expect } from 'vitest';
import { clampPage, getNextPage, getPrevPage, canGoNext, canGoPrev } from '../domain/pagination';
import { countWords, estimatePageReadingMinutes, calculateProgress } from '../domain/progress';
import { searchPages } from '../domain/searchEngine';
import { validateSettings, DEFAULT_SETTINGS } from '../domain/settings';
import { LocalStorageService } from '../infrastructure/storage';
import type { PageData } from '../domain/types';

describe('Domain: Pagination Logic', () => {
  it('clamps page numbers strictly within bounds', () => {
    expect(clampPage(850, 867, 888)).toBe(867);
    expect(clampPage(900, 867, 888)).toBe(888);
    expect(clampPage(875, 867, 888)).toBe(875);
    expect(clampPage(Number.NaN, 867, 888)).toBe(867);
  });

  it('correctly increments and respects page boundaries', () => {
    expect(canGoNext(867, 888)).toBe(true);
    expect(canGoNext(888, 888)).toBe(false);
    expect(getNextPage(867, 888)).toBe(868);
    expect(getNextPage(888, 888)).toBe(888);
  });

  it('correctly decrements and respects min boundaries', () => {
    expect(canGoPrev(867, 867)).toBe(false);
    expect(canGoPrev(870, 867)).toBe(true);
    expect(getPrevPage(870, 867)).toBe(869);
    expect(getPrevPage(867, 867)).toBe(867);
  });
});

describe('Domain: Reading Progress and Estimation', () => {
  it('counts words accurately for both English and Russian', () => {
    expect(countWords('')).toBe(0);
    expect(countWords('   ')).toBe(0);
    expect(countWords('Biblical theology is essential.')).toBe(4);
    expect(countWords('Библейское богословие имеет ключевое значение.')).toBe(5);
  });

  it('estimates page reading minutes with reasonable minimums', () => {
    expect(estimatePageReadingMinutes('')).toBe(1);
    const shortText = 'One two three four five';
    expect(estimatePageReadingMinutes(shortText)).toBe(1);
    const longText = new Array(360).fill('слово').join(' ');
    expect(estimatePageReadingMinutes(longText, 180)).toBe(2);
  });

  it('computes reading progress percent and remaining time', () => {
    const mockPages: PageData[] = [
      {
        pageNumber: 867,
        paragraphs: [{ id: '1', en: 'A B C', ru: 'А Б В' }],
        footnotes: [],
        imageSrc: '/scans/page_867.webp',
        translatedRu: 'А Б В',
      },
      {
        pageNumber: 868,
        paragraphs: [{ id: '2', en: 'D E F', ru: 'Г Д Е' }],
        footnotes: [],
        imageSrc: '/scans/page_868.webp',
        translatedRu: 'Г Д Е',
      },
    ];

    const progress1 = calculateProgress(867, mockPages);
    expect(progress1.percent).toBe(50);
    expect(progress1.totalPages).toBe(2);

    const progress2 = calculateProgress(868, mockPages);
    expect(progress2.percent).toBe(100);
  });
});

describe('Domain: Multilingual Search Engine', () => {
  const mockPages: PageData[] = [
    {
      pageNumber: 867,
      chapterTitle: 'Введение',
      paragraphs: [
        {
          id: 'p-1',
          en: 'In one sense, the discipline of biblical theology is old.',
          ru: 'В определенном смысле дисциплина библейского богословия стара.',
        },
      ],
      footnotes: [
        {
          id: 1,
          textEn: 'See Hengel 1994.',
          textRu: 'См.: Hengel 1994.',
        },
      ],
      imageSrc: '/scans/page_867.webp',
    },
    {
      pageNumber: 868,
      paragraphs: [
        {
          id: 'p-2',
          en: 'Johann Philip Gabler delivered his famous 1787 address.',
          ru: 'Иоганн Филипп Габлер произнес свою знаменитую речь в 1787 году.',
        },
      ],
      footnotes: [],
      imageSrc: '/scans/page_868.webp',
    },
  ];

  it('returns empty array for empty or too short query', () => {
    expect(searchPages(mockPages, '')).toEqual([]);
    expect(searchPages(mockPages, 'a')).toEqual([]);
  });

  it('finds Russian theological terms case-insensitively', () => {
    const matches = searchPages(mockPages, 'библейского');
    expect(matches.length).toBe(1);
    expect(matches[0].pageNumber).toBe(867);
    expect(matches[0].language).toBe('ru');
    expect(matches[0].snippetMatch).toBe('библейского');
  });

  it('finds English terms and properly marks language', () => {
    const matches = searchPages(mockPages, 'Gabler');
    expect(matches.length).toBe(1);
    expect(matches[0].pageNumber).toBe(868);
    expect(matches[0].language).toBe('en');
    expect(matches[0].snippetMatch).toBe('Gabler');
  });

  it('searches within footnotes', () => {
    const matches = searchPages(mockPages, 'Hengel');
    expect(matches.length).toBe(2); // One in EN footnote, one in RU footnote
    expect(matches[0].paragraphId).toBe('fn-1');
  });
});

describe('Domain: Reader Settings & Validation', () => {
  it('validates and clamps invalid settings to safe defaults', () => {
    const validated = validateSettings({
      fontSize: 999, // too large
      lineHeight: 0.1, // too small
      theme: 'invalid-theme' as any,
    });

    expect(validated.fontSize).toBe(28);
    expect(validated.lineHeight).toBe(1.4);
    expect(validated.theme).toBe(DEFAULT_SETTINGS.theme);
  });

  it('accepts custom valid settings', () => {
    const validated = validateSettings({
      fontSize: 20,
      theme: 'oled',
      mode: 'bilingual',
      fontFamily: 'sans',
    });

    expect(validated.fontSize).toBe(20);
    expect(validated.theme).toBe('oled');
    expect(validated.mode).toBe('bilingual');
    expect(validated.fontFamily).toBe('sans');
  });
});

describe('Infrastructure: Storage Adapter', () => {
  it('persists and retrieves settings correctly', () => {
    const storage = new LocalStorageService();
    storage.saveSettings({
      ...DEFAULT_SETTINGS,
      theme: 'dark',
      fontSize: 22,
    });

    const loaded = storage.getSettings();
    expect(loaded.theme).toBe('dark');
    expect(loaded.fontSize).toBe(22);
  });

  it('toggles bookmarks and keeps them sorted without duplicates', () => {
    const storage = new LocalStorageService();
    expect(storage.getBookmarks()).toEqual([]);

    storage.toggleBookmark(875);
    storage.toggleBookmark(868);
    expect(storage.getBookmarks()).toEqual([868, 875]);

    storage.toggleBookmark(875);
    expect(storage.getBookmarks()).toEqual([868]);
  });
});
