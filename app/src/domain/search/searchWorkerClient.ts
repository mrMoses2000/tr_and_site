import type { PageData } from '../types';
import { createDebouncedSearchExecutor, type DebouncedSearchExecutor, type SearchOptions } from './searchEngineV2';
import type {
  SearchWorkerCancelledMessage,
  SearchWorkerErrorMessage,
  SearchWorkerReadyMessage,
  SearchWorkerResultMessage,
  SearchWorkerSearchMessage,
} from './searchWorker';

export interface SearchWorkerSource {
  pages?: PageData[];
  searchIndexUrl?: string;
}

type PendingRequest = {
  resolve: (value: { query: string; matches: SearchWorkerResultMessage['matches']; totalMatches: number; truncated: boolean }) => void;
  reject: (reason: unknown) => void;
  timer: ReturnType<typeof setTimeout> | null;
  requestId: string;
  query: string;
  options?: SearchOptions;
};

function supportsWorker(): boolean {
  return typeof Worker !== 'undefined';
}

function createLegacyExecutor(pages: PageData[], debounceMs: number): DebouncedSearchExecutor {
  return createDebouncedSearchExecutor(pages, debounceMs);
}

export function createDebouncedSearchWorker(
  source: PageData[] | SearchWorkerSource,
  debounceMs = 250,
): DebouncedSearchExecutor {
  const pages = Array.isArray(source) ? source : source.pages ?? [];
  const searchIndexUrl = Array.isArray(source) ? undefined : source.searchIndexUrl;

  if (!searchIndexUrl || !supportsWorker()) {
    return createLegacyExecutor(pages, debounceMs);
  }

  const worker = new Worker(new URL('./searchWorker.ts', import.meta.url), { type: 'module' });
  let sequence = 0;
  let readyResolve: (() => void) | null = null;
  let readyReject: ((reason: unknown) => void) | null = null;
  let ready = false;
  let readyPromise = new Promise<void>((resolve, reject) => {
    readyResolve = resolve;
    readyReject = reject;
  });
  const pending = new Map<string, PendingRequest>();

  worker.postMessage({
    type: 'init',
    requestId: 'init',
    searchIndexUrl,
  } satisfies SearchWorkerSearchMessage | { type: 'init'; requestId: 'init'; searchIndexUrl: string });

  const cancelPending = (requestId: string, reason: string) => {
    const request = pending.get(requestId);
    if (!request) return;
    if (request.timer) {
      clearTimeout(request.timer);
      request.timer = null;
    }
    pending.delete(requestId);
    worker.postMessage({ type: 'cancel', requestId });
    request.reject(new Error(reason));
  };

  worker.addEventListener('message', (event: MessageEvent<SearchWorkerReadyMessage | SearchWorkerResultMessage | SearchWorkerCancelledMessage | SearchWorkerErrorMessage>) => {
    const message = event.data;
    if (!message || typeof message !== 'object') return;

    if (message.type === 'ready') {
      ready = true;
      readyResolve?.();
      readyResolve = null;
      readyReject = null;
      return;
    }

    if (message.type === 'result') {
      const request = pending.get(message.requestId);
      if (!request) return;
      if (request.timer) {
        clearTimeout(request.timer);
      }
      pending.delete(message.requestId);
      request.resolve({
        query: request.query,
        matches: message.matches,
        totalMatches: message.totalMatches,
        truncated: message.truncated,
      });
      return;
    }

    if (message.type === 'cancelled') {
      const request = pending.get(message.requestId);
      if (!request) return;
      if (request.timer) {
        clearTimeout(request.timer);
      }
      pending.delete(message.requestId);
      request.reject(new Error('Search cancelled'));
      return;
    }

    if (message.type === 'error') {
      if (message.requestId) {
        const request = pending.get(message.requestId);
        if (!request) return;
        if (request.timer) {
          clearTimeout(request.timer);
        }
        pending.delete(message.requestId);
        request.reject(new Error(message.message));
      } else {
        readyReject?.(new Error(message.message));
        readyReject = null;
        readyResolve = null;
      }
    }
  });

  const search = (query: string, options?: SearchOptions) => {
    if (!query.trim() || query.trim().length < 2) {
      return Promise.resolve({ query, matches: [], totalMatches: 0, truncated: false });
    }

    for (const [requestId] of pending.entries()) {
      cancelPending(requestId, 'Search cancelled by newer query');
    }

    const requestId = `req-${++sequence}`;
    return new Promise<{ query: string; matches: SearchWorkerResultMessage['matches']; totalMatches: number; truncated: boolean }>((resolve, reject) => {
      const request: PendingRequest = {
        resolve,
        reject,
        timer: null,
        requestId,
        query,
        options,
      };
      pending.set(requestId, request);
      request.timer = setTimeout(async () => {
        request.timer = null;
        try {
          await readyPromise;
        } catch (error) {
          pending.delete(requestId);
          reject(error);
          return;
        }
        if (!pending.has(requestId)) {
          return;
        }
        worker.postMessage({
          type: 'search',
          requestId,
          query,
          maxResults: options?.maxResults,
          snippetRadius: options?.snippetRadius,
        } satisfies SearchWorkerSearchMessage);
      }, debounceMs);
    });
  };

  const cancel = () => {
    for (const [requestId, request] of pending.entries()) {
      if (request.timer) {
        clearTimeout(request.timer);
      }
      worker.postMessage({ type: 'cancel', requestId });
      request.reject(new Error('Search cancelled'));
      pending.delete(requestId);
    }
  };

  if (!ready) {
    readyPromise = new Promise<void>((resolve, reject) => {
      readyResolve = resolve;
      readyReject = reject;
    });
  }

  return {
    search,
    cancel,
  };
}
