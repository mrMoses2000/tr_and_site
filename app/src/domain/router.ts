import type { ReaderLocationV2 } from './storage/storageV2';

export interface LocationResolverResult {
  startPage: number;
  endPage: number;
}

export type ManifestBoundsResolver = (slug: string) => LocationResolverResult | null;

/**
 * Parses URL hash into a structured ReaderLocationV2.
 * Handles both modern (#book=...&page=...) and legacy (#page=..., #catalog) hashes.
 */
export function parseReaderLocation(
  hash: string,
  fallbackSlug = 'schreiner-ntt',
  fallbackPage = 1
): ReaderLocationV2 {
  const clean = hash.startsWith('#') ? hash.slice(1) : hash;

  if (clean === 'catalog' || clean === 'home' || clean === '') {
    return {
      bookSlug: '',
      pageNumber: 1,
      view: 'catalog',
    };
  }

  const params = new URLSearchParams(clean);
  const bookSlug = params.get('book') || fallbackSlug;

  const rawPage = params.get('page');
  let pageNumber = fallbackPage;
  if (rawPage) {
    const parsed = parseInt(rawPage, 10);
    if (!Number.isNaN(parsed)) {
      pageNumber = parsed;
    }
  }

  const viewParam = params.get('view');
  const view = (['adapted', 'scan', 'compare', 'catalog'].includes(viewParam || '')
    ? (viewParam as any)
    : undefined);

  const modeParam = params.get('mode');
  const mode = (['ru', 'bilingual', 'en'].includes(modeParam || '')
    ? (modeParam as any)
    : undefined);

  const blockId = params.get('block') || params.get('blockId') || undefined;
  const footnoteId = params.get('fn') || params.get('footnoteId') || undefined;

  return {
    bookSlug,
    pageNumber,
    view,
    mode,
    blockId,
    footnoteId,
  };
}

/**
 * Serializes ReaderLocationV2 to standard URL hash format.
 */
export function serializeReaderLocation(loc: Partial<ReaderLocationV2>): string {
  if (loc.view === 'catalog' || !loc.bookSlug) {
    return '#catalog';
  }

  const params = new URLSearchParams();
  params.set('book', loc.bookSlug);
  params.set('page', String(loc.pageNumber || 1));

  if (loc.view) {
    params.set('view', loc.view);
  }
  if (loc.mode) {
    params.set('mode', loc.mode);
  }
  if (loc.blockId) {
    params.set('block', loc.blockId);
  }
  if (loc.footnoteId !== undefined) {
    params.set('fn', String(loc.footnoteId));
  }

  return `#${params.toString()}`;
}

/**
 * Validates and clamps reader location against target book manifest boundaries.
 * Prevents cross-book bound contamination (e.g. clamping Book B with Book A's start/end pages).
 */
export function resolveAndValidateLocation(
  targetLoc: Partial<ReaderLocationV2>,
  resolver: ManifestBoundsResolver,
  currentSlug = 'schreiner-ntt',
  currentPage = 1
): ReaderLocationV2 {
  const targetSlug = targetLoc.bookSlug || currentSlug;
  const manifestBounds = resolver(targetSlug);

  const minPage = manifestBounds?.startPage ?? 1;
  const maxPage = manifestBounds?.endPage ?? 9999;

  const requestedPage = targetLoc.pageNumber !== undefined ? targetLoc.pageNumber : currentPage;
  const clampedPage = Math.max(minPage, Math.min(maxPage, requestedPage));

  return {
    bookSlug: targetSlug,
    pageNumber: clampedPage,
    view: targetLoc.view,
    mode: targetLoc.mode,
    blockId: targetLoc.blockId,
    footnoteId: targetLoc.footnoteId,
  };
}

/**
 * Atomic location command:
 * 1. Resolves target manifest & validates target bounds
 * 2. Updates state atomically without intermediate renders
 * 3. Updates hash
 * 4. Closes overlays
 */
export interface OpenLocationCommandOptions {
  location: Partial<ReaderLocationV2>;
  resolver: ManifestBoundsResolver;
  currentSlug: string;
  currentPage: number;
  onNavigate: (resolved: ReaderLocationV2) => void;
  closeOverlays?: () => void;
  updateHash?: boolean;
}

export function openLocation(options: OpenLocationCommandOptions): ReaderLocationV2 {
  const resolved = resolveAndValidateLocation(
    options.location,
    options.resolver,
    options.currentSlug,
    options.currentPage
  );

  if (options.closeOverlays) {
    options.closeOverlays();
  }

  if (options.updateHash !== false && typeof window !== 'undefined') {
    window.location.hash = serializeReaderLocation(resolved);
  }

  options.onNavigate(resolved);
  return resolved;
}
