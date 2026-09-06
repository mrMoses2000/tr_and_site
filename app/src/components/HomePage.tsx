import { useState, type FC } from 'react';
import {
  BookOpen,
  ArrowRight,
  Library,
  FileText,
  Languages,
  Bookmark,
  Layers,
  Send,
  ExternalLink,
  ChevronRight,
} from 'lucide-react';
import type { BookSummary } from '../data/library/libraryRegistry';
import type { ReaderTheme } from '../domain/types';

interface HomePageProps {
  books: BookSummary[];
  activeTheme: ReaderTheme;
  onSelectTheme: (theme: ReaderTheme) => void;
  onOpenBook: (slug: string, page?: number) => void;
}

export const HomePage: FC<HomePageProps> = ({
  books,
  activeTheme,
  onSelectTheme,
  onOpenBook,
}) => {
  const [filterLang, setFilterLang] = useState<'all' | 'kk' | 'ru'>('all');

  const themes: { id: ReaderTheme; label: string }[] = [
    { id: 'sepia', label: 'Сепия' },
    { id: 'light', label: 'Светлая' },
    { id: 'dark', label: 'Тёмная' },
    { id: 'oled', label: 'OLED' },
  ];

  return (
    <div
      className="min-h-screen w-full transition-colors duration-200"
      style={{
        backgroundColor: 'var(--bg-primary)',
        color: 'var(--text-primary)',
      }}
    >
      {/* Editorial Top Navigation */}
      <header
        className="sticky top-0 z-40 w-full border-b backdrop-blur-md"
        style={{
          backgroundColor: 'var(--bg-primary)',
          borderColor: 'var(--border-subtle)',
        }}
      >
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-8">
          {/* Brand Logo & Editorial Title */}
          <div className="flex items-center space-x-3">
            <div
              className="flex h-10 w-10 items-center justify-center rounded-xl shadow-xs overflow-hidden"
              style={{
                backgroundColor: 'transparent',
              }}
            >
              <img src="/favicon.svg" alt="Логос" className="h-full w-full object-contain" />
            </div>
            <div className="flex flex-col">
              <span className="font-serif text-base font-bold tracking-tight">
                Логос • Богословская Читалка
              </span>
              <span
                className="text-[11px] font-medium tracking-wide uppercase opacity-65"
                style={{ color: 'var(--text-secondary)' }}
              >
                Библейский Институт • Logos Bible Institute
              </span>
            </div>
          </div>

          {/* Desktop Navigation Links */}
          <nav className="hidden md:flex items-center space-x-6 text-xs font-semibold tracking-wide">
            <a
              href="#catalog"
              className="transition-opacity hover:opacity-75"
              style={{ color: 'var(--text-secondary)' }}
            >
              Книжный фонд
            </a>
            <a
              href="#features"
              className="transition-opacity hover:opacity-75"
              style={{ color: 'var(--text-secondary)' }}
            >
              Инструменты чтения
            </a>
            <a
              href="#telegram"
              className="flex items-center space-x-1 transition-opacity hover:opacity-75"
              style={{ color: 'var(--accent)' }}
            >
              <Send className="h-3.5 w-3.5" />
              <span>Telegram Бот</span>
            </a>
          </nav>

          {/* Right: Theme Selector & Direct Read CTA */}
          <div className="flex items-center space-x-2.5 sm:space-x-3">
            <div
              className="flex items-center rounded-lg p-0.5"
              style={{
                backgroundColor: 'var(--bg-secondary)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              {themes.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => onSelectTheme(t.id)}
                  title={`Тема: ${t.label}`}
                  className={`rounded-md px-2 py-1 text-[11px] font-medium transition-all ${
                    activeTheme === t.id
                      ? 'shadow-xs font-semibold'
                      : 'opacity-60 hover:opacity-100'
                  }`}
                  style={{
                    backgroundColor:
                      activeTheme === t.id ? 'var(--bg-card)' : 'transparent',
                    color:
                      activeTheme === t.id
                        ? 'var(--accent)'
                        : 'var(--text-secondary)',
                  }}
                >
                  {t.label}
                </button>
              ))}
            </div>

            <button
              type="button"
              onClick={() => onOpenBook(books[0]?.slug || 'schreiner-ntt', 867)}
              className="flex items-center space-x-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold shadow-xs transition-all hover:opacity-90 active:scale-95"
              style={{
                backgroundColor: 'var(--accent)',
                color: '#ffffff',
              }}
            >
              <BookOpen className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Открыть читалку</span>
              <span className="sm:hidden">Читать</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Editorial Hero Section */}
      <section className="relative overflow-hidden border-b px-4 py-12 sm:px-8 sm:py-20" style={{ borderColor: 'var(--border-subtle)' }}>
        <div className="mx-auto max-w-7xl">
          <div className="grid grid-cols-1 gap-12 lg:grid-cols-12 lg:gap-16 items-center">
            {/* Left Content Column */}
            <div className="lg:col-span-7 flex flex-col space-y-6">
              {/* Badge */}
              <div className="inline-flex items-center space-x-2 rounded-full px-3 py-1 text-xs font-semibold w-fit shadow-xs"
                style={{
                  backgroundColor: 'var(--bg-secondary)',
                  color: 'var(--accent)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <Languages className="h-3.5 w-3.5" />
                <span>Baker Academic • Двуязычный параллельный корпус</span>
              </div>

              {/* Editorial Title */}
              <h1 className="font-serif text-3xl sm:text-4xl lg:text-5xl font-extrabold leading-[1.15] tracking-tight">
                Академическая богословская мысль в интерактивном формате
              </h1>

              {/* Subtitle */}
              <p className="text-sm sm:text-base leading-relaxed opacity-85" style={{ color: 'var(--text-secondary)' }}>
                Цифровая исследовательская среда для углубленного чтения первоисточников. 
                Синхронизированный параллельный перевод на <b>казахский (қазақ тілі)</b> и <b>русский</b> языки, 
                оригинальные архивные сканы высокого разрешения, интерактивный аппарат сносок 
                и персональная картотека цитат для научных публикаций.
              </p>

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => onOpenBook('schreiner-ntt', 867)}
                  className="flex items-center space-x-2 rounded-xl px-5 py-3 text-sm font-bold shadow-md transition-all hover:opacity-90 active:scale-95"
                  style={{
                    backgroundColor: 'var(--accent)',
                    color: '#ffffff',
                  }}
                >
                  <BookOpen className="h-4 w-4" />
                  <span>Читать: Томас Шрейнер (стр. 867)</span>
                  <ArrowRight className="h-4 w-4 ml-1" />
                </button>

                <a
                  href="#catalog"
                  className="flex items-center space-x-2 rounded-xl px-4 py-3 text-sm font-semibold transition-all hover:opacity-85"
                  style={{
                    backgroundColor: 'var(--bg-secondary)',
                    color: 'var(--text-primary)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <Library className="h-4 w-4 opacity-70" />
                  <span>Книжный фонд</span>
                </a>

                <a
                  href="https://t.me/pdf_to_web_book_bot"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center space-x-2 rounded-xl px-4 py-3 text-sm font-semibold transition-all hover:opacity-85"
                  style={{
                    backgroundColor: 'var(--bg-card)',
                    color: 'var(--text-secondary)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <Send className="h-4 w-4" style={{ color: 'var(--accent)' }} />
                  <span>@pdf_to_web_book_bot</span>
                </a>
              </div>

              {/* Research Metrics Strip */}
              <div className="grid grid-cols-3 gap-4 pt-6 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                <div>
                  <div className="text-xl sm:text-2xl font-bold font-serif" style={{ color: 'var(--text-primary)' }}>
                    22 стр.
                  </div>
                  <div className="text-xs opacity-65" style={{ color: 'var(--text-secondary)' }}>
                    Критический текст (867–888)
                  </div>
                </div>
                <div>
                  <div className="text-xl sm:text-2xl font-bold font-serif" style={{ color: 'var(--text-primary)' }}>
                    3 режима
                  </div>
                  <div className="text-xs opacity-65" style={{ color: 'var(--text-secondary)' }}>
                    Оригинал • Двуязычный • Перевод
                  </div>
                </div>
                <div>
                  <div className="text-xl sm:text-2xl font-bold font-serif" style={{ color: 'var(--text-primary)' }}>
                    100%
                  </div>
                  <div className="text-xs opacity-65" style={{ color: 'var(--text-secondary)' }}>
                    Сверка с печатными сканами
                  </div>
                </div>
              </div>
            </div>

            {/* Right: Featured Book Showcase Card */}
            <div className="lg:col-span-5">
              <div
                className="relative rounded-2xl p-6 sm:p-8 shadow-xl border transition-all duration-300 hover:shadow-2xl"
                style={{
                  backgroundColor: 'var(--bg-card)',
                  borderColor: 'var(--border-strong)',
                }}
              >
                {/* Book Spine Accent bar */}
                <div
                  className="absolute left-0 top-6 bottom-6 w-2 rounded-r"
                  style={{ backgroundColor: 'var(--accent)' }}
                />

                <div className="pl-3">
                  <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider opacity-70" style={{ color: 'var(--text-secondary)' }}>
                    <span>Baker Academic • 2008</span>
                    <span className="rounded px-2 py-0.5" style={{ backgroundColor: 'var(--bg-secondary)' }}>
                      Приложение
                    </span>
                  </div>

                  <h3 className="font-serif text-xl sm:text-2xl font-bold mt-2 leading-snug" style={{ color: 'var(--text-primary)' }}>
                    Размышления о богословии Нового Завета
                  </h3>

                  <div className="text-xs font-medium mt-1 opacity-80" style={{ color: 'var(--text-secondary)' }}>
                    Томас Р. Шрейнер (Thomas R. Schreiner)
                  </div>

                  <p className="mt-4 text-xs leading-relaxed opacity-75" style={{ color: 'var(--text-secondary)' }}>
                    Фундаментальный очерк по методологии библейского богословия: от Иоганна Филиппа Габлера 
                    и Тюбингенской школы до Адольфа Шлаттера, Герхардуса Фоса, Рудольфа Бультмана 
                    и современных дебатов о каноне и поиске богословского центра.
                  </p>

                  <div className="mt-6 flex flex-wrap gap-1.5">
                    <span className="rounded-md px-2 py-1 text-[11px] font-medium" style={{ backgroundColor: 'var(--bg-secondary)' }}>
                      🇰🇿 Қазақша аударма
                    </span>
                    <span className="rounded-md px-2 py-1 text-[11px] font-medium" style={{ backgroundColor: 'var(--bg-secondary)' }}>
                      🇷🇺 Русский перевод
                    </span>
                    <span className="rounded-md px-2 py-1 text-[11px] font-medium" style={{ backgroundColor: 'var(--bg-secondary)' }}>
                      🇬🇧 English Original
                    </span>
                    <span className="rounded-md px-2 py-1 text-[11px] font-medium" style={{ backgroundColor: 'var(--bg-secondary)' }}>
                      📑 112 сносок
                    </span>
                  </div>

                  <div className="mt-6 pt-4 border-t flex items-center justify-between" style={{ borderColor: 'var(--border-subtle)' }}>
                    <div className="text-xs font-medium opacity-70">
                      Начать с Введения (с. 867)
                    </div>
                    <button
                      type="button"
                      onClick={() => onOpenBook('schreiner-ntt', 867)}
                      className="flex items-center space-x-1 text-xs font-bold transition-transform hover:translate-x-1"
                      style={{ color: 'var(--accent)' }}
                    >
                      <span>Перейти в читалку</span>
                      <ChevronRight className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Library Catalog Section */}
      <section id="catalog" className="border-b px-4 py-12 sm:px-8 sm:py-16" style={{ borderColor: 'var(--border-subtle)' }}>
        <div className="mx-auto max-w-7xl">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between mb-8 gap-4">
            <div>
              <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
                <Library className="h-4 w-4" />
                <span>Каталог изданий</span>
              </div>
              <h2 className="font-serif text-2xl sm:text-3xl font-bold mt-1">
                Книжный фонд библиотеки
              </h2>
            </div>

            {/* Language filter pills */}
            <div
              className="flex items-center rounded-xl p-1 self-start sm:self-auto"
              style={{
                backgroundColor: 'var(--bg-secondary)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <button
                type="button"
                onClick={() => setFilterLang('all')}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                  filterLang === 'all' ? 'shadow-xs font-semibold' : 'opacity-70'
                }`}
                style={{
                  backgroundColor: filterLang === 'all' ? 'var(--bg-card)' : 'transparent',
                  color: filterLang === 'all' ? 'var(--accent)' : 'var(--text-secondary)',
                }}
              >
                Все издания ({books.length})
              </button>
              <button
                type="button"
                onClick={() => setFilterLang('kk')}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                  filterLang === 'kk' ? 'shadow-xs font-semibold' : 'opacity-70'
                }`}
                style={{
                  backgroundColor: filterLang === 'kk' ? 'var(--bg-card)' : 'transparent',
                  color: filterLang === 'kk' ? 'var(--accent)' : 'var(--text-secondary)',
                }}
              >
                🇰🇿 Қазақша
              </button>
              <button
                type="button"
                onClick={() => setFilterLang('ru')}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                  filterLang === 'ru' ? 'shadow-xs font-semibold' : 'opacity-70'
                }`}
                style={{
                  backgroundColor: filterLang === 'ru' ? 'var(--bg-card)' : 'transparent',
                  color: filterLang === 'ru' ? 'var(--accent)' : 'var(--text-secondary)',
                }}
              >
                🇷🇺 Русский
              </button>
            </div>
          </div>

          {/* Books Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {books.map((book) => (
              <div
                key={book.slug}
                className="group flex flex-col justify-between rounded-2xl p-6 border transition-all duration-200 hover:-translate-y-1 hover:shadow-lg"
                style={{
                  backgroundColor: 'var(--bg-card)',
                  borderColor: 'var(--border-subtle)',
                }}
              >
                <div>
                  <div className="flex items-center justify-between text-xs font-medium opacity-65 mb-2">
                    <span>{book.authorRu}</span>
                    <span>{book.totalPages} стр.</span>
                  </div>

                  <h3 className="font-serif text-lg font-bold leading-snug group-hover:underline decoration-1 underline-offset-4">
                    {book.titleRu}
                  </h3>

                  <div className="text-xs opacity-75 mt-1 font-serif italic">
                    {book.title}
                  </div>

                  <div className="mt-4 flex flex-wrap gap-1.5">
                    <span className="rounded px-2 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: 'var(--bg-secondary)' }}>
                      Двуязычный
                    </span>
                    <span className="rounded px-2 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: 'var(--bg-secondary)' }}>
                      Сноски
                    </span>
                    <span className="rounded px-2 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: 'var(--bg-secondary)' }}>
                      Сканы WebP
                    </span>
                  </div>
                </div>

                <div className="mt-6 pt-4 border-t flex items-center justify-between" style={{ borderColor: 'var(--border-subtle)' }}>
                  <span className="text-xs font-medium opacity-60">
                    Статус: Опубликовано
                  </span>
                  <button
                    type="button"
                    onClick={() => onOpenBook(book.slug)}
                    className="flex items-center space-x-1.5 rounded-lg px-3 py-1.5 text-xs font-bold shadow-xs transition-all hover:opacity-90 active:scale-95"
                    style={{
                      backgroundColor: 'var(--accent)',
                      color: '#ffffff',
                    }}
                  >
                    <span>Читать</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ))}

            {/* Ingestion Callout Card */}
            <div
              className="flex flex-col justify-between rounded-2xl p-6 border border-dashed transition-all"
              style={{
                backgroundColor: 'var(--bg-secondary)',
                borderColor: 'var(--border-strong)',
              }}
            >
              <div>
                <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
                  <Send className="h-3.5 w-3.5" />
                  <span>Добавить свою книгу</span>
                </div>

                <h3 className="font-serif text-lg font-bold mt-2">
                  Публикация через Telegram
                </h3>

                <p className="mt-2 text-xs leading-relaxed opacity-80" style={{ color: 'var(--text-secondary)' }}>
                  Отправьте PDF-файл в бота <b>@pdf_to_web_book_bot</b>. 
                  Конвейер выделит текст, выполнит академический перевод на казахский или русский язык, 
                  привяжет сноски и автоматически опубликует книгу в этом каталоге.
                </p>
              </div>

              <div className="mt-6 pt-4 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                <a
                  href="https://t.me/pdf_to_web_book_bot"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center space-x-2 w-full rounded-xl py-2.5 text-xs font-bold transition-all hover:opacity-90"
                  style={{
                    backgroundColor: 'var(--accent-soft)',
                    color: 'var(--accent)',
                    border: '1px solid var(--accent)',
                  }}
                >
                  <Send className="h-3.5 w-3.5" />
                  <span>Открыть @pdf_to_web_book_bot</span>
                  <ExternalLink className="h-3.5 w-3.5 opacity-70" />
                </a>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Scholarly Reader Features (Bento Style) */}
      <section id="features" className="border-b px-4 py-12 sm:px-8 sm:py-16" style={{ borderColor: 'var(--border-subtle)' }}>
        <div className="mx-auto max-w-7xl">
          <div className="max-w-2xl mb-12">
            <div className="text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
              Исследовательская среда
            </div>
            <h2 className="font-serif text-2xl sm:text-3xl font-bold mt-1">
              Инструменты для глубокой научной работы с текстом
            </h2>
            <p className="mt-2 text-xs sm:text-sm leading-relaxed opacity-80" style={{ color: 'var(--text-secondary)' }}>
              Разработано в строгом соответствии с академическими стандартами работы с первоисточниками.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* Feature 1: Bilingual Interleaving */}
            <div
              className="rounded-2xl p-6 border transition-all hover:shadow-md"
              style={{
                backgroundColor: 'var(--bg-card)',
                borderColor: 'var(--border-subtle)',
              }}
            >
              <div
                className="flex h-10 w-10 items-center justify-center rounded-xl mb-4 shadow-xs"
                style={{ backgroundColor: 'var(--accent-soft)', color: 'var(--accent)' }}
              >
                <Languages className="h-5 w-5" />
              </div>
              <h3 className="font-serif text-base font-bold mb-2">
                Параллельный интерливинг
              </h3>
              <p className="text-xs leading-relaxed opacity-80" style={{ color: 'var(--text-secondary)' }}>
                Синхронизированные параллельные колонки оригинала и перевода (казахский/русский). 
                Абзацы логически выровнены, исключая рассинхронизацию при чтении.
              </p>
            </div>

            {/* Feature 2: Footnote Apparatus */}
            <div
              className="rounded-2xl p-6 border transition-all hover:shadow-md"
              style={{
                backgroundColor: 'var(--bg-card)',
                borderColor: 'var(--border-subtle)',
              }}
            >
              <div
                className="flex h-10 w-10 items-center justify-center rounded-xl mb-4 shadow-xs"
                style={{ backgroundColor: 'var(--accent-soft)', color: 'var(--accent)' }}
              >
                <FileText className="h-5 w-5" />
              </div>
              <h3 className="font-serif text-base font-bold mb-2">
                Аппарат сносок
              </h3>
              <p className="text-xs leading-relaxed opacity-80" style={{ color: 'var(--text-secondary)' }}>
                Интерактивные всплывающие сноски с сохранением контекста. 
                Библиографические ссылки на Генгеля, Бультмана, Шлаттера и отцов церкви.
              </p>
            </div>

            {/* Feature 3: Research Thought Cards */}
            <div
              className="rounded-2xl p-6 border transition-all hover:shadow-md"
              style={{
                backgroundColor: 'var(--bg-card)',
                borderColor: 'var(--border-subtle)',
              }}
            >
              <div
                className="flex h-10 w-10 items-center justify-center rounded-xl mb-4 shadow-xs"
                style={{ backgroundColor: 'var(--accent-soft)', color: 'var(--accent)' }}
              >
                <Bookmark className="h-5 w-5" />
              </div>
              <h3 className="font-serif text-base font-bold mb-2">
                Картотека заметок
              </h3>
              <p className="text-xs leading-relaxed opacity-80" style={{ color: 'var(--text-secondary)' }}>
                Выделение ключевых цитат с классификацией (тезис, цитата, богословие, в диплом) 
                и экспорт всей картотеки в чистый Markdown для статей и диссертаций.
              </p>
            </div>

            {/* Feature 4: High-Res Scans */}
            <div
              className="rounded-2xl p-6 border transition-all hover:shadow-md"
              style={{
                backgroundColor: 'var(--bg-card)',
                borderColor: 'var(--border-subtle)',
              }}
            >
              <div
                className="flex h-10 w-10 items-center justify-center rounded-xl mb-4 shadow-xs"
                style={{ backgroundColor: 'var(--accent-soft)', color: 'var(--accent)' }}
              >
                <Layers className="h-5 w-5" />
              </div>
              <h3 className="font-serif text-base font-bold mb-2">
                Архивные WebP сканы
              </h3>
              <p className="text-xs leading-relaxed opacity-80" style={{ color: 'var(--text-secondary)' }}>
                Мгновенный доступ к фотокопиям оригинального печатного издания Baker Academic 2008 года 
                в режиме раздельного экрана (Split View) или модального окна.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Telegram Pipeline Information Section */}
      <section id="telegram" className="px-4 py-12 sm:px-8 sm:py-16">
        <div className="mx-auto max-w-7xl">
          <div
            className="rounded-3xl p-8 sm:p-12 border shadow-sm"
            style={{
              backgroundColor: 'var(--bg-card)',
              borderColor: 'var(--border-subtle)',
            }}
          >
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
              <div className="lg:col-span-8">
                <div className="inline-flex items-center space-x-2 rounded-full px-3 py-1 text-xs font-semibold mb-4"
                  style={{
                    backgroundColor: 'var(--bg-secondary)',
                    color: 'var(--accent)',
                  }}
                >
                  <Send className="h-3.5 w-3.5" />
                  <span>Автоматический конвейер публикации</span>
                </div>

                <h2 className="font-serif text-2xl sm:text-3xl font-bold leading-tight">
                  Как добавить книгу в читалку за 3 простых шага
                </h2>

                <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="rounded-xl p-4" style={{ backgroundColor: 'var(--bg-secondary)' }}>
                    <div className="text-xs font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--accent)' }}>
                      Шаг 1
                    </div>
                    <div className="text-sm font-semibold mb-1">Отправьте PDF</div>
                    <div className="text-xs opacity-75 leading-relaxed">
                      Пришлите файл книги в бот @pdf_to_web_book_bot.
                    </div>
                  </div>

                  <div className="rounded-xl p-4" style={{ backgroundColor: 'var(--bg-secondary)' }}>
                    <div className="text-xs font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--accent)' }}>
                      Шаг 2
                    </div>
                    <div className="text-sm font-semibold mb-1">Выберите режим</div>
                    <div className="text-xs opacity-75 leading-relaxed">
                      Казахский (Қазақша), русский или оригинал без перевода.
                    </div>
                  </div>

                  <div className="rounded-xl p-4" style={{ backgroundColor: 'var(--bg-secondary)' }}>
                    <div className="text-xs font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--accent)' }}>
                      Шаг 3
                    </div>
                    <div className="text-sm font-semibold mb-1">Читайте онлайн</div>
                    <div className="text-xs opacity-75 leading-relaxed">
                      Получите готовую ссылку на опубликованную книгу.
                    </div>
                  </div>
                </div>
              </div>

              <div className="lg:col-span-4 flex flex-col items-center justify-center p-6 rounded-2xl text-center" style={{ backgroundColor: 'var(--bg-secondary)' }}>
                <div className="text-xs font-mono font-semibold uppercase tracking-wider opacity-60 mb-2">
                  Telegram Bot Daemon
                </div>
                <div className="font-serif text-lg font-bold mb-1">
                  @pdf_to_web_book_bot
                </div>
                <div className="text-xs opacity-75 mb-6">
                  Статус: В сети • Long Polling активен
                </div>
                <a
                  href="https://t.me/pdf_to_web_book_bot"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center space-x-2 rounded-xl px-5 py-3 text-xs font-bold shadow-md transition-all hover:opacity-90 active:scale-95"
                  style={{
                    backgroundColor: 'var(--accent)',
                    color: '#ffffff',
                  }}
                >
                  <Send className="h-4 w-4" />
                  <span>Открыть бота в Telegram</span>
                </a>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Academic Footer */}
      <footer className="border-t px-4 py-8 sm:px-8 text-xs opacity-70" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-secondary)' }}>
        <div className="mx-auto max-w-7xl flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            Логос • Академическая богословская библиотека. Разработано для ученых, пасторов и студентов.
          </div>
          <div className="flex items-center space-x-4">
            <a href="https://t.me/pdf_to_web_book_bot" target="_blank" rel="noopener noreferrer" className="hover:underline">
              Telegram Бот
            </a>
            <span>•</span>
            <a href="https://harmonious-hotteok-0204c0.netlify.app" className="hover:underline">
              Netlify Production
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
};
