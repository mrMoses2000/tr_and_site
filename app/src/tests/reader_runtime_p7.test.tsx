import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useEffect } from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import App from '../App';
import { SearchDialog } from '../components/SearchDialog';
import type { BookManifest, PageData } from '../domain/types';
import { UnknownBookError } from '../data/library/libraryRegistry';
import { useReader } from '../domain/useReader';

const page: PageData = {
  pageNumber: 1,
  chapterTitle: 'Fixture chapter',
  paragraphs: [{ id: 'p-1', ru: 'Текст fixture. [7]', en: 'Fixture text. [7]' }],
  footnotes: [{ id: 7, textRu: 'Сноска fixture', textEn: 'Fixture footnote' }],
  imageSrc: '/fixture.webp',
};

const fixture: BookManifest = {
  slug: 'fixture-book',
  title: 'Fixture book',
  titleRu: 'Тестовая книга',
  author: 'Fixture author',
  authorRu: 'Автор теста',
  startPage: 1,
  endPage: 2,
  totalPages: 2,
  tableOfContents: [],
  pages: [page],
};

function ReaderProbe({
  loader,
  onReady,
}: {
  loader: (slug: string, signal?: AbortSignal) => Promise<BookManifest>;
  onReady: (reader: ReturnType<typeof useReader>) => void;
}) {
  const reader = useReader({
    loadManifest: loader,
    initialLocation: { bookSlug: 'book-a', pageNumber: 1 },
  });
  useEffect(() => onReady(reader), [onReady, reader]);
  return <div data-testid="loaded-book">{reader.manifest?.slug ?? reader.manifestLoadState}</div>;
}

describe('P7/P8 reader runtime contracts', () => {
  beforeEach(() => {
    localStorage.clear();
    window.location.hash = '#book=fixture-book&page=1';
  });

  it('loads a selected known book through the injected async loader', async () => {
    const loader = vi.fn(async (slug: string) => {
      if (slug !== 'fixture-book') throw new UnknownBookError(slug);
      return fixture;
    });
    render(<App readerOptions={{ loadManifest: loader }} />);
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Fixture chapter', level: 1 })).toBeInTheDocument());
    expect(loader).toHaveBeenCalledWith('fixture-book', expect.any(AbortSignal));
  });

  it('opens scan view when the location transition requests scan', async () => {
    const loader = vi.fn(async () => fixture);
    render(<App readerOptions={{ loadManifest: loader }} />);
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Fixture chapter', level: 1 })).toBeInTheDocument());
    fireEvent.click(screen.getByTitle(/Фото оригинала страницы/i));
    expect(await screen.findByText(/Оригинальный скан • Стр\. 1/i)).toBeInTheDocument();
  });

  it('renders a typed load error for an unknown deep-link book', async () => {
    window.location.hash = '#book=missing-book&page=1';
    const loader = vi.fn(async (slug: string) => {
      throw new UnknownBookError(slug);
    });
    render(<App readerOptions={{ loadManifest: loader }} />);
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/Unknown book slug/));
  });

  it('aborts a stale manifest load when the reader unmounts', () => {
    let receivedSignal: AbortSignal | undefined;
    const loader = vi.fn((_slug: string, signal?: AbortSignal) => {
      receivedSignal = signal;
      return new Promise<BookManifest>((_resolve, reject) => {
        signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
      });
    });
    const { unmount } = render(<App readerOptions={{ loadManifest: loader }} />);
    unmount();
    expect(receivedSignal?.aborted).toBe(true);
  });

  it('does not commit book A when its in-flight load resolves after switching to B', async () => {
    const pending = new Map<string, { resolve: (manifest: BookManifest) => void }>();
    const loader = vi.fn((slug: string, signal?: AbortSignal) => new Promise<BookManifest>((resolve, reject) => {
      pending.set(slug, { resolve });
      signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
    }));
    let reader: ReturnType<typeof useReader> | undefined;
    const onReady = (nextReader: ReturnType<typeof useReader>) => { reader = nextReader; };
    render(<ReaderProbe loader={loader} onReady={onReady} />);
    await waitFor(() => expect(loader).toHaveBeenCalledWith('book-a', expect.any(AbortSignal)));

    reader?.selectBook('book-b');
    await waitFor(() => expect(loader).toHaveBeenCalledWith('book-b', expect.any(AbortSignal)));
    pending.get('book-b')?.resolve({ ...fixture, slug: 'book-b' });
    await waitFor(() => expect(screen.getByTestId('loaded-book')).toHaveTextContent('book-b'));

    pending.get('book-a')?.resolve({ ...fixture, slug: 'book-a', title: 'Stale A' });
    await new Promise<void>((resolve) => queueMicrotask(resolve));
    expect(screen.getByTestId('loaded-book')).toHaveTextContent('book-b');
  });

  it('shows an explicit missing-page state instead of rendering page one', async () => {
    window.location.hash = '#book=fixture-book&page=2';
    const loader = vi.fn(async () => fixture);
    render(<App readerOptions={{ loadManifest: loader }} />);
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/Страница 2 отсутствует/));
  });

  it('opens and focuses the exact footnote from a deep-link location', async () => {
    window.location.hash = '#book=fixture-book&page=1&fn=7';
    const loader = vi.fn(async () => fixture);
    render(<App readerOptions={{ loadManifest: loader }} />);
    await waitFor(() => expect(screen.getByText('Сноска fixture')).toBeInTheDocument());
    await waitFor(() => expect(document.querySelector('[data-footnote-id="7"]')).toBe(document.activeElement));
    fireEvent.click(screen.getByTitle(/Закрыть/));
    await waitFor(() => expect(screen.queryByText('Сноска fixture')).not.toBeInTheDocument());
    expect(window.location.hash).not.toContain('fn=7');
  });

  it('passes paragraph and footnote anchors when selecting search results', async () => {
    const onSelectLocation = vi.fn();
    render(
      <SearchDialog
        isOpen
        onClose={vi.fn()}
        pages={[page]}
        onSelectLocation={onSelectLocation}
      />,
    );
    fireEvent.change(screen.getByLabelText(/Поиск по тексту/i), { target: { value: 'fixture' } });
    await waitFor(() => expect(screen.getAllByText(/fixture/i, { selector: 'mark' }).length).toBeGreaterThan(0));
    const paragraphMatch = screen.getAllByText(/fixture/i, { selector: 'mark' })[0];
    const paragraphResult = paragraphMatch.closest('button');
    expect(paragraphResult).not.toBeNull();
    fireEvent.click(paragraphResult!);
    expect(onSelectLocation).toHaveBeenCalledWith(expect.objectContaining({
      pageNumber: 1,
      blockId: 'p-1',
    }));
  });
});
