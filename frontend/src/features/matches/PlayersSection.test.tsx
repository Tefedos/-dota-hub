// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { PlayersSection } from './PlayersSection';

afterEach(cleanup);
const item = (item_id: number, status: 'known' | 'empty' | 'unmapped' = 'known') => ({
  item_id, name: status === 'known' ? `Item ${item_id}` : null, image_key: null,
  image_url: status === 'known' ? `https://example.test/${item_id}.png` : null, status,
});
const player = (slot: number, overrides: Record<string, unknown> = {}) => ({
  player_slot: slot, team: slot < 128 ? 'radiant' : 'dire', team_player_number: slot < 128 ? slot + 1 : slot - 127,
  display_name: `Nick ${slot}`, is_anonymous: false, hero_id: 2, hero_name: 'Axe',
  hero_image_url: 'https://example.test/axe.png', kills: 1, deaths: 2, assists: 3,
  gpm: 401, xpm: 502, hero_damage: 12345, tower_damage: 678, net_worth: 15000,
  hero_healing: 0, last_hits: 42, denies: 1, obs_placed: 2, sen_placed: 0,
  level: 22, item_details: [item(10), item(10), item(0, 'empty'), item(999, 'unmapped'), null, null],
  backpack_item_details: [item(20), null, null], neutral_item_details: item(30),
  ...overrides,
});

it('groups ten players by side in slot order and uses backend names, portraits and statistics', () => {
  const players = [128, 129, 130, 131, 132, 0, 1, 2, 3, 4].map(slot => player(slot)).reverse();
  render(<PlayersSection data={{ players }} />);
  const radiant = screen.getByRole('region', { name: 'Radiant' });
  const dire = screen.getByRole('region', { name: 'Dire' });
  expect(within(radiant).getAllByRole('article')).toHaveLength(5);
  expect(within(dire).getAllByRole('article')).toHaveLength(5);
  const first = within(dire).getAllByRole('article')[0]!;
  expect(first.textContent).toContain('Nick 128');
  expect(first.textContent).toContain('1 / 2 / 3');
  expect(first.textContent).toContain('Уровень 22');
  expect(within(first).getByRole('img', { name: 'Портрет Axe' }).getAttribute('src')).toBe('https://example.test/axe.png');
  fireEvent.click(within(first).getByText('Axe'));
  expect(within(first).getByText('Инвентарь')).toBeTruthy();
  expect(within(first).getAllByLabelText(/Инвентарь, слот [12]: Item 10/)).toHaveLength(2);
  expect(within(first).getByLabelText('Инвентарь, слот 3: Пусто')).toBeTruthy();
  expect(within(first).getByLabelText('Инвентарь, слот 4: Неизвестный предмет')).toBeTruthy();
  expect(within(first).getByLabelText('Рюкзак, слот 1: Item 20')).toBeTruthy();
  expect(within(first).getByLabelText('Нейтральный предмет, слот 1: Item 30')).toBeTruthy();
  fireEvent.click(within(first).getByText('Axe'));
  expect(within(first).getByRole('group').hasAttribute('open')).toBe(false);
});

it('changes one metric for both teams and sorts within each side without mutating API data', () => {
  const players = [player(0, { kills: 2, net_worth: 100 }), player(1, { kills: 8, net_worth: null }),
    player(128, { kills: 4, net_worth: 300 }), player(129, { kills: 9, net_worth: 400 })];
  const original = players.map(p => p.player_slot);
  render(<PlayersSection data={{ players }} />);
  fireEvent.change(screen.getByRole('combobox', { name: 'Показатель' }), { target: { value: 'net_worth' } });
  fireEvent.change(screen.getByRole('combobox', { name: 'Сортировка' }), { target: { value: 'kills' } });
  const radiant = within(screen.getByRole('region', { name: 'Radiant' })).getAllByRole('article');
  const dire = within(screen.getByRole('region', { name: 'Dire' })).getAllByRole('article');
  expect(radiant[0]!.textContent).toContain('Nick 1');
  expect(dire[0]!.textContent).toContain('Nick 129');
  expect(radiant[0]!.textContent).toContain('Стоимость—');
  expect(players.map(p => p.player_slot)).toEqual(original);
  fireEvent.change(screen.getByRole('combobox', { name: 'Сортировка' }), { target: { value: 'net_worth' } });
  expect(within(screen.getByRole('region', { name: 'Radiant' })).getAllByRole('article')[0]!.textContent).toContain('Nick 0');
});

it('keeps null distinct from zero, suppresses unconfirmed roles and handles empty and anonymous data', () => {
  render(<PlayersSection data={{ players: [player(0, { display_name: 'Очень длинный Unicode 🐉 ник', kills: null, deaths: 0,
    hero_name: null, hero_image_url: null, is_anonymous: true, position: { position: 'safe_lane', evidence: 'unknown' },
    obs_placed: null, sen_placed: null, stun_duration_seconds: null, buyback_count: null })] }} />);
  expect(screen.getByRole('status').textContent).toContain('Часть сведений');
  const first = screen.getByRole('article');
  expect(first.textContent).toContain('Анонимный игрок');
  expect(first.textContent).toContain('Неизвестный герой');
  expect(first.textContent).toContain('— / 0 / 3');
  expect(first.textContent).not.toContain('Безопасная линия');
  expect(within(first).getByRole('img', { name: 'Портрет героя недоступен' })).toBeTruthy();
  fireEvent.click(within(first).getByText('Неизвестный герой'));
  expect(first.textContent).toContain('Дополнительная статистика недоступна');
  cleanup();
  render(<PlayersSection data={{ players: [] }} />);
  expect(screen.getByRole('status').textContent).toContain('Данные игроков пока недоступны');
});

it('preserves Unicode nickname and handles image failure without changing hero name', () => {
  render(<PlayersSection data={{ players: [player(0, { display_name: 'Игрок 🐉 日本語' })] }} />);
  expect(screen.getByText('Игрок 🐉 日本語').getAttribute('title')).toBe('Игрок 🐉 日本語');
  fireEvent.error(screen.getByRole('img', { name: 'Портрет Axe' }));
  expect(screen.getByRole('img', { name: 'Портрет героя недоступен' })).toBeTruthy();
  expect(screen.getByText('Axe')).toBeTruthy();
});

it('switches the active team on mobile without changing the grouped players', () => {
  render(<PlayersSection data={{ players: [player(0), player(128)] }} />);
  fireEvent.click(screen.getByRole('button', { name: 'Dire' }));
  expect(screen.getByRole('button', { name: 'Dire' }).getAttribute('aria-pressed')).toBe('true');
  expect(screen.getByRole('region', { name: 'Dire' }).className).toContain('players-team-active');
  expect(within(screen.getByRole('region', { name: 'Radiant' })).getByText('Nick 0')).toBeTruthy();
});
