import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { DocumentBlockRenderer } from '../components/ast/DocumentBlockRenderer';
import type { DocumentBlock, InlineRun, SourceAnchor } from '../domain/v2/types';
import {
  getSourceCompareState,
  isTrackedSourceAnchor,
  type SourceAssetResolver,
} from '../domain/v2/sourceViewer';

const anchor: SourceAnchor = {
  sourceSha256: 'a'.repeat(64),
  pdfPageIndex: 53,
  printedPageLabel: '54',
  extractionMethod: 'native',
  candidateHash: 'cand-p53-example',
};

const run = (text: string, overrides: Partial<InlineRun> = {}): InlineRun => ({
  id: `run-${text}`,
  text,
  language: 'ru',
  source: anchor,
  ...overrides,
});

describe('P10 AST renderer', () => {
  it('renders all block variants with stable block targets', () => {
    const onFootnote = vi.fn();
    const blocks: DocumentBlock[] = [
      { type: 'heading', id: 'h-1', level: 2, runs: [run('Заголовок')] },
      { type: 'paragraph', id: 'p-1', runs: [run('Абзац')] },
      {
        type: 'quotation',
        id: 'q-1',
        runs: [run('Цитата')],
        attribution: [run('Автор')],
      },
      {
        type: 'list',
        id: 'list-1',
        ordered: true,
        items: [[{ type: 'paragraph', id: 'item-1', runs: [run('Пункт')] }]],
      },
      {
        type: 'table',
        id: 'table-1',
        rows: [[ [run('Ячейка')] ]],
      },
      { type: 'figure', id: 'figure-1', imageRef: '/figure.webp', alt: 'Схема' },
      {
        type: 'footnote',
        id: 'footnote-1',
        label: '4',
        anchors: ['fnref-4'],
        blocks: [{ type: 'paragraph', id: 'fn-p-1', runs: [run('Текст сноски')] }],
      },
      { type: 'pageBreak', id: 'break-1', pdfPageIndex: 54, printedPageLabel: '55' },
    ];

    render(<div>{blocks.map((block) => (
      <DocumentBlockRenderer key={block.id} block={block} onFootnoteClick={onFootnote} />
    ))}</div>);

    expect(screen.getByRole('heading', { name: 'Заголовок' })).toBeInTheDocument();
    expect(screen.getByText('Абзац')).toBeInTheDocument();
    expect(screen.getByText('Цитата')).toBeInTheDocument();
    expect(screen.getByRole('list')).toBeInTheDocument();
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Схема' })).toBeInTheDocument();
    expect(screen.getByText('Текст сноски')).toBeInTheDocument();
    expect(screen.getByRole('separator')).toHaveAttribute('aria-label', 'Переход к странице 55');

    for (const block of blocks) {
      expect(document.querySelector(`[data-block-id="${block.id}"]`)).toBeInTheDocument();
    }
  });

  it('preserves run language and marks without string heuristics', () => {
    const marked = run('λόγος', {
      id: 'marked-run',
      language: 'grc',
      marks: ['bold', 'italic', 'smallcaps', 'superscript'],
    });

    render(<DocumentBlockRenderer block={{ type: 'paragraph', id: 'marked-p', runs: [marked] }} />);

    const languageRun = document.querySelector('[data-run-id="marked-run"]');
    expect(languageRun).toHaveAttribute('lang', 'grc');
    expect(languageRun).toHaveTextContent('λόγος');
    expect(languageRun?.querySelector('strong em sup')).toBeTruthy();
  });

  it('uses an explicit image fallback for a table without inventing paragraph text', () => {
    render(<DocumentBlockRenderer block={{
      type: 'table',
      id: 'table-fallback',
      rows: [],
      fallbackImageRef: '/table.webp',
    }} />);

    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(screen.getByRole('img', { name: /таблица/i })).toHaveAttribute('src', '/table.webp');
    expect(screen.queryByText(/table-fallback/)).not.toBeInTheDocument();
  });

  it('does not expose an untracked V1 anchor as a source compare target', () => {
    const synthetic = { ...anchor, sourceSha256: 'sha256-v1-untracked-source' };
    expect(isTrackedSourceAnchor(synthetic)).toBe(false);
    expect(getSourceCompareState(synthetic)).toEqual({
      status: 'unavailable',
      reason: 'source-untracked',
    });
  });

  it('resolves a tracked source anchor through the injected asset resolver', () => {
    const resolver: SourceAssetResolver = {
      resolve: vi.fn(() => ({ status: 'available', url: '/source/osborne.pdf#page=54' })),
    };

    expect(getSourceCompareState(anchor, resolver)).toEqual({
      status: 'available',
      url: '/source/osborne.pdf#page=54',
    });
    expect(resolver.resolve).toHaveBeenCalledWith(anchor);
  });

  it.each([
    'https://evil.example/source.pdf',
    '//evil.example/source.pdf',
    'javascript:alert(1)',
    '/\\evil.example/source.pdf',
  ])('fails closed for an unsafe resolver URL: %s', (url) => {
    const resolver: SourceAssetResolver = { resolve: () => ({ status: 'available', url }) };
    expect(getSourceCompareState(anchor, resolver)).toEqual({
      status: 'unavailable',
      reason: 'invalid-source-url',
    });
  });

  it('clicks the first source anchor recursively for nested list/table blocks', () => {
    const nestedAnchor = { ...anchor, pdfPageIndex: 99, candidateHash: 'nested-candidate' };
    const onSourceAnchorClick = vi.fn();
    render(<DocumentBlockRenderer
      block={{
        type: 'list',
        id: 'nested-list',
        ordered: false,
        items: [[{
          type: 'table',
          id: 'nested-table',
          rows: [[[
            run('nested', { source: nestedAnchor }),
          ]]],
        }]],
      }}
      onSourceAnchorClick={onSourceAnchorClick}
    />);

    fireEvent.click(screen.getByTestId('source-action-nested-list'));
    expect(onSourceAnchorClick).toHaveBeenCalledTimes(1);
    expect(onSourceAnchorClick).toHaveBeenCalledWith(nestedAnchor);
  });

  it('exposes an accessible source target for keyboard and pointer navigation', () => {
    const onSourceAnchorClick = vi.fn();
    render(<DocumentBlockRenderer
      block={{ type: 'paragraph', id: 'source-p', runs: [run('Проверяемый текст')] }}
      onSourceAnchorClick={onSourceAnchorClick}
    />);

    fireEvent.click(screen.getByRole('button', { name: /открыть источник/i }));
    expect(onSourceAnchorClick).toHaveBeenCalledWith(anchor);
  });
});
