import { useState, type FC, type MouseEvent } from 'react';
import {
  X,
  ZoomIn,
  ZoomOut,
  RotateCw,
  Maximize2,
  Columns,
  Image as ImageIcon,
  ExternalLink,
} from 'lucide-react';
import type { PageData } from '../domain/types';

interface ScanViewerProps {
  page: PageData;
  isOpen: boolean;
  isSplit: boolean;
  onClose: () => void;
  onToggleSplit: () => void;
}

export const ScanViewer: FC<ScanViewerProps> = ({
  page,
  isOpen,
  isSplit,
  onClose,
  onToggleSplit,
}) => {
  const [zoom, setZoom] = useState<number>(1);
  const [rotation, setRotation] = useState<number>(0);
  const [isPanning, setIsPanning] = useState<boolean>(false);
  const [position, setPosition] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [startPos, setStartPos] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  if (!isOpen) return null;

  const handleZoomIn = () => setZoom(z => Math.min(z + 0.3, 3.5));
  const handleZoomOut = () => setZoom(z => Math.max(z - 0.3, 0.6));
  const handleResetZoom = () => {
    setZoom(1);
    setRotation(0);
    setPosition({ x: 0, y: 0 });
  };
  const handleRotate = () => setRotation(r => (r + 90) % 360);

  const handleMouseDown = (e: MouseEvent) => {
    if (zoom > 1) {
      setIsPanning(true);
      setStartPos({ x: e.clientX - position.x, y: e.clientY - position.y });
    }
  };

  const handleMouseMove = (e: MouseEvent) => {
    if (isPanning && zoom > 1) {
      setPosition({
        x: e.clientX - startPos.x,
        y: e.clientY - startPos.y,
      });
    }
  };

  const handleMouseUp = () => setIsPanning(false);

  // If in Split view mode, render as a persistent right-hand drawer
  if (isSplit) {
    return (
      <aside
        className="fixed top-14 right-0 bottom-14 z-20 flex w-full flex-col border-l shadow-xl transition-all md:w-1/2 lg:w-5/12"
        style={{
          backgroundColor: 'var(--bg-secondary)',
          borderColor: 'var(--border-strong)',
        }}
      >
        {/* Split Header */}
        <div className="flex h-12 items-center justify-between border-b px-4" style={{ borderColor: 'var(--border-subtle)', backgroundColor: 'var(--bg-card)' }}>
          <div className="flex items-center space-x-2">
            <ImageIcon className="h-4 w-4" style={{ color: 'var(--accent)' }} />
            <span className="text-xs font-semibold">Скан оригинала: стр. {page.pageNumber}</span>
          </div>

          <div className="flex items-center space-x-1">
            <button
              type="button"
              onClick={handleZoomIn}
              title="Приблизить"
              className="rounded p-1 hover:bg-black/10"
            >
              <ZoomIn className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={handleZoomOut}
              title="Отдалить"
              className="rounded p-1 hover:bg-black/10"
            >
              <ZoomOut className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={handleResetZoom}
              title="Сброс"
              className="rounded px-1.5 py-0.5 text-[10px] font-mono hover:bg-black/10"
            >
              {Math.round(zoom * 100)}%
            </button>
            <button
              type="button"
              onClick={onToggleSplit}
              title="Развернуть на весь экран"
              className="rounded p-1 hover:bg-black/10"
            >
              <Maximize2 className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={onClose}
              title="Закрыть скан"
              className="rounded p-1 hover:bg-black/10"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {/* Scan Image Container */}
        <div
          className="relative flex-1 overflow-hidden p-2 select-none"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          style={{ cursor: zoom > 1 ? (isPanning ? 'grabbing' : 'grab') : 'default' }}
        >
          <img
            src={page.imageSrc}
            alt={`Фотография страницы ${page.pageNumber}`}
            draggable={false}
            className="h-full w-full object-contain rounded-md shadow-sm transition-transform duration-100 ease-out"
            style={{
              transform: `translate(${position.x}px, ${position.y}px) scale(${zoom}) rotate(${rotation}deg)`,
            }}
          />
        </div>
      </aside>
    );
  }

  // Fullscreen / Modal mode
  return (
    <div
      className="fixed inset-0 z-50 flex flex-col bg-black/80 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={onClose}
    >
      {/* Top Controls Bar */}
      <div
        className="flex h-14 items-center justify-between border-b px-4 text-white sm:px-6"
        style={{ backgroundColor: 'rgba(20, 20, 24, 0.9)', borderColor: 'rgba(255, 255, 255, 0.1)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center space-x-3">
          <span className="flex items-center space-x-2 text-sm font-semibold tracking-tight">
            <ImageIcon className="h-4 w-4 text-amber-400" />
            <span>Оригинальный скан • Стр. {page.pageNumber}</span>
          </span>
          <a
            href={page.imageSrc}
            target="_blank"
            rel="noreferrer"
            title="Открыть изображение в новой вкладке"
            className="flex items-center space-x-1 rounded-md bg-white/10 px-2 py-1 text-xs text-white/80 hover:bg-white/20 transition-all"
          >
            <span>В новой вкладке</span>
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>

        <div className="flex items-center space-x-2">
          {/* Zoom & Rotate Controls */}
          <div className="flex items-center rounded-lg bg-white/10 p-0.5">
            <button
              type="button"
              onClick={handleZoomIn}
              title="Увеличить (+)"
              className="rounded p-1.5 hover:bg-white/15 text-white"
            >
              <ZoomIn className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={handleZoomOut}
              title="Уменьшить (-)"
              className="rounded p-1.5 hover:bg-white/15 text-white"
            >
              <ZoomOut className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={handleResetZoom}
              title="Сбросить масштаб"
              className="px-2 py-1 text-xs font-mono text-white/90 hover:bg-white/15 rounded"
            >
              {Math.round(zoom * 100)}%
            </button>
            <button
              type="button"
              onClick={handleRotate}
              title="Повернуть на 90°"
              className="rounded p-1.5 hover:bg-white/15 text-white"
            >
              <RotateCw className="h-4 w-4" />
            </button>
          </div>

          {/* Split Mode Switcher (on larger screens) */}
          <button
            type="button"
            onClick={onToggleSplit}
            title="Боковая панель (Split View)"
            className="hidden sm:flex items-center space-x-1.5 rounded-lg bg-white/10 px-2.5 py-1.5 text-xs text-white hover:bg-white/20"
          >
            <Columns className="h-4 w-4" />
            <span>Сплит</span>
          </button>

          {/* Close */}
          <button
            type="button"
            onClick={onClose}
            title="Закрыть [Esc]"
            className="rounded-lg bg-white/10 p-2 text-white hover:bg-white/20"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Main Image Canvas */}
      <div
        className="relative flex-1 overflow-hidden p-4 select-none flex items-center justify-center"
        onClick={(e) => e.stopPropagation()}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{ cursor: zoom > 1 ? (isPanning ? 'grabbing' : 'grab') : 'default' }}
      >
        <img
          src={page.imageSrc}
          alt={`Скан страницы ${page.pageNumber}`}
          draggable={false}
          className="max-h-full max-w-full object-contain rounded shadow-2xl transition-transform duration-100 ease-out"
          style={{
            transform: `translate(${position.x}px, ${position.y}px) scale(${zoom}) rotate(${rotation}deg)`,
          }}
        />
      </div>

      {/* Footer hint */}
      <div className="py-2 text-center text-xs text-white/50">
        Перетаскивайте изображение мышью при увеличении. Клавиша <kbd className="rounded bg-white/10 px-1 py-0.5">Esc</kbd> закрывает просмотр.
      </div>
    </div>
  );
};
