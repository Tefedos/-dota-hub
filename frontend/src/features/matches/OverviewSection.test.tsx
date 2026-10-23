// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import type { MatchEnvelope, OverviewReport } from './api';
import { OverviewSection } from './OverviewSection';
import independent from '../../../../backend/tests/fixtures/draft/independent.json';

const portrait = 'https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/antimage.png';
const nickname = 'ОченьДлинныйНикнеймБезПробеловКоторыйНеДолженЛоматьКарточкуИгрока';
const players = (start: number) => Array.from({ length: 5 }, (_, index) => ({
  player_slot: start + index, hero_id: index + 1, hero_name: index === 0 ? 'Anti-Mage' : `Герой ${index + 1}`,
  hero_image_url: index === 0 ? portrait : null, display_name: index === 0 ? nickname : null,
}));
const report: OverviewReport = {
  match_id: '9057722463', duration: 4349, start_time: 1792750321, game_mode: 22, patch: 60,
  game_mode_name: 'All Draft', patch_name: '7.41', winner: 'radiant',
  radiant: { team: 'radiant', team_id: null, name: null, score: 44, players: players(0) },
  dire: { team: 'dire', team_id: null, name: null, score: 42, players: players(128) },
  team_stats: { radiant: { kills: 44, towers_destroyed: null, roshan_kills: null },
    dire: { kills: 42, towers_destroyed: null, roshan_kills: null } },
  data_quality: { summary: 'complete', stats: 'complete', draft_order: 'complete', timeline: 'unavailable', roles: 'unavailable' },
  source_status: 'FOUND_PARTIAL', limitations: ['Хронология недоступна.'],
};
const envelope: MatchEnvelope = {
  schema_version: 1, match_id: report.match_id, status: 'ready', data: report as unknown as Record<string, unknown>,
  available_sections: ['overview', 'draft', 'players', 'timeline', 'ruiner'], error: null,
  limitations: ['Хронология недоступна.'], completeness: 'full',
};
const show = (data: OverviewReport = report, state: MatchEnvelope = envelope) =>
  render(<OverviewSection data={data as unknown as Record<string, unknown>} envelope={state} />);

afterEach(cleanup);

it('shows a verified result, metadata, ten players and one copy of repeated limitations', () => {
  show();
  expect(screen.getByRole('heading', { name: 'Обзор матча' })).toBeTruthy();
  const result = screen.getByRole('region', { name: 'Результат матча' });
  expect(within(result).getByLabelText('Счёт 44 : 42')).toBeTruthy();
  expect(result.querySelector('.overview-side-radiant.overview-winner')).not.toBeNull();
  expect(result.querySelector('.overview-side-dire.overview-winner')).toBeNull();
  expect(screen.getByText('72:29')).toBeTruthy();
  expect(screen.getByText('All Draft')).toBeTruthy();
  expect(screen.getByText('7.41')).toBeTruthy();
  expect(screen.getByText(/UTC/)).toBeTruthy();
  expect(screen.getAllByText(nickname)).toHaveLength(2);
  expect(screen.getAllByText('Анонимный игрок')).toHaveLength(8);
  expect(screen.getAllByRole('img', { name: 'Портрет героя недоступен' })).toHaveLength(8);
  expect(screen.getAllByText('Хронология недоступна.')).toHaveLength(1);
  const details = screen.getByText('Качество данных и ограничения').closest('details');
  expect(details?.open).toBe(false);
  fireEvent.click(screen.getByText('Качество данных и ограничения'));
  expect(details?.open).toBe(true);
  expect(screen.getByText('Исходные данные матча частично доступны.')).toBeTruthy();
  expect(screen.getByText('Готов · Есть ограничения')).toBeTruthy();
  expect(within(result).getAllByText('Radiant')).toHaveLength(1);
  expect(within(result).getAllByText('Dire')).toHaveLength(1);
  expect(screen.getAllByText('—')).toHaveLength(4);
  expect(screen.getByText('«—» означает: показатель не подтверждён данными матча.')).toBeTruthy();
  expect(document.querySelector('.overview-heading')?.textContent).not.toContain(report.match_id);
});

it('marks Dire as winner only when winner says Dire, even if its score is lower', () => {
  show({ ...report, winner: 'dire' });
  const result = screen.getByRole('region', { name: 'Результат матча' });
  expect(result.querySelector('.overview-side-dire.overview-winner')).not.toBeNull();
  expect(result.querySelector('.overview-side-radiant.overview-winner')).toBeNull();
});

it('does not invent a winner, score, names, portraits or missing participants', () => {
  show({ ...report, winner: null, radiant: { ...report.radiant, score: null, players: [report.radiant.players[0]!] },
    dire: { ...report.dire, players: [] }, game_mode_name: null, patch_name: null,
    team_stats: null, source_status: 'FOUND_PARTIAL' });
  const result = screen.getByRole('region', { name: 'Результат матча' });
  expect(within(result).getByLabelText('Счёт — : 42')).toBeTruthy();
  expect(result.querySelector('.overview-winner')).toBeNull();
  expect(screen.getByText('1 / 5 игроков')).toBeTruthy();
  expect(screen.getByText('0 / 5 игроков')).toBeTruthy();
  expect(screen.getByText('Данные игроков этой команды недоступны.')).toBeTruthy();
  expect(screen.getAllByText('Не определён')).toHaveLength(2);
  expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(6);
});

it('falls back when a portrait fails and refuses an unsafe URL', () => {
  const unsafe = { ...report, radiant: { ...report.radiant, players: [
    { ...report.radiant.players[0]!, hero_image_url: 'javascript:alert(1)' },
    ...report.radiant.players.slice(1),
  ] } };
  const { rerender } = show(unsafe);
  expect(screen.getAllByRole('img', { name: 'Портрет героя недоступен' })).toHaveLength(9);
  rerender(<OverviewSection data={report as unknown as Record<string, unknown>} envelope={envelope} />);
  const image = screen.getAllByAltText('Портрет Anti-Mage')[0]!;
  fireEvent.error(image);
  expect(screen.getAllByRole('img', { name: 'Портрет героя недоступен' })).toHaveLength(9);
});

it('shows an empty state when the report has no useful match data', () => {
  show({ ...report, duration: null, radiant: { ...report.radiant, score: null, players: [] },
    dire: { ...report.dire, score: null, players: [] } });
  expect(screen.getByText('Нет данных о матче.')).toBeTruthy();
});

it('renders the independent existing fixture with its own hero IDs and result', () => {
  const fixturePlayers = independent.match.players.map(player => ({
    player_slot: player.player_slot, hero_id: player.hero_id, hero_name: `Тестовый герой ${player.hero_id}`,
    hero_image_url: null, display_name: null,
  }));
  const fixture: OverviewReport = {
    ...report, match_id: String(independent.match.match_id), winner: 'radiant',
    radiant: { ...report.radiant, score: 0, players: fixturePlayers.filter(player => player.player_slot < 128) },
    dire: { ...report.dire, score: 0, players: fixturePlayers.filter(player => player.player_slot >= 128) },
    team_stats: null,
  };
  show(fixture, { ...envelope, match_id: fixture.match_id });
  expect(screen.getByLabelText('Счёт 0 : 0')).toBeTruthy();
  expect(screen.getByText('Тестовый герой 2')).toBeTruthy();
  expect(screen.getByText('Тестовый герой 54')).toBeTruthy();
  expect(screen.getAllByText('Анонимный игрок')).toHaveLength(10);
});
