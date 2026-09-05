import type { FC, ReactNode } from 'react';
import { Sparkles, Quote, Bookmark } from 'lucide-react';
import type { PageData, ReaderSettings, FootnotePair, ResearchCard } from '../domain/types';

interface ReaderContentProps {
  page: PageData;
  settings: ReaderSettings;
  cards: ResearchCard[];
  hoveredParagraphId: string | null;
  onHoverParagraph: (id: string | null) => void;
  onSelectFootnote: (footnote: FootnotePair) => void;
  onOpenScan?: () => void;
  onOpenCreateCard: (data: {
    pageNumber: number;
    paragraphId?: string;
    quote: string;
    quoteLanguage: 'ru' | 'en';
  }) => void;
  onOpenCards: () => void;
}

export const ReaderContent: FC<ReaderContentProps> = ({
  page,
  settings,
  cards,
  hoveredParagraphId,
  onHoverParagraph,
  onSelectFootnote,
  onOpenCreateCard,
  onOpenCards,
}) => {
  // Helper to parse footnote numbers into clickable elements
  const renderTextWithFootnotes = (text: string, isRu: boolean) => {
    const footnoteMap = new Map<number, FootnotePair>();
    page.footnotes.forEach(fn => footnoteMap.set(fn.id, fn));

    const parts: ReactNode[] = [];
    const regex = /([¹²³⁴⁵⁶⁷⁸⁹]+|\^\[\d+\]|(?<=\S)\[\d+\])/g;
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    const superscriptToNum = (s: string) => {
      const supMap: Record<string, string> = {
        '¹': '1', '²': '2', '³': '3', '⁴': '4', '⁵': '5',
        '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9', '⁰': '0'
      };
      return parseInt(s.split('').map(c => supMap[c] || c).join(''), 10);
    };

    while ((match = regex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        parts.push(text.slice(lastIndex, match.index));
      }

      const raw = match[0];
      let fnId: number;
      if (raw.startsWith('[') || raw.startsWith('^[')) {
        fnId = parseInt(raw.replace(/\D/g, ''), 10);
      } else {
        fnId = superscriptToNum(raw);
      }

      const fnData = footnoteMap.get(fnId);

      parts.push(
        <button
          key={`fn-${match.index}`}
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            if (fnData) {
              onSelectFootnote(fnData);
            }
          }}
          title={fnData ? (isRu ? fnData.textRu : fnData.textEn) : `Сноска ${fnId}`}
          className="mx-0.5 inline-flex items-center justify-center rounded px-1 py-0 text-[0.7em] font-bold transition-all hover:scale-110 active:scale-95 cursor-pointer"
          style={{
            color: 'var(--accent)',
            backgroundColor: 'var(--accent-soft)',
            verticalAlign: 'super',
            lineHeight: 1,
          }}
        >
          {fnId}
        </button>
      );

      lastIndex = regex.lastIndex;
    }

    if (lastIndex < text.length) {
      parts.push(text.slice(lastIndex));
    }

    return parts.length > 0 ? parts : text;
  };

  const fontFamilyStyle = settings.fontFamily === 'serif' ? 'var(--font-serif)' : 'var(--font-sans)';

  const getCardsForParagraph = (paraId: string) => {
    return cards.filter(c => c.paragraphId === paraId || (c.pageNumber === page.pageNumber && !c.paragraphId));
  };

  return (
    <article
      className="mx-auto w-full transition-all duration-200"
      style={{
        maxWidth: settings.mode === 'bilingual' ? '1280px' : `${settings.maxWidth}px`,
        fontFamily: fontFamilyStyle,
      }}
    >
      {/* Chapter / Section Header Banner */}
      {page.chapterTitle && (
        <header className="mb-8 border-b pb-4 text-center sm:mb-12" style={{ borderColor: 'var(--border-subtle)' }}>
          <div className="flex items-center justify-center space-x-2 text-xs font-semibold tracking-widest uppercase opacity-70"
            style={{ color: 'var(--accent)' }}
          >
            <Sparkles className="h-3.5 w-3.5" />
            <span>Приложение • Богословие Нового Завета</span>
          </div>
          <h1 className="mt-2 text-xl font-bold tracking-tight sm:text-2xl lg:text-3xl" style={{ color: 'var(--text-primary)' }}>
            {settings.mode === 'en' ? page.chapterTitle : (page.chapterTitle === 'Appendix: Reflections on New Testament Theology' ? 'Размышления о богословии Нового Завета' : page.chapterTitle)}
          </h1>
          <div className="mt-2 flex items-center justify-center space-x-3 text-xs opacity-60" style={{ color: 'var(--text-secondary)' }}>
            <span>Страница {page.pageNumber}</span>
            <span>•</span>
            <span>~{page.readingTimeMinutes || 2} мин на чтение</span>
          </div>
        </header>
      )}

      {/* Mode 1: Russian Editorial Reading View */}
      {settings.mode === 'ru' && (
        <div className="space-y-6">
          {page.paragraphs.map((para, idx) => {
            const isHeading = para.en.length < 50 && !para.en.includes('.') && !para.en.includes(';');
            if (isHeading) {
              return (
                <h2
                  key={para.id}
                  className="pt-4 text-lg font-bold tracking-tight sm:text-xl"
                  style={{ color: 'var(--text-primary)' }}
                >
                  {para.ru}
                </h2>
              );
            }

            // Drop cap only at the beginning of chapters (e.g. page 867, 870, 874, 879) on the very first paragraph
            const isChapterStartPage = [867, 870, 874, 879].includes(page.pageNumber);
            const useDropCap = settings.showDropCap && isChapterStartPage && idx === 0;
            const paraCards = getCardsForParagraph(para.id);

            return (
              <div
                key={para.id}
                data-paragraph-id={para.id}
                data-lang="ru"
                className="group relative rounded-xl p-2 -mx-2 transition-all"
                style={{
                  backgroundColor: paraCards.length > 0 ? 'var(--accent-soft)' : 'transparent',
                }}
              >
                <p
                  className={`text-justify transition-colors duration-150 ${useDropCap ? 'drop-cap' : ''}`}
                  style={{
                    fontSize: `${settings.fontSize}px`,
                    lineHeight: settings.lineHeight,
                    color: 'var(--text-primary)',
                  }}
                >
                  {renderTextWithFootnotes(para.ru, true)}
                </p>

                {/* Paragraph Action Toolbar on hover / active */}
                <div className="mt-2 flex items-center space-x-2 text-xs opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    type="button"
                    onClick={() =>
                      onOpenCreateCard({
                        pageNumber: page.pageNumber,
                        paragraphId: para.id,
                        quote: para.ru,
                        quoteLanguage: 'ru',
                      })
                    }
                    className="inline-flex items-center space-x-1 rounded-md px-2 py-1 font-medium transition-all hover:opacity-80 active:scale-95 cursor-pointer"
                    style={{ backgroundColor: 'var(--bg-secondary)', color: 'var(--accent)', border: '1px solid var(--border-subtle)' }}
                  >
                    <Quote className="h-3 w-3" />
                    <span>+ Карточка мысли</span>
                  </button>

                  {paraCards.length > 0 && (
                    <button
                      type="button"
                      onClick={onOpenCards}
                      className="inline-flex items-center space-x-1 rounded-md px-2 py-1 font-medium cursor-pointer"
                      style={{ backgroundColor: 'var(--accent)', color: 'white' }}
                    >
                      <Bookmark className="h-3 w-3" />
                      <span>{paraCards.length} {paraCards.length === 1 ? 'карточка' : 'карточки'}</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Mode 2: Bilingual Synchronized Side-by-Side */}
      {settings.mode === 'bilingual' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 lg:gap-10">
          {/* English Column */}
          <section aria-label="English Original" className="space-y-6">
            <div className="sticky top-16 z-10 flex items-center justify-between border-b pb-1.5 backdrop-blur-md"
              style={{ borderColor: 'var(--border-subtle)', backgroundColor: 'var(--bg-primary)' }}
            >
              <span className="text-xs font-bold uppercase tracking-wider opacity-60" style={{ color: 'var(--text-secondary)' }}>
                English Original (Schreiner, 2008)
              </span>
              <span className="text-[11px] opacity-40 font-mono">Page {page.pageNumber}</span>
            </div>

            {page.paragraphs.map((para) => {
              const isHighlighted = hoveredParagraphId === para.id;
              const isHeading = para.en.length < 50 && !para.en.includes('.') && !para.en.includes(';');

              if (isHeading) {
                return (
                  <h2 key={`en-${para.id}`} className="pt-2 text-base font-bold tracking-tight sm:text-lg" style={{ color: 'var(--text-primary)' }}>
                    {para.en}
                  </h2>
                );
              }

              const paraCards = getCardsForParagraph(para.id);

              return (
                <div
                  key={`en-${para.id}`}
                  data-paragraph-id={para.id}
                  data-lang="en"
                  onMouseEnter={() => onHoverParagraph(para.id)}
                  onMouseLeave={() => onHoverParagraph(null)}
                  className={`group relative rounded-lg p-2.5 text-justify transition-all duration-150 ${
                    isHighlighted ? 'ring-1' : ''
                  }`}
                  style={{
                    fontSize: `${settings.fontSize}px`,
                    lineHeight: settings.lineHeight,
                    color: 'var(--text-primary)',
                    backgroundColor: isHighlighted ? 'var(--accent-soft)' : (paraCards.length > 0 ? 'var(--accent-soft)' : 'transparent'),
                    borderColor: 'var(--accent)',
                  }}
                >
                  {renderTextWithFootnotes(para.en, false)}

                  <div className="mt-2 flex items-center space-x-2 text-[11px] opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      type="button"
                      onClick={() =>
                        onOpenCreateCard({
                          pageNumber: page.pageNumber,
                          paragraphId: para.id,
                          quote: para.en,
                          quoteLanguage: 'en',
                        })
                      }
                      className="inline-flex items-center space-x-1 rounded px-1.5 py-0.5 font-medium transition-all hover:opacity-80 active:scale-95 cursor-pointer"
                      style={{ backgroundColor: 'var(--bg-secondary)', color: 'var(--accent)', border: '1px solid var(--border-subtle)' }}
                    >
                      <Quote className="h-2.5 w-2.5" />
                      <span>+ Card</span>
                    </button>
                    {paraCards.length > 0 && (
                      <button
                        type="button"
                        onClick={onOpenCards}
                        className="inline-flex items-center space-x-1 rounded px-1.5 py-0.5 font-semibold text-white cursor-pointer"
                        style={{ backgroundColor: 'var(--accent)' }}
                      >
                        <span>{paraCards.length} {paraCards.length === 1 ? 'card' : 'cards'}</span>
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </section>

          {/* Russian Column */}
          <section aria-label="Russian Translation" className="space-y-6">
            <div className="sticky top-16 z-10 flex items-center justify-between border-b pb-1.5 backdrop-blur-md"
              style={{ borderColor: 'var(--border-subtle)', backgroundColor: 'var(--bg-primary)' }}
            >
              <span className="text-xs font-bold uppercase tracking-wider opacity-60" style={{ color: 'var(--accent)' }}>
                Русский академический перевод
              </span>
              <span className="text-[11px] opacity-40 font-mono">Стр. {page.pageNumber}</span>
            </div>

            {page.paragraphs.map((para) => {
              const isHighlighted = hoveredParagraphId === para.id;
              const isHeading = para.en.length < 50 && !para.en.includes('.') && !para.en.includes(';');

              if (isHeading) {
                return (
                  <h2 key={`ru-${para.id}`} className="pt-2 text-base font-bold tracking-tight sm:text-lg" style={{ color: 'var(--accent)' }}>
                    {para.ru}
                  </h2>
                );
              }

              const paraCards = getCardsForParagraph(para.id);

              return (
                <div
                  key={`ru-${para.id}`}
                  data-paragraph-id={para.id}
                  data-lang="ru"
                  onMouseEnter={() => onHoverParagraph(para.id)}
                  onMouseLeave={() => onHoverParagraph(null)}
                  className={`group relative rounded-lg p-2.5 text-justify transition-all duration-150 ${
                    isHighlighted ? 'ring-1' : ''
                  }`}
                  style={{
                    fontSize: `${settings.fontSize}px`,
                    lineHeight: settings.lineHeight,
                    color: 'var(--text-primary)',
                    backgroundColor: isHighlighted ? 'var(--accent-soft)' : (paraCards.length > 0 ? 'var(--accent-soft)' : 'transparent'),
                    borderColor: 'var(--accent)',
                  }}
                >
                  {renderTextWithFootnotes(para.ru, true)}

                  <div className="mt-2 flex items-center space-x-2 text-[11px] opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      type="button"
                      onClick={() =>
                        onOpenCreateCard({
                          pageNumber: page.pageNumber,
                          paragraphId: para.id,
                          quote: para.ru,
                          quoteLanguage: 'ru',
                        })
                      }
                      className="inline-flex items-center space-x-1 rounded px-1.5 py-0.5 font-medium transition-all hover:opacity-80 active:scale-95 cursor-pointer"
                      style={{ backgroundColor: 'var(--bg-secondary)', color: 'var(--accent)', border: '1px solid var(--border-subtle)' }}
                    >
                      <Quote className="h-2.5 w-2.5" />
                      <span>+ Карточка мысли</span>
                    </button>
                    {paraCards.length > 0 && (
                      <button
                        type="button"
                        onClick={onOpenCards}
                        className="inline-flex items-center space-x-1 rounded px-1.5 py-0.5 font-semibold text-white cursor-pointer"
                        style={{ backgroundColor: 'var(--accent)' }}
                      >
                        <span>{paraCards.length} {paraCards.length === 1 ? 'карточка' : 'карточки'}</span>
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </section>
        </div>
      )}

      {/* Mode 3: English Original View */}
      {settings.mode === 'en' && (
        <div className="space-y-6">
          {page.paragraphs.map((para, idx) => {
            const isHeading = para.en.length < 50 && !para.en.includes('.') && !para.en.includes(';');
            if (isHeading) {
              return (
                <h2
                  key={para.id}
                  className="pt-4 text-lg font-bold tracking-tight sm:text-xl"
                  style={{ color: 'var(--text-primary)' }}
                >
                  {para.en}
                </h2>
              );
            }

            const isChapterStartPage = [867, 870, 874, 879].includes(page.pageNumber);
            const useDropCap = settings.showDropCap && isChapterStartPage && idx === 0;
            const paraCards = getCardsForParagraph(para.id);

            return (
              <div
                key={para.id}
                data-paragraph-id={para.id}
                data-lang="en"
                className="group relative rounded-xl p-2 -mx-2 transition-all"
                style={{
                  backgroundColor: paraCards.length > 0 ? 'var(--accent-soft)' : 'transparent',
                }}
              >
                <p
                  className={`text-justify transition-colors duration-150 ${useDropCap ? 'drop-cap' : ''}`}
                  style={{
                    fontSize: `${settings.fontSize}px`,
                    lineHeight: settings.lineHeight,
                    color: 'var(--text-primary)',
                  }}
                >
                  {renderTextWithFootnotes(para.en, false)}
                </p>

                <div className="mt-2 flex items-center space-x-2 text-xs opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    type="button"
                    onClick={() =>
                      onOpenCreateCard({
                        pageNumber: page.pageNumber,
                        paragraphId: para.id,
                        quote: para.en,
                        quoteLanguage: 'en',
                      })
                    }
                    className="inline-flex items-center space-x-1 rounded-md px-2 py-1 font-medium transition-all hover:opacity-80 active:scale-95 cursor-pointer"
                    style={{ backgroundColor: 'var(--bg-secondary)', color: 'var(--accent)', border: '1px solid var(--border-subtle)' }}
                  >
                    <Quote className="h-3 w-3" />
                    <span>+ Research Card</span>
                  </button>

                  {paraCards.length > 0 && (
                    <button
                      type="button"
                      onClick={onOpenCards}
                      className="inline-flex items-center space-x-1 rounded-md px-2 py-1 font-medium cursor-pointer"
                      style={{ backgroundColor: 'var(--accent)', color: 'white' }}
                    >
                      <Bookmark className="h-3 w-3" />
                      <span>{paraCards.length} {paraCards.length === 1 ? 'card' : 'cards'}</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Footnotes Section at Bottom of Page */}
      {page.footnotes && page.footnotes.length > 0 && (
        <footer className="mt-14 border-t pt-6" style={{ borderColor: 'var(--border-subtle)' }}>
          <h3 className="mb-4 text-xs font-bold uppercase tracking-wider opacity-60" style={{ color: 'var(--text-secondary)' }}>
            Сноски и библиографические примечания ({page.footnotes.length})
          </h3>
          <ol className="space-y-3 pl-2 text-xs" style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            {page.footnotes.map((fn) => (
              <li
                key={fn.id}
                onClick={() => onSelectFootnote(fn)}
                className="group flex items-start space-x-2.5 rounded-lg p-2 transition-all hover:bg-opacity-50 cursor-pointer"
                style={{ backgroundColor: 'transparent' }}
              >
                <span
                  className="flex h-5 w-5 shrink-0 items-center justify-center rounded font-semibold text-[11px]"
                  style={{ backgroundColor: 'var(--accent-soft)', color: 'var(--accent)' }}
                >
                  {fn.id}
                </span>
                <div className="flex-1 space-y-1">
                  <div className="font-medium" style={{ color: 'var(--text-primary)' }}>
                    {fn.textRu}
                  </div>
                  <div className="text-[11px] opacity-75 font-serif italic" style={{ color: 'var(--text-secondary)' }}>
                    {fn.textEn}
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </footer>
      )}
    </article>
  );
};
