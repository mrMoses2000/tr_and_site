import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import App from '../App';

describe('Integration: Reader Application', () => {
  beforeEach(() => {
    localStorage.clear();
    window.location.hash = '#book=schreiner-ntt&page=867';
  });

  it('renders initial page 867 with Russian translation and chapter header', () => {
    render(<App />);

    expect(screen.getByText(/Размышления о богословии Нового Завета/i)).toBeInTheDocument();
    expect(screen.getByText(/Введение/i)).toBeInTheDocument();
    expect(screen.getByText(/Стр\. 867/i)).toBeInTheDocument();
    expect(screen.getByText(/Томас Р\. Шрейнер/i)).toBeInTheDocument();
  });

  it('navigates to next page 868 on Next button click', () => {
    render(<App />);

    const nextBtn = screen.getByRole('button', { name: /Вперед/i });
    fireEvent.click(nextBtn);

    expect(screen.getByText(/Стр\. 868/i)).toBeInTheDocument();
    expect(screen.getByText(/Иоганн Филипп Габлер/i)).toBeInTheDocument();
  });

  it('switches between reader modes (Russian, Bilingual, English)', () => {
    render(<App />);

    const bilingualBtn = screen.getByRole('button', { name: /Параллельно/i });
    fireEvent.click(bilingualBtn);

    expect(screen.getByText(/English Original/i)).toBeInTheDocument();
    expect(screen.getByText(/Русский академический перевод/i)).toBeInTheDocument();

    const enBtn = screen.getByRole('button', { name: /Original/i });
    fireEvent.click(enBtn);

    expect(screen.getByText(/In one sense, the discipline of biblical theology/i)).toBeInTheDocument();
  });

  it('opens Table of Contents and navigates to selected chapter', () => {
    render(<App />);

    const tocBtn = screen.getByTitle(/Содержание/i);
    fireEvent.click(tocBtn);

    expect(screen.getByRole('heading', { name: /Оглавление/i })).toBeInTheDocument();
    const chapterLink = screen.getByText(/Поиски единого богословского центра/i);
    fireEvent.click(chapterLink);

    expect(screen.getByText(/Стр\. 879/i)).toBeInTheDocument();
  });

  it('opens Scan viewer modal when scan button is clicked', () => {
    render(<App />);

    const scanBtn = screen.getByTitle(/Фото оригинала страницы/i);
    fireEvent.click(scanBtn);

    expect(screen.getByText(/Оригинальный скан • Стр\. 867/i)).toBeInTheDocument();
  });

  it('opens cards drawer and shows empty state when no cards exist', () => {
    render(<App />);

    const cardsBtn = screen.getByTitle(/Карточки мыслей/i);
    fireEvent.click(cardsBtn);

    expect(screen.getByText(/Карточки мыслей и цитат/i)).toBeInTheDocument();
    expect(screen.getByText(/Картотека пока пуста/i)).toBeInTheDocument();
  });

  it('allows creating a new thought card and viewing it in the drawer', () => {
    render(<App />);

    const createCardButtons = screen.getAllByText(/\+ Карточка мысли/i);
    fireEvent.click(createCardButtons[0]);

    expect(screen.getByText(/Создать карточку мысли/i)).toBeInTheDocument();

    const noteInput = screen.getByPlaceholderText(/Запишите ваши мысли/i);
    fireEvent.change(noteInput, { target: { value: 'Моя ключевая мысль для дипломной работы' } });

    const saveBtn = screen.getByRole('button', { name: /Создать карточку/i });
    fireEvent.click(saveBtn);

    // Open cards drawer to verify card exists
    const cardsBtn = screen.getByTitle(/Карточки мыслей/i);
    fireEvent.click(cardsBtn);

    expect(screen.getByText(/Моя ключевая мысль для дипломной работы/i)).toBeInTheDocument();
  });

  it('switches between books atomically via TOC without page bounds contamination', () => {
    render(<App />);

    // Initially Schreiner page 867
    expect(screen.getByText(/Томас Р\. Шрейнер/i)).toBeInTheDocument();
    expect(screen.getByText(/Стр\. 867/i)).toBeInTheDocument();

    // Open TOC
    const tocBtn = screen.getByTitle(/Содержание/i);
    fireEvent.click(tocBtn);

    // Switch to Osborne book
    const bookSelect = screen.getByRole('combobox');
    fireEvent.change(bookSelect, { target: { value: 'ozborn-germenevticheskaya-spiral' } });

    // Verify Osborne loaded at its start page (page 1) without being clamped to 867
    expect(screen.getAllByText(/Грант Р\. Осборн/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Стр\. 1/i)).toBeInTheDocument();
    expect(screen.getByText(/736 стр\./i)).toBeInTheDocument();

    // Re-open TOC and switch back to Schreiner
    fireEvent.click(screen.getByTitle(/Содержание/i));
    const bookSelectBack = screen.getByRole('combobox');
    fireEvent.change(bookSelectBack, { target: { value: 'schreiner-ntt' } });

    // Verify Schreiner is restored at page 867
    expect(screen.getByText(/Томас Р\. Шрейнер/i)).toBeInTheDocument();
    expect(screen.getByText(/Стр\. 867/i)).toBeInTheDocument();
  });
});

