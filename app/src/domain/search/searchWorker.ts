import { searchCorpusV2, type SearchCorpusEntry } from './searchEngineV2';

export interface SearchIndexFile {
  schemaVersion: '1.0';
  bookSlug: string;
  releaseId: string;
  pageRange: { start: number; end: number };
  entries: SearchCorpusEntry[];
}

type SearchWorkerInitMessage = {
  type: 'init';
  requestId: 'init';
  searchIndexUrl: string;
};

type SearchWorkerSearchMessage = {
  type: 'search';
  requestId: string;
  query: string;
  maxResults?: number;
  snippetRadius?: number;
};

type SearchWorkerCancelMessage = {
  type: 'cancel';
  requestId: string;
};

type SearchWorkerDisposeMessage = {
  type: 'dispose';
};

type SearchWorkerRequest =
  | SearchWorkerInitMessage
  | SearchWorkerSearchMessage
  | SearchWorkerCancelMessage
  | SearchWorkerDisposeMessage;

type SearchWorkerReadyMessage = {
  type: 'ready';
  bookSlug: string;
  releaseId: string;
};

type SearchWorkerResultMessage = {
  type: 'result';
  requestId: string;
  matches: ReturnType<typeof searchCorpusV2>['matches'];
  totalMatches: number;
  truncated: boolean;
};

type SearchWorkerCancelledMessage = {
  type: 'cancelled';
  requestId: string;
};

type SearchWorkerErrorMessage = {
  type: 'error';
  requestId?: string;
  message: string;
};

type SearchWorkerResponse =
  | SearchWorkerReadyMessage
  | SearchWorkerResultMessage
  | SearchWorkerCancelledMessage
  | SearchWorkerErrorMessage;

const cancelledRequests = new Set<string>();
let searchIndexPromise: Promise<SearchIndexFile> | null = null;
let loadedIndex: SearchIndexFile | null = null;

function isSearchIndexFile(value: unknown): value is SearchIndexFile {
  if (!value || typeof value !== 'object') return false;
  const index = value as Partial<SearchIndexFile>;
  return index.schemaVersion === '1.0'
    && typeof index.bookSlug === 'string'
    && typeof index.releaseId === 'string'
    && typeof index.pageRange?.start === 'number'
    && typeof index.pageRange?.end === 'number'
    && Array.isArray(index.entries);
}

async function loadSearchIndex(searchIndexUrl: string, signal?: AbortSignal): Promise<SearchIndexFile> {
  if (!searchIndexPromise) {
    searchIndexPromise = fetch(searchIndexUrl, { signal })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Failed to fetch search index: ${response.status}`);
        }
        const parsed = await response.json() as unknown;
        if (!isSearchIndexFile(parsed)) {
          throw new Error(`Invalid search index: ${searchIndexUrl}`);
        }
        loadedIndex = parsed;
        return parsed;
      })
      .catch((error) => {
        searchIndexPromise = null;
        loadedIndex = null;
        throw error;
      });
  }
  return searchIndexPromise;
}

function emit(message: SearchWorkerResponse): void {
  (self as unknown as { postMessage: (msg: unknown) => void }).postMessage(message);
}

async function handleSearch(message: SearchWorkerSearchMessage): Promise<void> {
  if (!loadedIndex) {
    emit({ type: 'error', requestId: message.requestId, message: 'Search index not initialized' });
    return;
  }

  if (cancelledRequests.has(message.requestId)) {
    cancelledRequests.delete(message.requestId);
    emit({ type: 'cancelled', requestId: message.requestId });
    return;
  }

  const result = searchCorpusV2(loadedIndex.entries, message.query, {
    maxResults: message.maxResults,
    snippetRadius: message.snippetRadius,
    isCancelled: () => cancelledRequests.has(message.requestId),
  });

  if (cancelledRequests.has(message.requestId)) {
    cancelledRequests.delete(message.requestId);
    emit({ type: 'cancelled', requestId: message.requestId });
    return;
  }

  emit({
    type: 'result',
    requestId: message.requestId,
    matches: result.matches,
    totalMatches: result.totalMatches,
    truncated: result.truncated,
  });
}

self.addEventListener('message', (event: MessageEvent<SearchWorkerRequest>) => {
  const message = event.data;
  if (!message || typeof message !== 'object') return;

  if (message.type === 'cancel') {
    cancelledRequests.add(message.requestId);
    return;
  }

  if (message.type === 'dispose') {
    cancelledRequests.clear();
    searchIndexPromise = null;
    loadedIndex = null;
    return;
  }

  if (message.type === 'init') {
    void loadSearchIndex(message.searchIndexUrl)
      .then((index) => {
        emit({
          type: 'ready',
          bookSlug: index.bookSlug,
          releaseId: index.releaseId,
        });
      })
      .catch((error: unknown) => {
        emit({
          type: 'error',
          requestId: message.requestId,
          message: error instanceof Error ? error.message : String(error),
        });
      });
    return;
  }

  if (message.type === 'search') {
    void handleSearch(message).catch((error: unknown) => {
      emit({
        type: 'error',
        requestId: message.requestId,
        message: error instanceof Error ? error.message : String(error),
      });
    });
  }
});

export type {
  SearchWorkerRequest,
  SearchWorkerResponse,
  SearchWorkerReadyMessage,
  SearchWorkerResultMessage,
  SearchWorkerCancelledMessage,
  SearchWorkerErrorMessage,
  SearchWorkerSearchMessage,
};
