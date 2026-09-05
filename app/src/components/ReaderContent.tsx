import type { FC, ReactNode } from 'react';
import { MessageSquare, ExternalLink, Sparkles } from 'lucide-react';
import type { PageData, ReaderSettings, FootnotePair } from '../domain/types';

interface ReaderContentProps {
  page: PageData;
  settings: ReaderSettings;
  hoveredParagraphId: string | null;
  onHoverParagraph: (id: string | null) => void;
  onSelectFootnote: (footnote: FootnotePair) => void;
  onOpenScan: () => void;
}

export const ReaderContent: FC<ReaderContentProps> = ({
  page,
  settings,
  hoveredParagraphId,
  onHoverParagraph,
  onSelectFootnote,
  onOpenScan,
}) => {
  // Helper to parse footnote numbers into clickable elements
  const renderTextWithFootnotes = (text: string, isRu: boolean) => {
    // Regex matches footnote superscripts like ¹, ², ³, ⁴, ⁵ or bracketed numbers or standard numbers after words
    // Or we look up footnotes for this page
    const footnoteMap = new Map<number, FootnotePair>();
    page.footnotes.forEach(fn => footnoteMap.set(fn.id, fn));

    // Match superscripts ¹-⁹ or numbers like [1] or plain footnote indicators
    const parts: ReactNode[] = [];
    const regex = /([¹²³⁴⁵⁶⁷⁸⁹]+|\^\[\d+\]|(?<=\S)\[\d+\])/g;
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    // Mapping unicode superscripts to numbers
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

      {/* Margin Notes / Editorial Callout if present on this physical scan */}
      {page.marginNotes && page.marginNotes.length > 0 && (
        <aside
          className="mb-8 rounded-xl border p-4 shadow-xs transition-all sm:p-5"
          style={{
            backgroundColor: 'var(--bg-secondary)',
            borderColor: 'var(--border-strong)',
          }}
        >
          <div className="flex items-start space-x-3">
            <div className="rounded-lg p-1.5" style={{ backgroundColor: 'var(--accent-soft)', color: 'var(--accent)' }}>
              <MessageSquare className="h-4 w-4" />
            </div>
            <div className="flex-1 text-xs sm:text-sm">
              <span className="font-semibold" style={{ color: 'var(--accent)' }}>Пометы на полях оригинала книги:</span>
              <ul className="mt-1.5 list-disc space-y-1 pl-4 opacity-90" style={{ color: 'var(--text-secondary)' }}>
                {page.marginNotes.map((note, idx) => (
                  <li key={idx}>{note}</li>
                ))}
              </ul>
            </div>
            <button
              type="button"
              onClick={onOpenScan}
              className="flex items-center space-x-1 rounded-md px-2 py-1 text-xs font-medium transition-all hover:opacity-80 active:scale-95"
              style={{ backgroundColor: 'var(--bg-card)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)' }}
            >
              <span>Скан</span>
              <ExternalLink className="h-3 w-3" />
            </button>
          </div>
        </aside>
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

            const isFirstPara = idx === 0 || (idx === 1 && page.paragraphs[0].en.length < 50);
            const useDropCap = settings.showDropCap && isFirstPara;

            return (
              <p
                key={para.id}
                className={`text-justify transition-colors duration-150 ${useDropCap ? 'drop-cap' : ''}`}
                style={{
                  fontSize: `${settings.fontSize}px`,
                  lineHeight: settings.lineHeight,
                  color: 'var(--text-primary)',
                }}
              >
                {renderTextWithFootnotes(para.ru, true)}
              </p>
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

              return (
                <div
                  key={`en-${para.id}`}
                  onMouseEnter={() => onHoverParagraph(para.id)}
                  onMouseLeave={() => onHoverParagraph(null)}
                  className={`rounded-lg p-2.5 text-justify transition-all duration-150 ${
                    isHighlighted ? 'ring-1' : ''
                  }`}
                  style={{
                    fontSize: `${settings.fontSize}px`,
                    lineHeight: settings.lineHeight,
                    color: 'var(--text-primary)',
                    backgroundColor: isHighlighted ? 'var(--accent-soft)' : 'transparent',
                    borderColor: 'var(--accent)',
                  }}
                >
                  {renderTextWithFootnotes(para.en, false)}
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

              return (
                <div
                  key={`ru-${para.id}`}
                  onMouseEnter={() => onHoverParagraph(para.id)}
                  onMouseLeave={() => onHoverParagraph(null)}
                  className={`rounded-lg p-2.5 text-justify transition-all duration-150 ${
                    isHighlighted ? 'ring-1' : ''
                  }`}
                  style={{
                    fontSize: `${settings.fontSize}px`,
                    lineHeight: settings.lineHeight,
                    color: 'var(--text-primary)',
                    backgroundColor: isHighlighted ? 'var(--accent-soft)' : 'transparent',
                    borderColor: 'var(--accent)',
                  }}
                >
                  {renderTextWithFootnotes(para.ru, true)}
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

            const isFirstPara = idx === 0 || (idx === 1 && page.paragraphs[0].en.length < 50);
            const useDropCap = settings.showDropCap && isFirstPara;

            return (
              <p
                key={para.id}
                className={`text-justify transition-colors duration-150 ${useDropCap ? 'drop-cap' : ''}`}
                style={{
                  fontSize: `${settings.fontSize}px`,
                  lineHeight: settings.lineHeight,
                  color: 'var(--text-primary)',
                }}
              >
                {renderTextWithFootnotes(para.en, false)}
              </p>
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
