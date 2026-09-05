import type { ResearchCard, CardTag, HighlightColor } from './types';

export const CARD_TAG_LABELS: Record<CardTag, { label: string; labelEn: string; iconName: string }> = {
  thesis: { label: 'Тезис', labelEn: 'Thesis', iconName: 'Bookmark' },
  quote: { label: 'Цитата', labelEn: 'Quote', iconName: 'Quote' },
  thought: { label: 'Мысль / Заметка', labelEn: 'Thought', iconName: 'Lightbulb' },
  'for-paper': { label: 'Для статьи / работы', labelEn: 'For Paper', iconName: 'PenTool' },
  theology: { label: 'Богословие', labelEn: 'Theology', iconName: 'Sparkles' },
  question: { label: 'Вопрос для изучения', labelEn: 'Question', iconName: 'HelpCircle' },
};

export const COLOR_CLASSES: Record<HighlightColor, { bg: string; text: string; border: string; highlight: string }> = {
  amber: {
    bg: 'bg-amber-500/10 dark:bg-amber-500/20',
    text: 'text-amber-700 dark:text-amber-300',
    border: 'border-amber-400 dark:border-amber-600',
    highlight: 'bg-amber-200/70 dark:bg-amber-900/50',
  },
  emerald: {
    bg: 'bg-emerald-500/10 dark:bg-emerald-500/20',
    text: 'text-emerald-700 dark:text-emerald-300',
    border: 'border-emerald-400 dark:border-emerald-600',
    highlight: 'bg-emerald-200/70 dark:bg-emerald-900/50',
  },
  blue: {
    bg: 'bg-sky-500/10 dark:bg-sky-500/20',
    text: 'text-sky-700 dark:text-sky-300',
    border: 'border-sky-400 dark:border-sky-600',
    highlight: 'bg-sky-200/70 dark:bg-sky-900/50',
  },
  purple: {
    bg: 'bg-purple-500/10 dark:bg-purple-500/20',
    text: 'text-purple-700 dark:text-purple-300',
    border: 'border-purple-400 dark:border-purple-600',
    highlight: 'bg-purple-200/70 dark:bg-purple-900/50',
  },
};

export function generateCardId(): string {
  return `card-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`;
}

export interface CreateCardInput {
  pageNumber: number;
  paragraphId?: string;
  quote: string;
  quoteLanguage?: 'ru' | 'en';
  note: string;
  tag?: CardTag;
  color?: HighlightColor;
}

export function createResearchCard(input: CreateCardInput): ResearchCard {
  const now = new Date().toISOString();
  return {
    id: generateCardId(),
    pageNumber: input.pageNumber,
    paragraphId: input.paragraphId,
    quote: input.quote.trim(),
    quoteLanguage: input.quoteLanguage || 'ru',
    note: input.note.trim(),
    tag: input.tag || 'thought',
    color: input.color || 'amber',
    createdAt: now,
    updatedAt: now,
  };
}

export interface FilterCardOptions {
  query?: string;
  tag?: CardTag | 'all';
  pageNumber?: number | 'all';
}

export function filterResearchCards(cards: ResearchCard[], options: FilterCardOptions): ResearchCard[] {
  let filtered = [...cards];

  if (options.tag && options.tag !== 'all') {
    filtered = filtered.filter(c => c.tag === options.tag);
  }

  if (options.pageNumber && options.pageNumber !== 'all') {
    filtered = filtered.filter(c => c.pageNumber === options.pageNumber);
  }

  if (options.query && options.query.trim()) {
    const q = options.query.toLowerCase().trim();
    filtered = filtered.filter(
      c => c.quote.toLowerCase().includes(q) || c.note.toLowerCase().includes(q)
    );
  }

  // Sort newest first
  return filtered.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
}

export function formatAcademicCitation(card: ResearchCard): string {
  if (card.quoteLanguage === 'ru') {
    return `«${card.quote}» // Шрайнер Т. Богословие Нового Завета: возвеличивание Бога во Христе. Приложение: Размышления о богословии Нового Завета. С. ${card.pageNumber}.`;
  }
  return `"${card.quote}" // Schreiner, Thomas R. New Testament Theology: Magnifying God in Christ. Appendix: Reflections on New Testament Theology. P. ${card.pageNumber}.`;
}

export function exportCardsToMarkdown(cards: ResearchCard[]): string {
  const lines: string[] = [
    '# Академические выписки и карточки мыслей',
    '**Источник:** Томас Р. Шрайнер, *Богословие Нового Завета* (Приложение, с. 867–888)',
    `**Всего карточек:** ${cards.length}`,
    `**Дата экспорта:** ${new Date().toLocaleDateString('ru-RU')}`,
    '',
    '---',
    '',
  ];

  cards.forEach((card, index) => {
    const tagInfo = CARD_TAG_LABELS[card.tag] || { label: card.tag };
    lines.push(`### ${index + 1}. [Стр. ${card.pageNumber}] ${tagInfo.label}`);
    lines.push('');
    lines.push(`> ${card.quote.replace(/\n/g, '\n> ')}`);
    lines.push('');
    if (card.note) {
      lines.push(`**Моя мысль / комментарий:**`);
      lines.push(card.note);
      lines.push('');
    }
    lines.push(`*Библиографическая ссылка:* \`${formatAcademicCitation(card)}\``);
    lines.push('');
    lines.push('---');
    lines.push('');
  });

  return lines.join('\n');
}
