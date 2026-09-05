/**
 * Reader settings definitions and validation
 */
import type { ReaderSettings, ReaderTheme, FontFamily, ReaderMode } from './types';

export const DEFAULT_SETTINGS: ReaderSettings = {
  fontSize: 18,
  lineHeight: 1.75,
  maxWidth: 720,
  theme: 'sepia',
  fontFamily: 'serif',
  mode: 'ru',
  showDropCap: true,
  showScanModal: false,
};

const VALID_THEMES: ReaderTheme[] = ['sepia', 'light', 'dark', 'oled'];
const VALID_FONTS: FontFamily[] = ['serif', 'sans'];
const VALID_MODES: ReaderMode[] = ['ru', 'bilingual', 'en'];

export function validateSettings(input?: Partial<ReaderSettings>): ReaderSettings {
  if (!input) return { ...DEFAULT_SETTINGS };

  const fontSize = typeof input.fontSize === 'number'
    ? Math.min(Math.max(input.fontSize, 14), 28)
    : DEFAULT_SETTINGS.fontSize;

  const lineHeight = typeof input.lineHeight === 'number'
    ? Math.min(Math.max(input.lineHeight, 1.4), 2.2)
    : DEFAULT_SETTINGS.lineHeight;

  const maxWidth = typeof input.maxWidth === 'number'
    ? Math.min(Math.max(input.maxWidth, 500), 1000)
    : DEFAULT_SETTINGS.maxWidth;

  const theme: ReaderTheme = VALID_THEMES.includes(input.theme as ReaderTheme)
    ? (input.theme as ReaderTheme)
    : DEFAULT_SETTINGS.theme;

  const fontFamily: FontFamily = VALID_FONTS.includes(input.fontFamily as FontFamily)
    ? (input.fontFamily as FontFamily)
    : DEFAULT_SETTINGS.fontFamily;

  const mode: ReaderMode = VALID_MODES.includes(input.mode as ReaderMode)
    ? (input.mode as ReaderMode)
    : DEFAULT_SETTINGS.mode;

  return {
    fontSize,
    lineHeight,
    maxWidth,
    theme,
    fontFamily,
    mode,
    showDropCap: typeof input.showDropCap === 'boolean' ? input.showDropCap : DEFAULT_SETTINGS.showDropCap,
    showScanModal: typeof input.showScanModal === 'boolean' ? input.showScanModal : DEFAULT_SETTINGS.showScanModal,
  };
}
