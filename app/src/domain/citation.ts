import type { BookCitationMetadata, ResearchCardV2 } from './v2/types';
import { CARD_TAG_LABELS } from './cards';

export type { BookCitationMetadata };

export function extractBookCitationMetadata(
  manifest: any
): BookCitationMetadata {
  const rawTitle = manifest?.title;
  let titleVal = '';
  if (typeof rawTitle === 'string') {
    titleVal = rawTitle;
  } else if (rawTitle && typeof rawTitle === 'object') {
    titleVal = rawTitle.ru || rawTitle.en || Object.values(rawTitle)[0] || '';
  }

  const rawSubtitle = manifest?.subtitle;
  let subtitleVal: string | undefined;
  if (typeof rawSubtitle === 'string') {
    subtitleVal = rawSubtitle;
  } else if (rawSubtitle && typeof rawSubtitle === 'object') {
    subtitleVal = rawSubtitle.ru || rawSubtitle.en || Object.values(rawSubtitle)[0];
  }

  if (manifest?.citation) {
    return {
      shortTitle: manifest.citation.shortTitle || titleVal,
      author: manifest.authorRu || manifest.author || manifest.contributors?.[0]?.name || '',
      title: titleVal,
      subtitle: subtitleVal,
      publisher: manifest.citation.publisher || manifest.publisher,
      place: manifest.citation.place,
      year: manifest.citation.year,
      edition: manifest.citation.edition,
    };
  }

  return {
    shortTitle: manifest.titleRu || manifest.title || '',
    author: manifest.authorRu || manifest.author || '',
    title: manifest.titleRu || manifest.title || '',
    subtitle: manifest.subtitleRu || manifest.subtitle,
    publisher: manifest.publisher,
    year: manifest.publisher?.match(/\b(19\d\d|20\d\d)\b/)?.[0],
  };
}

export function formatAcademicCitationV2(
  card: ResearchCardV2,
  lang: 'ru' | 'en' | string = 'ru',
  metadataOverride?: BookCitationMetadata
): string {
  const meta = metadataOverride || card.citationSnapshot || {
    author: card.bookSlug === 'schreiner-ntt' ? 'Томас Р. Шрайнер' : 'Автор не указан',
    title: card.bookSlug === 'schreiner-ntt' ? 'Богословие Нового Завета' : 'Источник не указан',
    shortTitle: card.bookSlug === 'schreiner-ntt' ? 'Богословие Нового Завета' : 'Источник',
  };

  const isRu = lang === 'ru' || card.quoteLanguage === 'ru';

  const author = meta.author || '';
  const title = meta.title || meta.shortTitle;
  const subtitle = meta.subtitle ? `: ${meta.subtitle}` : '';
  const publisher = meta.publisher ? `${meta.publisher}. ` : '';
  const year = meta.year ? `${meta.year}. ` : '';

  if (isRu) {
    const pubYearPart = publisher || year ? `${publisher}${year}` : '';
    return `«${card.quote}» // ${author ? `${author}. ` : ''}${title}${subtitle}. ${pubYearPart}С. ${card.pageNumber}.`;
  }

  const pubInfo = [meta.place, meta.publisher, meta.year].filter(Boolean).join(': ');
  const parenthesizedPub = pubInfo ? ` (${pubInfo})` : '';
  return `"${card.quote}" // ${author ? `${author}, ` : ''}${title}${subtitle}${parenthesizedPub}, p. ${card.pageNumber}.`;
}

export function exportCardsToMarkdownV2(
  cards: ResearchCardV2[],
  metadata?: BookCitationMetadata
): string {
  const primaryMeta = metadata || cards[0]?.citationSnapshot;
  const author = primaryMeta?.author || 'Исследовательские выписки';
  const title = primaryMeta?.title || primaryMeta?.shortTitle || 'Книга';

  const lines: string[] = [
    '# Академические выписки и карточки мыслей',
    `**Источник:** ${author}, *${title}*`,
    `**Всего карточек:** ${cards.length}`,
    `**Дата экспорта:** ${new Date().toLocaleDateString('ru-RU')}`,
    '',
    '---',
    '',
  ];

  cards.forEach((card, index) => {
    const tagInfo = CARD_TAG_LABELS[card.tag as keyof typeof CARD_TAG_LABELS] || { label: card.tag };
    lines.push(`### ${index + 1}. [Стр. ${card.pageNumber}] ${tagInfo.label}`);
    lines.push('');
    lines.push(`> ${card.quote.replace(/\n/g, '\n> ')}`);
    lines.push('');
    if (card.note) {
      lines.push(`**Моя мысль / комментарий:**`);
      lines.push(card.note);
      lines.push('');
    }
    lines.push(`*Библиографическая ссылка:* \`${formatAcademicCitationV2(card, card.quoteLanguage, primaryMeta)}\``);
    lines.push('');
    lines.push('---');
    lines.push('');
  });

  return lines.join('\n');
}
