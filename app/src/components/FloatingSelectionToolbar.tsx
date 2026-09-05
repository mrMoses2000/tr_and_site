import { useState, useEffect, type FC } from 'react';
import { Quote } from 'lucide-react';

interface FloatingSelectionToolbarProps {
  currentPage: number;
  onOpenCreateCard: (data: {
    pageNumber: number;
    paragraphId?: string;
    quote: string;
    quoteLanguage: 'ru' | 'en';
  }) => void;
}

export const FloatingSelectionToolbar: FC<FloatingSelectionToolbarProps> = ({
  currentPage,
  onOpenCreateCard,
}) => {
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null);
  const [selectedText, setSelectedText] = useState('');
  const [quoteLang, setQuoteLang] = useState<'ru' | 'en'>('ru');
  const [paragraphId, setParagraphId] = useState<string | undefined>();

  useEffect(() => {
    const handleSelectionChange = () => {
      const selection = window.getSelection();
      if (!selection || selection.isCollapsed || !selection.toString().trim()) {
        setPosition(null);
        return;
      }

      const text = selection.toString().trim();
      if (text.length < 3) {
        setPosition(null);
        return;
      }

      // Check if selection is inside reader container
      const range = selection.getRangeAt(0);
      const container = document.getElementById('reader-scroll-container');
      if (!container || !container.contains(range.commonAncestorContainer)) {
        setPosition(null);
        return;
      }

      // Determine language & paragraph id
      let node: Node | null = range.commonAncestorContainer;
      let detectedLang: 'ru' | 'en' = 'ru';
      let foundParaId: string | undefined;

      while (node && node !== container) {
        if (node instanceof HTMLElement) {
          if (node.dataset.paragraphId) {
            foundParaId = node.dataset.paragraphId;
          }
          if (node.dataset.lang === 'en') {
            detectedLang = 'en';
          } else if (node.dataset.lang === 'ru') {
            detectedLang = 'ru';
          }
        }
        node = node.parentNode;
      }

      const rect = range.getBoundingClientRect();
      // Position toolbar centered above selection
      setPosition({
        x: rect.left + rect.width / 2,
        y: Math.max(10, rect.top - 46),
      });
      setSelectedText(text);
      setQuoteLang(detectedLang);
      setParagraphId(foundParaId);
    };

    document.addEventListener('mouseup', handleSelectionChange);
    document.addEventListener('keyup', handleSelectionChange);

    return () => {
      document.removeEventListener('mouseup', handleSelectionChange);
      document.removeEventListener('keyup', handleSelectionChange);
    };
  }, []);

  if (!position || !selectedText) return null;

  const handleCreate = () => {
    onOpenCreateCard({
      pageNumber: currentPage,
      paragraphId,
      quote: selectedText,
      quoteLanguage: quoteLang,
    });
    setPosition(null);
    window.getSelection()?.removeAllRanges();
  };

  return (
    <div
      className="fixed z-40 -translate-x-1/2 flex items-center shadow-xl rounded-full border px-3 py-1.5 backdrop-blur-md transition-all animate-in fade-in zoom-in-95 duration-150"
      style={{
        left: `${position.x}px`,
        top: `${position.y}px`,
        backgroundColor: 'var(--bg-card)',
        borderColor: 'var(--accent)',
        color: 'var(--text-primary)',
      }}
    >
      <button
        type="button"
        onMouseDown={(e) => {
          e.preventDefault(); // Don't lose selection before handleCreate
          handleCreate();
        }}
        className="flex items-center space-x-1.5 text-xs font-semibold hover:opacity-80 active:scale-95 transition-transform cursor-pointer"
        style={{ color: 'var(--accent)' }}
      >
        <Quote className="h-3.5 w-3.5" />
        <span>Создать карточку мысли</span>
      </button>
    </div>
  );
};
