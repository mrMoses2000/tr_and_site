export type ReaderTheme = 'sepia' | 'light' | 'dark' | 'oled';
export type FontFamily = 'serif' | 'sans';
export type ReaderMode = 'ru' | 'bilingual' | 'en';

export type CardTag = 'thesis' | 'quote' | 'thought' | 'for-paper' | 'theology' | 'question';
export type HighlightColor = 'amber' | 'emerald' | 'blue' | 'purple';

import type { BookCitationMetadata, SourceAnchor } from './v2/types';

export interface ResearchCard {
  id: string;
  bookSlug?: string;
  releaseId?: string;
  pageNumber: number;
  paragraphId?: string;
  sourceAnchor?: SourceAnchor;
  citationSnapshot?: BookCitationMetadata;
  quote: string;
  quoteLanguage: 'ru' | 'en';
  note: string;
  tag: CardTag;
  color: HighlightColor;
  createdAt: string;
  updatedAt: string;
}

export interface ParagraphPair {
  id: string;
  en: string;
  ru: string;
}

export interface FootnotePair {
  id: number;
  textEn: string;
  textRu: string;
}

export interface PageData {
  pageNumber: number;
  chapterTitle?: string;
  originalEn?: string;
  translatedRu?: string;
  paragraphs: ParagraphPair[];
  footnotes: FootnotePair[];
  imageSrc: string;
  marginNotes?: string[];
  readingTimeMinutes?: number;
  notes?: string[];
}

export interface TocItem {
  pageNumber: number;
  titleEn: string;
  titleRu: string;
  level: number;
}

export interface BookManifest {
  slug?: string;
  title: string;
  titleRu: string;
  subtitle?: string;
  subtitleRu?: string;
  author: string;
  authorRu?: string;
  publisher?: string;
  startPage: number;
  endPage: number;
  totalPages: number;
  tableOfContents: TocItem[];
  pages: PageData[];
}

export interface ReaderSettings {
  fontSize: number; // 14 - 28 px
  lineHeight: number; // 1.4 - 2.2
  maxWidth: number; // 500 - 1000 px
  theme: ReaderTheme;
  fontFamily: FontFamily;
  mode: ReaderMode;
  showDropCap: boolean;
  showScanModal: boolean;
}

export interface ReadingProgress {
  currentPage: number;
  totalPages: number;
  percent: number;
  estimatedMinutesLeft: number;
}
