import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import App from '../App';

describe('Integration: Editorial HomePage & Catalog Hub', () => {
  beforeEach(() => {
    localStorage.clear();
    window.location.hash = '';
  });

  it('renders editorial home page with title, badge, and book catalog when on root hash', () => {
    render(<App />);

    expect(screen.getByText(/Логос • Богословская Читалка/i)).toBeInTheDocument();
    expect(screen.getByText(/Академическая богословская мысль в интерактивном формате/i)).toBeInTheDocument();
    expect(screen.getByText(/Baker Academic • Двуязычный параллельный корпус/i)).toBeInTheDocument();
    expect(screen.getByText(/Книжный фонд библиотеки/i)).toBeInTheDocument();
  });

  it('navigates from HomePage to Reader when "Читать: Томас Шрейнер" is clicked', () => {
    render(<App />);

    const readBtn = screen.getByRole('button', { name: /Читать: Томас Шрейнер/i });
    fireEvent.click(readBtn);

    // Should now be inside the Reader
    expect(screen.getByText(/Стр\. 867/i)).toBeInTheDocument();
    expect(screen.getByText(/Введение/i)).toBeInTheDocument();

    // And clicking "Каталог" in Header should return back to HomePage
    const catalogBtn = screen.getByRole('button', { name: /В библиотеку/i });
    fireEvent.click(catalogBtn);

    expect(screen.getByText(/Книжный фонд библиотеки/i)).toBeInTheDocument();
  });

  it('allows switching theme from the HomePage header', () => {
    render(<App />);

    const darkBtn = screen.getByRole('button', { name: /Тёмная/i });
    fireEvent.click(darkBtn);

    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');

    const sepiaBtn = screen.getByRole('button', { name: /Сепия/i });
    fireEvent.click(sepiaBtn);

    expect(document.documentElement.getAttribute('data-theme')).toBe('sepia');
  });
});
