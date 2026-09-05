import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import App from '../App';

describe('Integration: Reader Application', () => {
  beforeEach(() => {
    localStorage.clear();
    window.location.hash = '';
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
});
