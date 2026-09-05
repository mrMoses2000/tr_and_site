import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReaderContent } from '../components/ReaderContent';
import type { PageData, ReaderSettings } from '../domain/types';

const defaultSettings: ReaderSettings = {
  fontSize: 18,
  lineHeight: 1.6,
  maxWidth: 800,
  theme: 'light',
  fontFamily: 'serif',
  mode: 'ru',
  showDropCap: true,
  showScanModal: false,
};

describe('R1 Fidelity Contracts: Frontend Reader', () => {
  it('R1-09: short diagram fragments and letters must NOT be rendered as headings', () => {
    // Page with diagram fragments that previously triggered short-string heading heuristic
    const pageWithDiagramLabels: PageData = {
      pageNumber: 50,
      imageSrc: '/scans/test/page_50.webp',
      readingTimeMinutes: 5,
      paragraphs: [
        { id: 'p-50-1', ru: 'Обычный вводный абзац.', en: 'Normal intro paragraph.' },
        { id: 'p-50-2', ru: 'Сп', en: 'Сп' },
        { id: 'p-50-3', ru: 'славы', en: 'славы' },
        { id: 'p-50-4', ru: 'в похвалу', en: 'в похвалу' },
        { id: 'p-50-5', ru: 'Т', en: 'Т' },
      ],
      footnotes: [],
    };

    render(
      <ReaderContent
        page={pageWithDiagramLabels}
        settings={defaultSettings}
        cards={[]}
        hoveredParagraphId={null}
        onHoverParagraph={vi.fn()}
        onSelectFootnote={vi.fn()}
        onOpenScan={vi.fn()}
        onOpenCreateCard={vi.fn()}
        onOpenCards={vi.fn()}
      />
    );

    // None of these diagram fragments should become h2/h3 headings!
    expect(screen.queryByRole('heading', { name: 'Сп' })).toBeNull();
    expect(screen.queryByRole('heading', { name: 'славы' })).toBeNull();
    expect(screen.queryByRole('heading', { name: 'в похвалу' })).toBeNull();
    expect(screen.queryByRole('heading', { name: 'Т' })).toBeNull();
  });

  it('R1-10: reader renders typed AST blocks when page contains structured blocks', () => {
    const pageWithAst: PageData = {
      pageNumber: 45,
      imageSrc: '/scans/test/page_45.webp',
      readingTimeMinutes: 5,
      paragraphs: [],
      footnotes: [],
      blocks: [
        {
          type: 'figure',
          id: 'fig-1-5',
          imageRef: '/figures/fig-1-5.png',
          alt: 'Рис. 1.5. Фразовая диаграмма Ефесянам 1.5–7',
          caption: 'Рис. 1.5. Фразовая диаграмма Ефесянам 1.5–7',
        },
      ],
    };

    render(
      <ReaderContent
        page={pageWithAst as PageData}
        settings={defaultSettings}
        cards={[]}
        hoveredParagraphId={null}
        onHoverParagraph={vi.fn()}
        onSelectFootnote={vi.fn()}
        onOpenScan={vi.fn()}
        onOpenCreateCard={vi.fn()}
        onOpenCards={vi.fn()}
      />
    );

    // When structured blocks are present, FigureBlock must be rendered
    expect(screen.getByRole('img', { name: /Рис\. 1\.5/i })).toBeInTheDocument();
  });
});
