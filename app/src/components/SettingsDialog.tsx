import type { FC } from 'react';
import { X, Check, Type, RefreshCcw } from 'lucide-react';
import { DEFAULT_SETTINGS } from '../domain/settings';
import type { ReaderSettings, ReaderTheme } from '../domain/types';

interface SettingsDialogProps {
  isOpen: boolean;
  onClose: () => void;
  settings: ReaderSettings;
  onUpdateSettings: (updater: Partial<ReaderSettings>) => void;
}

export const SettingsDialog: FC<SettingsDialogProps> = ({
  isOpen,
  onClose,
  settings,
  onUpdateSettings,
}) => {
  if (!isOpen) return null;

  const themes: { id: ReaderTheme; label: string; desc: string; bg: string; text: string }[] = [
    { id: 'sepia', label: 'Папирус', desc: 'Теплый винтаж', bg: '#fbf0d9', text: '#382c1e' },
    { id: 'light', label: 'Светлая', desc: 'Классическая', bg: '#faf9f6', text: '#1c1c1c' },
    { id: 'dark', label: 'Графит', desc: 'Комфорт ночи', bg: '#18181b', text: '#f4f4f5' },
    { id: 'oled', label: 'OLED', desc: 'Истинный черный', bg: '#000000', text: '#e4e4e7' },
  ];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl border p-5 shadow-2xl transition-all sm:p-6"
        style={{
          backgroundColor: 'var(--bg-card)',
          borderColor: 'var(--border-strong)',
          color: 'var(--text-primary)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b pb-3.5" style={{ borderColor: 'var(--border-subtle)' }}>
          <div className="flex items-center space-x-2">
            <Type className="h-5 w-5" style={{ color: 'var(--accent)' }} />
            <h2 className="text-sm font-bold tracking-tight">Настройки чтения</h2>
          </div>

          <div className="flex items-center space-x-1">
            <button
              type="button"
              onClick={() => onUpdateSettings(DEFAULT_SETTINGS)}
              title="Сбросить по умолчанию"
              className="rounded-lg p-1.5 transition-all hover:opacity-80 active:scale-95"
              style={{ backgroundColor: 'var(--bg-secondary)', color: 'var(--text-secondary)' }}
            >
              <RefreshCcw className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1.5 transition-all hover:opacity-80 active:scale-95"
              style={{ backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)' }}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="mt-5 space-y-6 text-xs">
          {/* Theme Selector */}
          <div>
            <label className="block font-semibold uppercase tracking-wider opacity-60 mb-2.5">
              Цветовая тема
            </label>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {themes.map((t) => {
                const isSelected = settings.theme === t.id;
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => onUpdateSettings({ theme: t.id })}
                    className={`flex flex-col items-center justify-center rounded-xl p-2.5 transition-all border ${
                      isSelected ? 'ring-2' : 'hover:opacity-90'
                    }`}
                    style={{
                      backgroundColor: t.bg,
                      color: t.text,
                      borderColor: isSelected ? 'var(--accent)' : 'var(--border-subtle)',
                      boxShadow: isSelected ? '0 0 0 2px var(--accent)' : 'none',
                    }}
                  >
                    <span className="font-bold text-xs">{t.label}</span>
                    <span className="text-[10px] opacity-70 mt-0.5">{t.desc}</span>
                    {isSelected && <Check className="mt-1 h-3.5 w-3.5 text-current" />}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Typography Mode */}
          <div>
            <label className="block font-semibold uppercase tracking-wider opacity-60 mb-2.5">
              Гарнитура шрифта
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => onUpdateSettings({ fontFamily: 'serif' })}
                className={`rounded-xl p-3 text-left transition-all border font-serif ${
                  settings.fontFamily === 'serif' ? 'ring-2' : 'opacity-70 hover:opacity-100'
                }`}
                style={{
                  backgroundColor: 'var(--bg-secondary)',
                  color: 'var(--text-primary)',
                  borderColor: settings.fontFamily === 'serif' ? 'var(--accent)' : 'var(--border-subtle)',
                }}
              >
                <div className="text-sm font-bold">Литературный</div>
                <div className="text-[11px] opacity-70 mt-0.5">Literata / С засечками</div>
              </button>

              <button
                type="button"
                onClick={() => onUpdateSettings({ fontFamily: 'sans' })}
                className={`rounded-xl p-3 text-left transition-all border font-sans ${
                  settings.fontFamily === 'sans' ? 'ring-2' : 'opacity-70 hover:opacity-100'
                }`}
                style={{
                  backgroundColor: 'var(--bg-secondary)',
                  color: 'var(--text-primary)',
                  borderColor: settings.fontFamily === 'sans' ? 'var(--accent)' : 'var(--border-subtle)',
                }}
              >
                <div className="text-sm font-bold">Современный</div>
                <div className="text-[11px] opacity-70 mt-0.5">Inter / Гротеск</div>
              </button>
            </div>
          </div>

          {/* Font Size Slider */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold uppercase tracking-wider opacity-60">Размер текста</span>
              <span className="font-mono font-bold text-xs" style={{ color: 'var(--accent)' }}>
                {settings.fontSize} px
              </span>
            </div>
            <input
              type="range"
              min={15}
              max={26}
              step={1}
              value={settings.fontSize}
              onChange={(e) => onUpdateSettings({ fontSize: parseInt(e.target.value, 10) })}
              className="w-full accent-amber-600 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] opacity-50 font-mono mt-1">
              <span>15px (компактный)</span>
              <span>20px (стандарт)</span>
              <span>26px (крупный)</span>
            </div>
          </div>

          {/* Line Height Slider */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold uppercase tracking-wider opacity-60">Межстрочный интервал</span>
              <span className="font-mono font-bold text-xs" style={{ color: 'var(--accent)' }}>
                {settings.lineHeight.toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              min={1.4}
              max={2.1}
              step={0.05}
              value={settings.lineHeight}
              onChange={(e) => onUpdateSettings({ lineHeight: parseFloat(e.target.value) })}
              className="w-full accent-amber-600 cursor-pointer"
            />
          </div>

          {/* Width Slider */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold uppercase tracking-wider opacity-60">Ширина полосы текста</span>
              <span className="font-mono font-bold text-xs" style={{ color: 'var(--accent)' }}>
                {settings.maxWidth} px
              </span>
            </div>
            <input
              type="range"
              min={580}
              max={920}
              step={20}
              value={settings.maxWidth}
              onChange={(e) => onUpdateSettings({ maxWidth: parseInt(e.target.value, 10) })}
              className="w-full accent-amber-600 cursor-pointer"
            />
          </div>

          {/* Drop Cap Toggle */}
          <div className="flex items-center justify-between pt-2 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
            <div>
              <div className="font-bold text-xs">Буквица (Drop Cap)</div>
              <div className="text-[11px] opacity-70">Декоративная заглавная буква в начале главы</div>
            </div>
            <input
              type="checkbox"
              checked={settings.showDropCap}
              onChange={(e) => onUpdateSettings({ showDropCap: e.target.checked })}
              className="h-4 w-4 rounded accent-amber-600 cursor-pointer"
            />
          </div>
        </div>
      </div>
    </div>
  );
};
