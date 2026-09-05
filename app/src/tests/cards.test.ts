import { describe, it, expect, beforeEach } from 'vitest';
import {
  createResearchCard,
  filterResearchCards,
  formatAcademicCitation,
  exportCardsToMarkdown,
} from '../domain/cards';
import { LocalStorageService } from '../infrastructure/storage';
import type { ResearchCard } from '../domain/types';

describe('Research Cards Domain Logic', () => {
  it('creates a valid research card with defaults', () => {
    const card = createResearchCard({
      pageNumber: 870,
      quote: 'The kingdom of God is already and not yet.',
      note: 'Key tension in NT theology',
    });

    expect(card.id).toBeDefined();
    expect(card.pageNumber).toBe(870);
    expect(card.quote).toBe('The kingdom of God is already and not yet.');
    expect(card.note).toBe('Key tension in NT theology');
    expect(card.tag).toBe('thought');
    expect(card.color).toBe('amber');
    expect(card.createdAt).toBeDefined();
  });

  it('filters cards by tag, page, and search query', () => {
    const cards: ResearchCard[] = [
      createResearchCard({
        pageNumber: 868,
        quote: 'Библейское богословие носит описательный характер.',
        note: 'Определение Габлера',
        tag: 'thesis',
        quoteLanguage: 'ru',
      }),
      createResearchCard({
        pageNumber: 871,
        quote: 'Pauline theology centers on justification.',
        note: 'Argument to compare with Sanders',
        tag: 'for-paper',
        quoteLanguage: 'en',
      }),
      createResearchCard({
        pageNumber: 868,
        quote: 'История спасения как нарративная рамка.',
        note: 'Шрайнер подчеркивает нарратив',
        tag: 'theology',
        quoteLanguage: 'ru',
      }),
    ];

    // Filter by tag
    const thesisOnly = filterResearchCards(cards, { tag: 'thesis' });
    expect(thesisOnly.length).toBe(1);
    expect(thesisOnly[0].tag).toBe('thesis');

    // Filter by page
    const page868Only = filterResearchCards(cards, { pageNumber: 868 });
    expect(page868Only.length).toBe(2);

    // Search query
    const searched = filterResearchCards(cards, { query: 'Габлера' });
    expect(searched.length).toBe(1);
    expect(searched[0].note).toContain('Габлера');

    // Search query matching quote
    const searchedQuote = filterResearchCards(cards, { query: 'Pauline' });
    expect(searchedQuote.length).toBe(1);
  });

  it('formats academic citations in Russian and English', () => {
    const ruCard = createResearchCard({
      pageNumber: 875,
      quote: 'Центральная тема Нового Завета — слава Бога во Христе.',
      note: 'Главный тезис Шрайнера',
      quoteLanguage: 'ru',
    });

    const citationRu = formatAcademicCitation(ruCard);
    expect(citationRu).toContain('«Центральная тема Нового Завета — слава Бога во Христе.»');
    expect(citationRu).toContain('Шрайнер Т.');
    expect(citationRu).toContain('С. 875.');

    const enCard = createResearchCard({
      pageNumber: 875,
      quote: 'The central theme of the NT is magnifying God in Christ.',
      note: 'Main thesis',
      quoteLanguage: 'en',
    });

    const citationEn = formatAcademicCitation(enCard);
    expect(citationEn).toContain('"The central theme of the NT is magnifying God in Christ."');
    expect(citationEn).toContain('Schreiner, Thomas R.');
    expect(citationEn).toContain('P. 875.');
  });

  it('exports cards to structured markdown format', () => {
    const cards = [
      createResearchCard({
        pageNumber: 869,
        quote: 'Богословие не может быть оторвано от экзегезы.',
        note: 'Использовать во введении дипломной работы',
        tag: 'for-paper',
      }),
    ];

    const md = exportCardsToMarkdown(cards);
    expect(md).toContain('# Академические выписки и карточки мыслей');
    expect(md).toContain('Томас Р. Шрайнер');
    expect(md).toContain('Стр. 869');
    expect(md).toContain('Для статьи / работы');
    expect(md).toContain('Использовать во введении дипломной работы');
  });
});

describe('Cards Storage Adapter', () => {
  let storage: LocalStorageService;

  beforeEach(() => {
    storage = new LocalStorageService();
  });

  it('adds, updates, and deletes cards cleanly', () => {
    expect(storage.getCards()).toEqual([]);

    const card = createResearchCard({
      pageNumber: 870,
      quote: 'Тестовая цитата',
      note: 'Тестовая мысль',
    });

    const updatedList = storage.addCard(card);
    expect(updatedList.length).toBe(1);
    expect(storage.getCards().length).toBe(1);

    // Update
    storage.updateCard(card.id, { note: 'Обновленная мысль' });
    const fetched = storage.getCards()[0];
    expect(fetched.note).toBe('Обновленная мысль');

    // Delete
    const afterDelete = storage.deleteCard(card.id);
    expect(afterDelete.length).toBe(0);
    expect(storage.getCards().length).toBe(0);
  });
});
