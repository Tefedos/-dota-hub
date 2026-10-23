// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthStatus } from './AuthStatus';
import { getMe, login, SessionExpired } from './api';
import { telegramInitData } from './telegram';

const user = { telegram_user_id: '9007199254740993', username: null, display_name: 'Fixture', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' };
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn());
  window.Telegram = { WebApp: { initData: '', ready: vi.fn() } };
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
  delete window.Telegram;
  document.getElementById('telegram-web-app')?.remove();
});

function success() {
  const raw = `synthetic-bridge-${crypto.randomUUID()}`;
  const token = `synthetic-session-${crypto.randomUUID()}`;
  window.Telegram = { WebApp: { initData: raw, ready: vi.fn() } };
  vi.mocked(fetch).mockResolvedValueOnce(json({ access_token: token, token_type: 'bearer', expires_in: 60, user })).mockResolvedValueOnce(json(user));
  return { raw, token };
}

describe('React authentication', () => {
  it('shows not Telegram and never submits empty initData', async () => {
    render(<AuthStatus />);
    expect(screen.getByText('Входим через Telegram…')).toBeTruthy();
    expect(await screen.findByText('Откройте Dota Hub через Telegram для входа')).toBeTruthy();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('sends raw initData, verifies the bearer session and keeps it out of storage and DOM', async () => {
    const storage = vi.spyOn(Storage.prototype, 'setItem');
    const { raw, token } = success();
    const view = render(<AuthStatus />);
    expect(await screen.findByText('Вход через Telegram выполнен')).toBeTruthy();
    expect(fetch).toHaveBeenNthCalledWith(1, '/api/v1/auth/telegram', expect.objectContaining({ body: JSON.stringify({ init_data: raw }), credentials: 'omit', redirect: 'error' }));
    expect(fetch).toHaveBeenNthCalledWith(2, '/api/v1/auth/me', expect.objectContaining({ headers: expect.objectContaining({ Authorization: `Bearer ${token}` }) }));
    expect(storage).not.toHaveBeenCalled();
    expect(document.body.textContent).not.toContain(token);
    expect(document.body.textContent).not.toContain(raw);
    view.unmount();
    window.Telegram = { WebApp: { initData: '', ready: vi.fn() } };
    render(<AuthStatus />);
    expect(await screen.findByText('Откройте Dota Hub через Telegram для входа')).toBeTruthy();
  });

  it('discards the session on expiry and does not refresh silently', async () => {
    vi.useFakeTimers();
    const { token } = success();
    render(<AuthStatus />);
    await act(async () => {});
    expect(screen.getByText('Вход через Telegram выполнен')).toBeTruthy();
    await act(async () => { await vi.advanceTimersByTimeAsync(60000); });
    expect(screen.getByText('Сессия истекла')).toBeTruthy();
    expect(screen.queryByText('Fixture')).toBeNull();
    expect(document.body.textContent).not.toContain(token);
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('checks expiry after waking from a suspended tab', async () => {
    vi.useFakeTimers();
    success();
    render(<AuthStatus />);
    await act(async () => {});
    vi.setSystemTime(Date.now() + 120000);
    act(() => { document.dispatchEvent(new Event('visibilitychange')); });
    expect(screen.getByText('Сессия истекла')).toBeTruthy();
  });

  it('shows an error without server text and supports an explicit retry', async () => {
    window.Telegram = { WebApp: { initData: 'synthetic-bridge-data', ready: vi.fn() } };
    vi.mocked(fetch).mockResolvedValueOnce(json({ error: { message: 'private-marker' } }, 503));
    render(<AuthStatus />);
    expect(await screen.findByText('Не удалось войти через Telegram')).toBeTruthy();
    expect(document.body.textContent).not.toContain('private-marker');
    success();
    fireEvent.click(screen.getByRole('button', { name: 'Повторить вход' }));
    expect(await screen.findByText('Вход через Telegram выполнен')).toBeTruthy();
  });

  it('treats a 401 from the protected endpoint as an expired session', async () => {
    success();
    vi.mocked(fetch).mockReset().mockResolvedValueOnce(json({ access_token: 'synthetic-token', token_type: 'bearer', expires_in: 60, user })).mockResolvedValueOnce(json({}, 401));
    render(<AuthStatus />);
    expect(await screen.findByText('Сессия истекла')).toBeTruthy();
    expect(screen.queryByText('Fixture')).toBeNull();
  });

  it('cancels requests on unmount', async () => {
    window.Telegram = { WebApp: { initData: 'synthetic-bridge-data', ready: vi.fn() } };
    vi.mocked(fetch).mockImplementation(() => new Promise(() => {}));
    const view = render(<AuthStatus />);
    await waitFor(() => expect(fetch).toHaveBeenCalledOnce());
    const signal = vi.mocked(fetch).mock.calls[0]?.[1]?.signal;
    view.unmount();
    expect(signal?.aborted).toBe(true);
  });
});

describe('bridge and HTTP boundary', () => {
  it('waits for the SDK load event and never reads initDataUnsafe', async () => {
    delete window.Telegram;
    const script = document.createElement('script');
    script.id = 'telegram-web-app'; document.head.append(script);
    const pending = telegramInitData(new AbortController().signal);
    const app = { initData: 'synthetic-raw', ready: vi.fn() };
    Object.defineProperty(app, 'initDataUnsafe', { get: () => { throw new Error('Unsafe data read'); } });
    window.Telegram = { WebApp: app };
    script.dispatchEvent(new Event('load'));
    expect(await pending).toBe('synthetic-raw');
  });

  it('bounds SDK loading time', async () => {
    vi.useFakeTimers(); delete window.Telegram;
    const script = document.createElement('script'); script.id = 'telegram-web-app'; document.head.append(script);
    const pending = expect(telegramInitData(new AbortController().signal)).rejects.toThrow('Telegram недоступен');
    await vi.advanceTimersByTimeAsync(8000);
    await pending;
  });

  it('rejects malformed success responses', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(json({ access_token: 'synthetic', token_type: 'bearer', expires_in: 900, user: { telegram_user_id: 123 } }));
    await expect(login('synthetic-raw', new AbortController().signal)).rejects.toThrow('Некорректный ответ сервера');
    vi.mocked(fetch).mockResolvedValueOnce(json({}, 401));
    await expect(getMe('synthetic', new AbortController().signal)).rejects.toBeInstanceOf(SessionExpired);
  });

  it('aborts a stalled HTTP request after five seconds', async () => {
    vi.useFakeTimers();
    vi.mocked(fetch).mockImplementation((_url, init) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
    }));
    const pending = expect(login('synthetic-raw', new AbortController().signal)).rejects.toThrow('Aborted');
    await vi.advanceTimersByTimeAsync(5000);
    await pending;
  });
});
