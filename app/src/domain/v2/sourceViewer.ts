import type { SourceAnchor } from './types';

export type SourceCompareStatus = 'available' | 'unavailable' | 'needs_review';

export type SourceAssetResolution =
  | { status: 'available'; url: string }
  | { status: 'unavailable'; reason: string }
  | { status: 'needs_review'; reason: string };

export interface SourceAssetResolver {
  /** Implementations are runtime boundaries; results are validated below. */
  resolve(anchor: SourceAnchor): unknown;
}

export interface SourceViewerController {
  openSource(anchor: SourceAnchor): void;
}

export function isTrackedSourceAnchor(anchor: SourceAnchor): boolean {
  return /^[a-f0-9]{64}$/i.test(anchor.sourceSha256)
    && anchor.sourceSha256 !== 'sha256-v1-untracked-source';
}

export function getSourceCompareState(
  anchor: SourceAnchor,
  resolver?: SourceAssetResolver,
): SourceAssetResolution {
  if (!isTrackedSourceAnchor(anchor)) {
    return { status: 'unavailable', reason: 'source-untracked' };
  }
  if (!resolver) {
    return { status: 'unavailable', reason: 'source-resolver-unavailable' };
  }
  try {
    const result = resolver.resolve(anchor);
    if (!result || typeof result !== 'object') {
      return { status: 'unavailable', reason: 'invalid-source-resolver-result' };
    }

    const candidate = result as Record<string, unknown>;
    if (candidate.status === 'available') {
      if (typeof candidate.url !== 'string' || !isSafeRootRelativeUrl(candidate.url)) {
        return { status: 'unavailable', reason: 'invalid-source-url' };
      }
      return { status: 'available', url: candidate.url };
    }
    if (candidate.status === 'unavailable' || candidate.status === 'needs_review') {
      if (typeof candidate.reason !== 'string' || candidate.reason.trim() === '') {
        return { status: 'unavailable', reason: 'invalid-source-resolver-result' };
      }
      return { status: candidate.status, reason: candidate.reason };
    }
    return { status: 'unavailable', reason: 'invalid-source-resolver-result' };
  } catch {
    return { status: 'unavailable', reason: 'source-resolver-failed' };
  }
}

function isSafeRootRelativeUrl(value: string): boolean {
  if (!value.startsWith('/') || value.startsWith('//') || value.includes('\\') || /[\u0000-\u001f]/.test(value)) {
    return false;
  }
  try {
    const parsed = new URL(value, 'https://logos.invalid');
    return parsed.origin === 'https://logos.invalid' && parsed.protocol === 'https:';
  } catch {
    return false;
  }
}
