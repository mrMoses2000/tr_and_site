import { describe, it, expect } from 'vitest';
import { bookManifest as schreinerManifest } from '../data/bookManifest';
import { adaptManifestV1ToV2, validateManifestV2, isManifestV2 } from '../domain/v2/adapter';

describe('Phase P1: V2 Contracts & Adapter (Test-First)', () => {
  it('adapts Schreiner ManifestV1 to BookManifestV2 with correct capabilities', () => {
    const v2 = adaptManifestV1ToV2(schreinerManifest);

    expect(v2.schemaVersion).toBe('2.0');
    expect(v2.slug).toBe('schreiner-ntt');
    expect(v2.sourceLanguage).toBe('en');
    // Schreiner has distinct EN original and RU translation
    expect(v2.availableLanguages).toContain('en');
    expect(v2.availableLanguages).toContain('ru');
    expect(v2.availableViews).toEqual(['adapted', 'scan', 'compare']);

    expect(v2.citation.shortTitle).toBeTruthy();
    expect(v2.citation.publisher).toBe('Baker Academic');
    expect(v2.contributors.length).toBeGreaterThan(0);
    expect(v2.contributors[0].role).toBe('author');
  });

  it('correctly sets single-language capability for Russian original without false English', () => {
    const osborneLikeV1 = {
      slug: 'ozborn-spiral',
      title: 'Герменевтическая спираль',
      titleRu: 'Герменевтическая спираль',
      author: 'Грант Р. Осборн',
      authorRu: 'Грант Р. Осборн',
      publisher: 'ЕААА, 2015',
      sourceLanguage: 'ru',
      targetLanguage: 'original',
      startPage: 1,
      endPage: 10,
      totalPages: 10,
      tableOfContents: [
        { pageNumber: 1, titleRu: 'Предисловие', titleEn: 'Предисловие', level: 1 }
      ],
      pages: [
        {
          pageNumber: 1,
          chapterTitle: 'Предисловие',
          paragraphs: [
            { id: 'p-1-1', ru: 'Текст на русском языке', en: 'Текст на русском языке' }
          ],
          footnotes: [],
          imageSrc: '/scans/ozborn-spiral/page_1.webp'
        }
      ]
    };

    const v2 = adaptManifestV1ToV2(osborneLikeV1 as any);

    expect(v2.schemaVersion).toBe('2.0');
    expect(v2.sourceLanguage).toBe('ru');
    // Must NOT claim English is available when both columns are Russian original!
    expect(v2.availableLanguages).toEqual(['ru']);
    expect(v2.title['ru']).toBe('Герменевтическая спираль');
  });

  it('generates deterministic and stable block IDs across adaptation runs', () => {
    const v2_first = adaptManifestV1ToV2(schreinerManifest);
    const v2_second = adaptManifestV1ToV2(schreinerManifest);

    expect(v2_first.releaseId).toBe(v2_second.releaseId);
    expect(v2_first.pages[0].blocks[0].id).toBe(v2_second.pages[0].blocks[0].id);
    expect(v2_first.pages[0].blocks[0].id).toMatch(/^blk-schreiner-ntt-p867-/);
  });

  it('attaches verifiable source anchors to every block run', () => {
    const v2 = adaptManifestV1ToV2(schreinerManifest);
    const firstBlock = v2.pages[0].blocks[0];

    expect(firstBlock.type).toBe('paragraph');
    if (firstBlock.type === 'paragraph') {
      expect(firstBlock.runs.length).toBeGreaterThan(0);
      const run = firstBlock.runs[0];
      expect(run.source).toBeDefined();
      expect(run.source.pdfPageIndex).toBe(867);
      expect(run.source.extractionMethod).toBe('native');
      expect(run.source.candidateHash).toBeTruthy();
    }
  });

  it('rejects invalid or tampered ManifestV2 schemas', () => {
    // Missing schemaVersion
    expect(() => validateManifestV2({ slug: 'test' } as any)).toThrow(/schemaVersion/i);

    // Wrong schemaVersion
    expect(() => validateManifestV2({ schemaVersion: '1.0', slug: 'test' } as any)).toThrow(/unsupported schemaVersion/i);

    // Inverted pageRange
    expect(() => validateManifestV2({
      schemaVersion: '2.0',
      slug: 'test',
      releaseId: 'rel-1',
      sourceRevision: 'rev-1',
      title: { ru: 'Title' },
      contributors: [],
      citation: { shortTitle: 'T' },
      sourceLanguage: 'ru',
      availableLanguages: ['ru'],
      availableViews: ['adapted'],
      pageRange: { start: 10, end: 5 },
      assets: {},
      toc: [],
      pagesIndexUrl: '/pages',
      pages: []
    })).toThrow(/pageRange/i);
  });

  it('identifies V2 manifest via isManifestV2 type guard', () => {
    const v2 = adaptManifestV1ToV2(schreinerManifest);
    expect(isManifestV2(v2)).toBe(true);
    expect(isManifestV2(schreinerManifest)).toBe(false);
    expect(isManifestV2(null)).toBe(false);
  });
});
