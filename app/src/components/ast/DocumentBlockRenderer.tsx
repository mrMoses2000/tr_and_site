import type { FC, ReactNode } from 'react';
import type {
  DocumentBlock,
  InlineRun,
  PageV2,
  SourceAnchor,
} from '../../domain/v2/types';

export interface DocumentBlockRendererProps {
  block: DocumentBlock;
  onFootnoteClick?: (block: Extract<DocumentBlock, { type: 'footnote' }>) => void;
  onSourceAnchorClick?: (anchor: SourceAnchor) => void;
}

export interface InlineRunRendererProps {
  runs: InlineRun[];
  onSourceAnchorClick?: (anchor: SourceAnchor) => void;
}

export interface PageV2RendererProps {
  page: PageV2;
  onFootnoteClick?: DocumentBlockRendererProps['onFootnoteClick'];
  onSourceAnchorClick?: DocumentBlockRendererProps['onSourceAnchorClick'];
}

function runContent(run: InlineRun): ReactNode {
  let content: ReactNode = run.text;
  const marks = run.marks ?? [];

  if (marks.includes('superscript')) content = <sup>{content}</sup>;
  if (marks.includes('subscript')) content = <sub>{content}</sub>;
  if (marks.includes('smallcaps')) content = <span className="[font-variant:small-caps]">{content}</span>;
  if (marks.includes('italic')) content = <em>{content}</em>;
  if (marks.includes('bold')) content = <strong>{content}</strong>;
  return content;
}

export const InlineRunRenderer: FC<InlineRunRendererProps> = ({ runs, onSourceAnchorClick }) => (
  <>
    {runs.map((run) => {
      const content = (
        <span
          key={run.id}
          data-run-id={run.id}
          lang={run.language === 'und' ? undefined : run.language}
          className="inline-run"
        >
          {runContent(run)}
        </span>
      );

      if (!onSourceAnchorClick) return content;
      return (
        <span key={run.id} data-source-anchor={run.source.candidateHash}>
          {content}
        </span>
      );
    })}
  </>
);

function blockText(block: DocumentBlock): string {
  switch (block.type) {
    case 'heading':
    case 'paragraph':
    case 'quotation':
      return block.runs.map((run) => run.text).join('');
    case 'list':
      return block.items.flatMap((item) => item.map(blockText)).join(' ');
    case 'table':
      return block.rows.flatMap((row) => row.flatMap((cell) => cell.map((run) => run.text))).join(' ');
    case 'figure':
      return Array.isArray(block.caption)
        ? block.caption.map((run) => run.text).join('')
        : (typeof block.caption === 'string' ? block.caption : (block.alt ?? ''));
    case 'footnote':
      return block.blocks.map(blockText).join(' ');
    case 'pageBreak':
      return '';
  }
}

function firstSourceAnchor(block: DocumentBlock): SourceAnchor | undefined {
  switch (block.type) {
    case 'heading':
    case 'paragraph':
    case 'quotation':
      return block.runs[0]?.source;
    case 'list':
      for (const item of block.items) {
        for (const child of item) {
          const source = firstSourceAnchor(child);
          if (source) return source;
        }
      }
      return undefined;
    case 'table':
      for (const row of block.rows) {
        for (const cell of row) {
          for (const run of cell) {
            if (run.source) return run.source;
          }
        }
      }
      return undefined;
    case 'footnote':
      for (const child of block.blocks) {
        const source = firstSourceAnchor(child);
        if (source) return source;
      }
      return undefined;
    case 'figure':
    case 'pageBreak':
      return undefined;
  }
}

function renderBlockContent(
  block: DocumentBlock,
  onFootnoteClick?: DocumentBlockRendererProps['onFootnoteClick'],
  onSourceAnchorClick?: DocumentBlockRendererProps['onSourceAnchorClick'],
): ReactNode {
  switch (block.type) {
    case 'heading': {
      const Heading = `h${block.level || 2}` as 'h1' | 'h2' | 'h3' | 'h4';
      const headingClasses = {
        h1: 'text-2xl font-bold tracking-tight text-[var(--text-primary)] mt-8 mb-4 border-b border-[var(--border-subtle)] pb-2',
        h2: 'text-xl font-bold tracking-tight text-[var(--text-primary)] mt-6 mb-3',
        h3: 'text-lg font-semibold tracking-tight text-[var(--text-primary)] mt-4 mb-2',
        h4: 'text-base font-semibold text-[var(--text-primary)] mt-3 mb-1',
      }[Heading] || 'text-xl font-bold text-[var(--text-primary)]';
      return (
        <Heading className={headingClasses}>
          <InlineRunRenderer runs={block.runs} onSourceAnchorClick={onSourceAnchorClick} />
        </Heading>
      );
    }
    case 'paragraph':
      return (
        <p className="my-3 text-justify leading-relaxed text-[var(--text-primary)] transition-colors duration-150">
          <InlineRunRenderer runs={block.runs} onSourceAnchorClick={onSourceAnchorClick} />
        </p>
      );
    case 'quotation':
      return (
        <blockquote className="my-5 rounded-r-xl border-l-4 border-[var(--accent)] bg-[var(--bg-secondary)]/50 py-3 px-5 text-justify italic text-[var(--text-primary)] shadow-xs">
          <p><InlineRunRenderer runs={block.runs} onSourceAnchorClick={onSourceAnchorClick} /></p>
          {block.attribution && (
            <footer className="mt-2 text-right text-xs not-italic font-medium text-[var(--text-secondary)]">
              — <InlineRunRenderer runs={block.attribution} onSourceAnchorClick={onSourceAnchorClick} />
            </footer>
          )}
        </blockquote>
      );
    case 'list': {
      const List = block.ordered ? 'ol' : 'ul';
      const listClasses = block.ordered
        ? 'my-4 space-y-2 pl-6 list-decimal text-[var(--text-primary)]'
        : 'my-4 space-y-2 pl-6 list-disc text-[var(--text-primary)]';
      return (
        <List className={listClasses}>
          {block.items.map((item, index) => (
            <li key={`${block.id}-item-${index}`} className="leading-relaxed">
              {item.map((child) => (
                <DocumentBlockRenderer
                  key={child.id}
                  block={child}
                  onFootnoteClick={onFootnoteClick}
                  onSourceAnchorClick={onSourceAnchorClick}
                />
              ))}
            </li>
          ))}
        </List>
      );
    }
    case 'table':
      if (block.rows.length === 0 && block.fallbackImageRef) {
        return (
          <div className="my-6 text-center">
            <img src={block.fallbackImageRef} alt="Таблица или схема" className="mx-auto max-w-full rounded-xl border border-[var(--border-subtle)] shadow-xs" />
          </div>
        );
      }
      return (
        <div className="my-6 overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-card)] shadow-xs">
          <table className="w-full border-collapse text-sm">
            <tbody>
              {block.rows.map((row, rowIndex) => (
                <tr key={`${block.id}-row-${rowIndex}`} className="transition-colors hover:bg-[var(--bg-secondary)]/40">
                  {row.map((cell, cellIndex) => (
                    <td key={`${block.id}-cell-${rowIndex}-${cellIndex}`} className="border-b border-[var(--border-subtle)] px-4 py-2.5 text-[var(--text-primary)]">
                      <InlineRunRenderer runs={cell} onSourceAnchorClick={onSourceAnchorClick} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    case 'figure':
      return (
        <figure className="my-8 overflow-hidden rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-4 shadow-sm transition-all duration-200 hover:shadow-md text-center">
          <img
            src={block.imageRef}
            alt={block.alt || (typeof block.caption === 'string' ? block.caption : 'Иллюстрация')}
            className="mx-auto max-h-[500px] w-auto max-w-full rounded-lg object-contain shadow-xs"
          />
          {block.caption && (
            <figcaption className="mt-3 border-t border-[var(--border-subtle)]/60 pt-2.5 text-center text-xs font-medium tracking-wide text-[var(--text-secondary)]">
              {Array.isArray(block.caption) ? (
                <InlineRunRenderer runs={block.caption} onSourceAnchorClick={onSourceAnchorClick} />
              ) : (
                block.caption
              )}
            </figcaption>
          )}
        </figure>
      );
    case 'footnote':
      return (
        <aside aria-label={`Сноска ${block.label}`} data-footnote-anchors={block.anchors.join(' ')} className="my-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-secondary)]/30 p-3 text-xs text-[var(--text-secondary)]">
          <button
            type="button"
            onClick={() => onFootnoteClick?.(block)}
            className="mr-2 inline-flex h-5 w-5 items-center justify-center rounded bg-[var(--accent-soft)] font-mono text-[11px] font-bold text-[var(--accent)] transition-transform hover:scale-105 active:scale-95 cursor-pointer focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
          >
            {block.label}
          </button>
          <div className="inline">
            {block.blocks.map((child) => (
              <DocumentBlockRenderer
                key={child.id}
                block={child}
                onFootnoteClick={onFootnoteClick}
                onSourceAnchorClick={onSourceAnchorClick}
              />
            ))}
          </div>
        </aside>
      );
    case 'pageBreak':
      return <div role="separator" aria-label={`Переход к странице ${block.printedPageLabel ?? block.pdfPageIndex + 1}`} className="my-8 border-b border-dashed border-[var(--border-subtle)] opacity-40" />;
  }
}

export const DocumentBlockRenderer: FC<DocumentBlockRendererProps> = ({
  block,
  onFootnoteClick,
  onSourceAnchorClick,
}) => (
  <section data-block-id={block.id} data-block-type={block.type}>
    {renderBlockContent(block, onFootnoteClick, onSourceAnchorClick)}
    {onSourceAnchorClick && firstSourceAnchor(block) && (
      <button
        type="button"
        className="sr-only focus:not-sr-only"
        data-source-action="true"
        data-testid={`source-action-${block.id}`}
        aria-label={`Открыть источник для ${blockText(block).slice(0, 60)}`}
        onClick={() => onSourceAnchorClick(firstSourceAnchor(block)!)}
      >
        Открыть источник
      </button>
    )}
  </section>
);

export const PageV2Renderer: FC<PageV2RendererProps> = ({
  page,
  onFootnoteClick,
  onSourceAnchorClick,
}) => (
  <article data-page-number={page.pageNumber}>
    {page.chapterTitle && <header><h1>{page.chapterTitle}</h1></header>}
    <div>
      {page.blocks.map((block) => (
        <DocumentBlockRenderer
          key={block.id}
          block={block}
          onFootnoteClick={onFootnoteClick}
          onSourceAnchorClick={onSourceAnchorClick}
        />
      ))}
    </div>
  </article>
);
