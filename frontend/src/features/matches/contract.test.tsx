// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { App } from '../../app/App';
import { MatchReportPage } from '../../pages/MatchReportPage';
import { telegramStartMatchId, validMatchId } from '../auth/telegram';
import { getMatchSection } from './api';

const user = { telegram_user_id: '42', username: null, display_name: 'Fixture', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' };
const session = { access_token: 'test-memory-token', token_type: 'bearer' as const, expires_in: 900, user };
const envelope = { schema_version: 1, match_id: '8888765469', status: 'ready', available_sections: ['overview', 'draft'], data: { match_id: '8888765469' }, error: null, limitations: [] };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

beforeEach(() => { vi.stubGlobal('fetch', vi.fn()); vi.spyOn(window, 'scrollTo').mockImplementation(() => {}); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); delete window.Telegram; window.history.replaceState({}, '', '/'); });

it('routes signed raw start_param after login and sends the bearer token', async () => {
  const raw = 'auth_date=synthetic&start_param=match_8888765469&hash=synthetic';
  window.Telegram = { WebApp: { initData: raw, ready: vi.fn() } };
  vi.mocked(fetch).mockImplementation(async path => {
    if (path === '/api/v1/auth/telegram') return json(session);
    if (path === '/api/v1/auth/me') return json(user);
    if (String(path).includes('/matches/')) return json(envelope);
    return json({ status: 'ok', service: 'dota-hub-api' });
  });
  render(<MemoryRouter><App /></MemoryRouter>);
  expect(await screen.findByRole('heading', { name: 'Матч 8888765469' })).toBeTruthy();
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/v1/matches/8888765469/overview', expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Bearer test-memory-token' }) })));
  expect(fetch).toHaveBeenCalledWith('/api/v1/auth/telegram', expect.objectContaining({ body: JSON.stringify({ init_data: raw }) }));
  expect(document.body.textContent).not.toContain(session.access_token);
  expect(window.localStorage.getItem('access_token')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Драфт' }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/v1/matches/8888765469/draft', expect.anything()));
});

it('does not fetch from a replayed match link without an authenticated session', async () => {
  render(<MemoryRouter initialEntries={['/matches/8888765469']}><Routes><Route path="/matches/:matchId" element={<MatchReportPage session={null} />} /></Routes></MemoryRouter>);
  expect(screen.getByText('Для просмотра анализа войдите через Telegram.')).toBeTruthy();
  expect(fetch).not.toHaveBeenCalled();
});

it('accepts only canonical positive bigint IDs in start parameters', () => {
  for (const value of ['0', '-1', '01', '1e3', '9223372036854775808', ' 123', '<b>1</b>']) expect(validMatchId(value)).toBeNull();
  expect(validMatchId('9223372036854775807')).toBe('9223372036854775807');
  window.Telegram = { WebApp: { initData: '', startParam: 'match_8888765469', ready: vi.fn() } };
  expect(telegramStartMatchId()).toBe('8888765469');
  window.Telegram.WebApp!.startParam = 'match_0';
  expect(telegramStartMatchId()).toBeNull();
});

it('shows pending and supports an explicit read-only refresh', async () => {
  vi.mocked(fetch).mockResolvedValueOnce(json({ ...envelope, status: 'running', data: null }, 202)).mockResolvedValueOnce(json(envelope));
  render(<MemoryRouter initialEntries={['/matches/8888765469']}><Routes><Route path="/matches/:matchId" element={<MatchReportPage session={session} />} /></Routes></MemoryRouter>);
  expect(await screen.findByText('Матч обрабатывается. Обновите статус через несколько секунд.')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Обновить' }));
  await waitFor(() => expect(screen.getByRole('heading', { name: 'Обзор матча' })).toBeTruthy());
  expect(screen.queryByText('Данные раздела получены.')).toBeNull();
  expect(fetch).toHaveBeenCalledTimes(2);
});

it.each([401, 404, 429, 503])('handles HTTP %s without displaying private error text', async status => {
  vi.mocked(fetch).mockResolvedValueOnce(json({ ...envelope, status: 'failed', data: null, error: { message: 'private-token', code: 'PRIVATE', retryable: true } }, status));
  await expect(getMatchSection('8888765469', 'overview', session.access_token, new AbortController().signal)).rejects.not.toThrow('private-token');
});

it('rejects a success payload for a different match', async () => {
  vi.mocked(fetch).mockResolvedValueOnce(json({ ...envelope, match_id: '123' }));
  await expect(getMatchSection('8888765469', 'overview', session.access_token, new AbortController().signal)).rejects.toThrow('Некорректный ответ');
});

it('shows a friendly network error and allows an explicit retry', async () => {
  vi.mocked(fetch).mockRejectedValueOnce(new TypeError('Failed to fetch')).mockResolvedValueOnce(json(envelope));
  render(<MemoryRouter initialEntries={['/matches/8888765469']}><Routes><Route path="/matches/:matchId" element={<MatchReportPage session={session} />} /></Routes></MemoryRouter>);
  expect(await screen.findByText('Нет связи с сервером. Проверьте подключение и повторите попытку.')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Обновить' }));
  expect(await screen.findByText('Нет данных о матче.')).toBeTruthy();
  expect(document.body.textContent).not.toContain('Failed to fetch');
});

it('does not show a late response from the previous Match ID', async () => {
  let resolveOld!: (value: Response) => void;
  vi.mocked(fetch).mockImplementation(path => String(path).includes('8888765469')
    ? new Promise<Response>(resolve => { resolveOld = resolve; })
    : Promise.resolve(json({ ...envelope, match_id: '9057722463', data: { match_id: '9057722463' } })));
  function SwitchMatch() {
    const navigate = useNavigate();
    return <button type="button" onClick={() => navigate('/matches/9057722463')}>Другой матч</button>;
  }
  render(<MemoryRouter initialEntries={['/matches/8888765469']}><SwitchMatch /><Routes><Route path="/matches/:matchId" element={<MatchReportPage session={session} />} /></Routes></MemoryRouter>);
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/v1/matches/8888765469/overview', expect.anything()));
  fireEvent.click(screen.getByRole('button', { name: 'Другой матч' }));
  expect(await screen.findByRole('heading', { name: 'Матч 9057722463' })).toBeTruthy();
  resolveOld(json(envelope));
  await screen.findByText('Нет данных о матче.');
  expect(document.body.textContent).not.toContain('DOTA HUB / МАТЧ 8888765469');
  expect(fetch).toHaveBeenCalledWith('/api/v1/matches/9057722463/overview', expect.anything());
});

it('uses the existing tabs to open every other analysis section', async () => {
  vi.mocked(fetch).mockResolvedValue(json(envelope));
  render(<MemoryRouter initialEntries={['/matches/8888765469']}><Routes><Route path="/matches/:matchId" element={<MatchReportPage session={session} />} /></Routes></MemoryRouter>);
  await screen.findByRole('heading', { name: 'Обзор матча' });
  expect(Array.from(screen.getByRole('navigation', { name: 'Разделы анализа' }).querySelectorAll('button'), button => button.textContent))
    .toEqual(['Обзор', 'Игроки', 'Драфт', 'Ход матча', 'Индекс ошибок / Вывод']);
  for (const [name, path] of [
    ['Драфт', 'draft'], ['Игроки', 'players'], ['Ход матча', 'timeline'], ['Индекс ошибок / Вывод', 'ruiner'],
  ]) {
    fireEvent.click(screen.getByRole('button', { name }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(`/api/v1/matches/8888765469/${path}`, expect.anything()));
  }
});

it('shows the players loading, success and missing-match states without a technical success message', async () => {
  let complete!: (value: Response) => void;
  vi.mocked(fetch).mockResolvedValueOnce(json(envelope)).mockImplementationOnce(() => new Promise<Response>(resolve => { complete = resolve; }));
  render(<MemoryRouter initialEntries={['/matches/8888765469']}><Routes><Route path="/matches/:matchId" element={<MatchReportPage session={session} />} /></Routes></MemoryRouter>);
  await screen.findByRole('heading', { name: 'Обзор матча' });
  fireEvent.click(screen.getByRole('button', { name: 'Игроки' }));
  expect(screen.getByText('Загружаем игроков…')).toBeTruthy();
  complete(json(envelope));
  await waitFor(() => expect(screen.getByText('Данные игроков пока недоступны.')).toBeTruthy());
  expect(screen.queryByText('Данные раздела получены.')).toBeNull();
  vi.mocked(fetch).mockResolvedValueOnce(json({ ...envelope, status: 'failed', data: null, error: { code: 'NOT_FOUND', message: 'internal', retryable: false } }, 404));
  fireEvent.click(screen.getByRole('button', { name: 'Обновить' }));
  expect(await screen.findByText('Матч не найден в OpenDota.')).toBeTruthy();
  expect(document.body.textContent).not.toContain('internal');
});

it('shows RI loading, empty, error and retry through the existing page', async () => {
  let complete!: (value: Response) => void;
  vi.mocked(fetch).mockImplementation(path => String(path).endsWith('/ruiner')
    ? new Promise<Response>(resolve => { complete = resolve; }) : Promise.resolve(json(envelope)));
  render(<MemoryRouter initialEntries={['/matches/8888765469']}><Routes><Route path="/matches/:matchId" element={<MatchReportPage session={session} />} /></Routes></MemoryRouter>);
  await screen.findByRole('heading', { name: 'Обзор матча' });
  fireEvent.click(screen.getByRole('button', { name: 'Индекс ошибок / Вывод' }));
  expect(screen.getByText('Загружаем анализ…')).toBeTruthy();
  complete(json({ ...envelope, data: { match_id: envelope.match_id, quality: 'insufficient', players: [], teams: {}, limitations: [] } }));
  expect(await screen.findByText('Данные игроков этой команды недоступны.')).toBeTruthy();
  vi.mocked(fetch).mockRejectedValue(new TypeError('network'));
  fireEvent.click(screen.getByRole('button', { name: 'Обновить' }));
  expect(await screen.findByText('Нет связи с сервером. Проверьте подключение и повторите попытку.')).toBeTruthy();
  expect(screen.queryByRole('heading', { name: 'Предварительный лидер не определён' })).toBeNull();
});
