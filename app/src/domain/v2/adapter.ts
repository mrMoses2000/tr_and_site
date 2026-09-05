import type { BookManifest } from '../types';
import type {
  BookManifestV2,
  DocumentBlock,
  LanguageCode,
  PageV2,
  SourceAnchor,
  TocNode,
} from './types';

function fnv1a(str: string): string {
  let hash = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) {
    hash ^= str.charCodeAt(i);
    hash += (hash << 1) + (hash << 4) + (hash << 7) + (hash << 8) + (hash << 24);
  }
  return (hash >>> 0).toString(16).padStart(8, '0');
}

export function computeCandidateHash(text: string, pageIndex: number): string {
  return `cand-p${pageIndex}-${fnv1a(text)}`;
}

export function isManifestV2(val: unknown): val is BookManifestV2 {
  if (!val || typeof val !== 'object') {
    return false;
  }
  return (val as any).schemaVersion === '2.0';
}

export function validateManifestV2(manifest: unknown): BookManifestV2 {
  if (!manifest || typeof manifest !== 'object') {
    throw new Error('Invalid manifest: expected an object');
  }
  const m = manifest as Record<string, any>;
  if (!('schemaVersion' in m)) {
    throw new Error('Manifest missing required schemaVersion property');
  }
  if (m.schemaVersion !== '2.0') {
    throw new Error(`Unsupported schemaVersion: "${m.schemaVersion}". Expected "2.0".`);
  }
  if (m.pageRange) {
    const { start, end } = m.pageRange;
    if (typeof start === 'number' && typeof end === 'number' && start > end) {
      throw new Error(`Invalid pageRange: start (${start}) must be <= end (${end})`);
    }
  }
  return manifest as BookManifestV2;
}

export function adaptManifestV1ToV2(v1: BookManifest): BookManifestV2 {
  const slug =
    v1.slug ||
    (v1.author?.toLowerCase().includes('schreiner') || v1.title?.toLowerCase().includes('reflections')
      ? 'schreiner-ntt'
      : (v1.titleRu || v1.title || 'book')
          .toLowerCase()
          .replace(/[^a-zа-я0-9_-]/gi, '-')
          .replace(/-+/g, '-')
          .replace(/^-|-$/g, ''));

  const rawSourceLang = (v1 as any).sourceLanguage || (v1.authorRu && v1.author && v1.author !== v1.authorRu ? 'en' : 'ru');
  const sourceLanguage: LanguageCode = (['ru', 'en', 'kk', 'grc', 'he'].includes(rawSourceLang)
    ? rawSourceLang
    : 'ru') as LanguageCode;

  // Determine actual language capabilities:
  // If all paragraphs have identical Russian and English or empty English, it's single-language.
  let hasDistinctEn = false;
  if (v1.pages && Array.isArray(v1.pages)) {
    for (const page of v1.pages) {
      if (page.paragraphs) {
        for (const p of page.paragraphs) {
          if (p.en && p.ru && p.en.trim() !== p.ru.trim()) {
            hasDistinctEn = true;
            break;
          }
        }
      }
      if (hasDistinctEn) break;
    }
  }

  const availableLanguages: LanguageCode[] = hasDistinctEn
    ? ['en', 'ru']
    : [sourceLanguage];

  let publisherName = v1.publisher || '';
  let pubYear: string | undefined;
  if (publisherName.includes(',')) {
    const parts = publisherName.split(',');
    publisherName = parts[0].trim();
    pubYear = parts.slice(1).join(',').trim();
  }

  const contributors: Array<{ role: string; name: string; language?: string }> = [];
  if (v1.author) {
    contributors.push({
      role: 'author',
      name: v1.author,
      language: sourceLanguage,
    });
  }
  if (v1.authorRu && v1.authorRu !== v1.author) {
    contributors.push({
      role: 'translator',
      name: v1.authorRu,
      language: 'ru',
    });
  }

  const startPage = v1.startPage || 1;
  const endPage = v1.endPage || (v1.pages ? v1.pages.length : startPage);
  const totalPages = v1.totalPages || (endPage - startPage + 1);

  const releaseId = `rel-${slug}-p${startPage}-${totalPages}`;

  const pages: PageV2[] = (v1.pages || []).map((page) => {
    const blocks: DocumentBlock[] = [];

    (page.paragraphs || []).forEach((para, idx) => {
      const blockId = `blk-${slug}-p${page.pageNumber}-${idx}`;
      const text = para.ru || para.en || '';
      const anchor: SourceAnchor = {
        sourceSha256: 'sha256-v1-untracked-source',
        pdfPageIndex: page.pageNumber,
        extractionMethod: 'native',
        candidateHash: computeCandidateHash(text, page.pageNumber),
      };

      const block: DocumentBlock = {
        type: 'paragraph',
        id: blockId,
        runs: [
          {
            id: `${blockId}-r0`,
            text,
            language: 'ru',
            source: anchor,
          },
        ],
      };
      blocks.push(block);
    });

    (page.footnotes || []).forEach((fn) => {
      const fnId = `blk-${slug}-p${page.pageNumber}-fn-${fn.id}`;
      const fnText = fn.textRu || fn.textEn || '';
      const anchor: SourceAnchor = {
        sourceSha256: 'sha256-v1-untracked-source',
        pdfPageIndex: page.pageNumber,
        extractionMethod: 'native',
        candidateHash: computeCandidateHash(fnText, page.pageNumber),
      };

      const fnBlock: DocumentBlock = {
        type: 'footnote',
        id: fnId,
        label: String(fn.id),
        anchors: [`fnref-${fn.id}`],
        blocks: [
          {
            type: 'paragraph',
            id: `${fnId}-p`,
            runs: [
              {
                id: `${fnId}-r0`,
                text: fnText,
                language: 'ru',
                source: anchor,
              },
            ],
          },
        ],
      };
      blocks.push(fnBlock);
    });

    return {
      pageNumber: page.pageNumber,
      chapterTitle: page.chapterTitle,
      imageSrc: page.imageSrc,
      blocks,
      readingTimeMinutes: page.readingTimeMinutes || 2,
    };
  });

  const toc: TocNode[] = (v1.tableOfContents || []).map((item, idx) => ({
    id: `toc-${slug}-${item.pageNumber}-${idx}`,
    level: item.level,
    title: {
      ru: item.titleRu,
      en: item.titleEn || item.titleRu,
    },
    pageIndex: item.pageNumber,
    targetBlockId: `blk-${slug}-p${item.pageNumber}-0`,
  }));

  const manifestV2: BookManifestV2 = {
    schemaVersion: '2.0',
    slug,
    releaseId,
    sourceRevision: 'rev-v1-baseline',
    title: {
      ru: v1.titleRu || v1.title,
      en: v1.title || v1.titleRu,
    },
    subtitle: v1.subtitle || v1.subtitleRu ? {
      ru: v1.subtitleRu || v1.subtitle || '',
      en: v1.subtitle || v1.subtitleRu || '',
    } : undefined,
    contributors,
    citation: {
      shortTitle: (v1 as any).citation?.shortTitle || v1.titleRu || v1.title,
      publisher: publisherName || undefined,
      year: pubYear || undefined,
    },
    sourceLanguage,
    availableLanguages,
    availableViews: ['adapted', 'scan', 'compare'],
    pageRange: {
      start: startPage,
      end: endPage,
    },
    assets: {
      baseUrl: '',
      scanPattern: `/scans/${slug}/page_{page}.webp`,
    },
    toc,
    pagesIndexUrl: `/books/${slug}/${releaseId}/pages.json`,
    pages,
  };

  return validateManifestV2(manifestV2);
}
