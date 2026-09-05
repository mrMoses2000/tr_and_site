/**
 * Document AST & Versioned Manifest V2 Contracts
 * According to GEMINI_IMPLEMENTATION_PLAYBOOK.md Section 6
 */

export type LanguageCode = 'ru' | 'kk' | 'en' | 'grc' | 'he' | 'und';

export interface SourceAnchor {
  sourceSha256: string;
  pdfPageIndex: number;
  printedPageLabel?: string;
  renderedSide?: 'left' | 'right' | 'full';
  bbox?: [number, number, number, number];
  extractionMethod: 'native' | 'ocr' | 'vision' | 'manual';
  candidateHash: string;
  confidence?: number;
}

export interface InlineRun {
  id: string;
  text: string;
  language: LanguageCode;
  marks?: Array<'bold' | 'italic' | 'smallcaps' | 'superscript' | 'subscript'>;
  source: SourceAnchor;
}

export type DocumentBlock =
  | { type: 'heading'; id: string; level: 1 | 2 | 3 | 4; runs: InlineRun[] }
  | { type: 'paragraph'; id: string; runs: InlineRun[] }
  | { type: 'quotation'; id: string; runs: InlineRun[]; attribution?: InlineRun[] }
  | { type: 'list'; id: string; ordered: boolean; items: DocumentBlock[][] }
  | { type: 'table'; id: string; rows: InlineRun[][][]; fallbackImageRef?: string }
  | { type: 'figure'; id: string; imageRef: string; caption?: InlineRun[]; alt?: string }
  | { type: 'footnote'; id: string; label: string; blocks: DocumentBlock[]; anchors: string[] }
  | { type: 'pageBreak'; id: string; pdfPageIndex: number; printedPageLabel?: string };

export interface TocNode {
  id: string;
  level: number;
  title: Record<string, string>;
  pageIndex: number;
  printedPageLabel?: string;
  targetBlockId?: string;
  children?: TocNode[];
}

export interface PageV2 {
  pageNumber: number;
  printedPageLabel?: string;
  chapterTitle?: string;
  imageSrc: string;
  blocks: DocumentBlock[];
  readingTimeMinutes: number;
}

export interface BookManifestV2 {
  schemaVersion: '2.0';
  slug: string;
  releaseId: string;
  sourceRevision: string;
  title: Record<string, string>;
  subtitle?: Record<string, string>;
  contributors: Array<{ role: string; name: string; language?: string }>;
  citation: {
    shortTitle: string;
    publisher?: string;
    place?: string;
    year?: string;
    edition?: string;
  };
  sourceLanguage: LanguageCode;
  availableLanguages: LanguageCode[];
  availableViews: Array<'adapted' | 'scan' | 'compare'>;
  pageRange: { start: number; end: number };
  assets: { baseUrl?: string; scanPattern?: string; sourcePdf?: string };
  toc: TocNode[];
  pagesIndexUrl: string;
  pages: PageV2[];
  audioEditions?: Array<{
    editionId: string;
    language: LanguageCode;
    durationSeconds: number;
    audioUrl: string;
  }>;
}

export interface BookCitationMetadata {
  shortTitle: string;
  author: string;
  title: string;
  subtitle?: string;
  publisher?: string;
  place?: string;
  year?: string;
  edition?: string;
}

export interface ResearchCardV2 {
  id: string;
  bookSlug: string;
  releaseId?: string;
  pageNumber: number;
  blockId?: string;
  sourceAnchor?: SourceAnchor;
  citationSnapshot?: BookCitationMetadata;
  quote: string;
  quoteLanguage: 'ru' | 'en' | string;
  note: string;
  tag: 'thesis' | 'quote' | 'thought' | 'for-paper' | 'theology' | 'question';
  color: 'amber' | 'emerald' | 'blue' | 'purple';
  createdAt: string;
  updatedAt: string;
}

