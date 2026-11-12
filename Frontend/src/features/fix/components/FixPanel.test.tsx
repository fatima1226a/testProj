import { fireEvent, render, screen } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import type { CoordinateFix } from '../../survival/useSurvival';
import type { SiteSurvival } from '../../survival/types';
import { FixPanel } from './FixPanel';

const site = (status: SiteSurvival['status'], message: string | null = null): SiteSurvival => ({
  status,
  survives: status === 'ok' ? true : status === 'fail' || status === 'north' ? false : null,
  result: null,
  message,
});

const fix = (patch: Partial<CoordinateFix> = {}): CoordinateFix => ({
  run: vi.fn(),
  searching: false,
  error: null,
  note: null,
  offer: null,
  acceptOffer: vi.fn(),
  dismissOffer: vi.fn(),
  ...patch,
});

test('unsuitable coordinates: message, hint and the search button', () => {
  render(<FixPanel site={site('north', 'Северные широты не подходят.')} coordsKey="k" fix={fix()} />);
  expect(
    screen.getByText('Текущие выбранные координаты не подходят для выживания аппарата.'),
  ).toBeDefined();
  expect(screen.getByText('Нажмите на кнопку, чтобы найти подходящие координаты.')).toBeDefined();
  expect(screen.getByRole('button', { name: 'Найти подходящие координаты' })).toBeDefined();
});

test('suitable coordinates: no search button', () => {
  render(<FixPanel site={site('ok')} coordsKey="k" fix={fix()} />);
  expect(screen.getByText('Выбранные координаты подходят для выживания аппарата.')).toBeDefined();
  expect(screen.queryByRole('button', { name: 'Найти подходящие координаты' })).toBeNull();
});

test('waiting for the backend does not claim the coordinates are bad', () => {
  render(<FixPanel site={site('loading')} coordsKey="k" fix={fix()} />);
  expect(screen.getByText('Проверяем координаты…')).toBeDefined();
});

test('no coordinates on this date: the popup offers the nearest date and applies it on request', () => {
  const acceptOffer = vi.fn();
  const dismissOffer = vi.fn();
  const offer = {
    latitude: -89.4,
    longitude: -137,
    start: '2026-11-15T00:00:00Z',
    landing: '2026-11-19T00:00:00Z',
    shiftDays: 1,
  };
  render(
    <FixPanel
      site={site('fail', 'Уклон выше допустимого.')}
      coordsKey="k"
      fix={fix({ offer, acceptOffer, dismissOffer })}
    />,
  );
  expect(screen.getByText(/На выбранную дату подходящих координат нет/)).toBeDefined();
  expect(screen.getByText('на 1 сут позже')).toBeDefined();
  expect(screen.queryByRole('button', { name: 'Найти подходящие координаты' })).toBeNull();

  fireEvent.click(screen.getByRole('button', { name: 'Выбрать эту дату' }));
  expect(acceptOffer).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: 'Не нужно' }));
  expect(dismissOffer).toHaveBeenCalledTimes(1);
});
