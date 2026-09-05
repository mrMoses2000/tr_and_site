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
      const Heading = `h${block.level}` as 'h1' | 'h2' | 'h3' | 'h4';
      return <Heading><InlineRunRenderer runs={block.runs} onSourceAnchorClick={onSourceAnchorClick} /></Heading>;
    }
    case 'paragraph':
      return <p><InlineRunRenderer runs={block.runs} onSourceAnchorClick={onSourceAnchorClick} /></p>;
    case 'quotation':
      return (
        <blockquote>
          <p><InlineRunRenderer runs={block.runs} onSourceAnchorClick={onSourceAnchorClick} /></p>
          {block.attribution && (
            <footer>— <InlineRunRenderer runs={block.attribution} onSourceAnchorClick={onSourceAnchorClick} /></footer>
          )}
        </blockquote>
      );
    case 'list': {
      const List = block.ordered ? 'ol' : 'ul';
      return (
        <List>
          {block.items.map((item, index) => (
            <li key={`${block.id}-item-${index}`}>
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
        return <img src={block.fallbackImageRef} alt="Таблица или схема" />;
      }
      return (
        <div className="overflow-x-auto">
          <table>
            <tbody>
              {block.rows.map((row, rowIndex) => (
                <tr key={`${block.id}-row-${rowIndex}`}>
                  {row.map((cell, cellIndex) => (
                    <td key={`${block.id}-cell-${rowIndex}-${cellIndex}`}>
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
        <figure className="my-6 text-center">
          <img src={block.imageRef} alt={block.alt || (typeof block.caption === 'string' ? block.caption : 'Иллюстрация')} className="mx-auto max-w-full rounded-lg shadow-sm" />
          {block.caption && (
            <figcaption className="mt-2 text-sm text-neutral-600 dark:text-neutral-400">
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
        <aside aria-label={`Сноска ${block.label}`} data-footnote-anchors={block.anchors.join(' ')}>
          <button type="button" onClick={() => onFootnoteClick?.(block)}>{block.label}</button>
          <div>{block.blocks.map((child) => (
            <DocumentBlockRenderer
              key={child.id}
              block={child}
              onFootnoteClick={onFootnoteClick}
              onSourceAnchorClick={onSourceAnchorClick}
            />
          ))}</div>
        </aside>
      );
    case 'pageBreak':
      return <div role="separator" aria-label={`Переход к странице ${block.printedPageLabel ?? block.pdfPageIndex + 1}`} />;
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
