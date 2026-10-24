// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import type { MatchPlayer } from './api';
import { RuinerSection } from './RuinerSection';
import { preliminaryReasons } from './ruiner';
import type { PerformancePlayer, PreliminarySelection, RuinerReport } from './ruiner';

afterEach(cleanup);
const signal = { code: 'relative_high:deaths_per_min', metric: 'deaths_per_min', text: 'Наблюдаемое отклонение от союзников.', value: .5, reference: .25, magnitude: 1 };
const preliminary = (status: 'single' | 'group' | 'none', slots: number[]): PreliminarySelection => ({
  projection_version: 'ri_preliminary_v1', minimum_margin: 15, status, player_slots: slots,
  leader_slot: status === 'single' ? slots[0]! : null, highest_index: status === 'none' ? null : 50,
  margin: status === 'group' ? 8 : status === 'single' ? 25 : null, confidence: 'low',
  reason_codes: [status === 'group' ? 'close_scores' : status === 'single' ? 'highest_relative_index' : 'incomplete_player_scores', 'leaver_context_unknown'],
});
function report(): RuinerReport {
  const players: PerformancePlayer[] = [0, 1, 2, 3, 4, 128, 129, 130, 131, 132].map(slot => ({
    player_slot: slot, team_player_number: slot % 128 + 1, hero_id: slot + 1, team: slot < 128 ? 'radiant' : 'dire',
    error_index: slot === 0 || slot === 131 ? 50 : slot === 4 ? 42 : 0, confidence: 'low', evidence_coverage: 1,
    position: { position: null, evidence: 'unknown' }, positive_signals: [], negative_signals: [signal],
    missing_metrics: ['gpm'], limitations: ['Роль не подтверждена.'],
  }));
  const selection = { selection_status: 'no_confident_selection' as const, selected_player_slot: null };
  return { match_id: '123', quality: 'partial', players, limitations: ['Нет популяционной нормы.'],
    teams: { radiant: { selection, preliminary_selection: preliminary('group', [0, 4]) },
      dire: { selection, preliminary_selection: preliminary('single', [131]) } } };
}
function show(data = report(), identities: MatchPlayer[] = []) {
  return render(<RuinerSection data={data as unknown as Record<string, unknown>} identities={identities} heroNames={{ 1: 'Techies', 5: 'Mirana', 132: 'Pudge' }} />);
}

it('shows a group with equal highlights and switches to a single Dire leader by slot', () => {
  const data = report(), before = JSON.stringify(data);
  const { container } = show(data);
  expect(screen.getByRole('heading', { name: 'Игроки с близкими индексами' })).toBeTruthy();
  expect([...container.querySelectorAll('.ri-player-selected')].map(p => p.getAttribute('data-player-slot'))).toEqual(['0', '4']);
  expect(screen.getAllByText('В группе близких индексов')).toHaveLength(2);
  expect(container.querySelectorAll('.ri-player')).toHaveLength(5);
  fireEvent.click(screen.getByRole('button', { name: 'Dire' }));
  expect(screen.getByRole('heading', { name: 'Предварительный лидер по индексу — Pudge' })).toBeTruthy();
  expect(container.querySelector('.ri-player-selected')?.getAttribute('data-player-slot')).toBe('131');
  expect(screen.getByText(/Отрыв от следующего: 25/)).toBeTruthy();
  expect(screen.getByText(/Подтверждённый кандидат: не определён. Уверенность: низкая/)).toBeTruthy();
  expect(JSON.stringify(data)).toBe(before);
});

it('does not invent a leader or zero for none and old reports', () => {
  const data = report();
  data.players[0]!.error_index = null;
  data.teams.radiant!.preliminary_selection = preliminary('none', []);
  const { container, rerender } = show(data);
  expect(screen.getByText('Нет оценки')).toBeTruthy();
  expect(screen.getByText(preliminaryReasons.incomplete_player_scores!)).toBeTruthy();
  expect(container.querySelector('.ri-player-selected')).toBeNull();
  delete data.teams.radiant!.preliminary_selection;
  rerender(<RuinerSection data={data as unknown as Record<string, unknown>} heroNames={{}} />);
  expect(screen.getByText(/В сохранённом отчёте нет предварительного результата/)).toBeTruthy();
  expect(container.querySelector('.ri-player-selected')).toBeNull();
});

it('gives confirmed selection priority and does not duplicate preliminary conclusions', () => {
  const data = report();
  data.teams.radiant!.selection = { selection_status: 'selected', selected_player_slot: 1 };
  data.players[1]!.confidence = 'medium';
  const { container } = show(data);
  expect(screen.getByRole('heading', { name: /Подтверждённый выбор модели/ })).toBeTruthy();
  expect(screen.queryByRole('heading', { name: 'Игроки с близкими индексами' })).toBeNull();
  expect(container.querySelector('.ri-player-selected')?.getAttribute('data-player-slot')).toBe('1');
  expect(screen.queryByText(/Подтверждённый кандидат: не определён/)).toBeNull();
});

it('joins catalog identities by slot, shows portrait, long nickname and expandable localized evidence', () => {
  const nickname = 'ОченьДлинныйНикнейм'.repeat(12);
  const identities = [{ player_slot: 0, hero_id: 1, hero_name: 'Techies', hero_image_url: 'https://example.test/techies.png', display_name: nickname },
    { player_slot: 4, hero_id: 999, hero_name: 'Wrong hero', hero_image_url: 'https://example.test/wrong.png' }] as MatchPlayer[];
  const data = report();
  data.players[0]!.positive_signals = [{ ...signal, code: 'positive:healing_per_min', metric: 'healing_per_min' }];
  const { container } = show(data, identities);
  expect(screen.getByRole('img', { name: 'Портрет Techies' }).getAttribute('src')).toBe('https://example.test/techies.png');
  expect(screen.getByText(nickname)).toBeTruthy();
  expect(screen.queryByText('Wrong hero')).toBeNull();
  expect(screen.getByText('Участник №5 · слот 4')).toBeTruthy();
  const card = container.querySelector('.ri-player')! as HTMLElement;
  const details = card.querySelector('details')!;
  expect(details.open).toBe(false);
  fireEvent.click(card.querySelector('summary')!);
  expect(details.open).toBe(true);
  expect(within(card).getAllByText(/Значение: 0,5 · Ориентир: 0,25/)).toHaveLength(2);
  expect(within(card).getByText(/Покрытие взвешенных отрицательных осей: 100%/)).toBeTruthy();
  expect(within(card).getByText(/Недоступны: Золото в минуту/)).toBeTruthy();
  expect(card.textContent).not.toContain('relative_high');
  expect(card.textContent).not.toContain('штрафные баллы');
  const limits = container.querySelector<HTMLDetailsElement>('.ri-limitations')!;
  expect(limits.open).toBe(false);
  fireEvent.click(limits.querySelector('summary')!);
  expect(limits.open).toBe(true);
});

it.each(Object.keys(preliminaryReasons))('localizes preliminary reason %s', reason => {
  const data = report();
  data.teams.radiant!.preliminary_selection = { ...preliminary('none', []), reason_codes: [reason] };
  show(data);
  expect(within(screen.getByRole('article', { name: 'Результат команды' })).getByText(preliminaryReasons[reason]!)).toBeTruthy();
});

it('handles empty data and unknown future reason without leaking enums', () => {
  const data = report();
  data.players = [];
  data.quality = 'insufficient';
  data.teams.radiant!.preliminary_selection = { ...preliminary('none', []), reason_codes: ['future_reason'] };
  show(data);
  expect(screen.getByText('Данные игроков этой команды недоступны.')).toBeTruthy();
  expect(screen.getByText('Дополнительное ограничение данных.')).toBeTruthy();
  expect(document.body.textContent).not.toContain('future_reason');
});

it('keeps all envelope limitations once in the collapsed disclosure', () => {
  const data = report();
  const { container } = render(<RuinerSection data={data as unknown as Record<string, unknown>} heroNames={{}}
    envelopeLimits={['Нет популяционной нормы.', 'Нет Timeline.', 'Нет Roles.']} />);
  const limits = container.querySelector<HTMLDetailsElement>('.ri-limitations')!;
  expect(limits.open).toBe(false);
  expect(within(limits).getAllByText('Нет популяционной нормы.')).toHaveLength(1);
  expect(limits.textContent).toContain('Нет Timeline.');
  expect(limits.textContent).toContain('Нет Roles.');
});
