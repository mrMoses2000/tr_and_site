import '@testing-library/jest-dom/vitest';
import fs from 'node:fs';
import path from 'node:path';

const publicDir = path.resolve(process.cwd(), 'public');
const originalFetch = globalThis.fetch;

globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
  let urlString = '';
  if (typeof input === 'string') {
    urlString = input;
  } else if (input instanceof URL) {
    urlString = input.pathname;
  } else if (input instanceof Request) {
    urlString = input.url;
  } else {
    urlString = String(input);
  }

  if (urlString.startsWith('http://localhost') || urlString.startsWith('http://127.0.0.1')) {
    try {
      const parsed = new URL(urlString);
      urlString = parsed.pathname;
    } catch {
      // ignore
    }
  }

  if (urlString.startsWith('/')) {
    if (init?.signal?.aborted) {
      const abortError = new Error('This operation was aborted');
      abortError.name = 'AbortError';
      throw abortError;
    }

    const cleanPath = urlString.split('?')[0].replace(/^\/+/, '');
    const filePath = path.join(publicDir, cleanPath);
    if (fs.existsSync(filePath)) {
      const content = fs.readFileSync(filePath, 'utf8');
      return new Response(content, {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    return new Response('Not Found', { status: 404 });
  }

  return originalFetch(input, init);
};
